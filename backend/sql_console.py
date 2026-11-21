"""Read-only SQL console.

Three layers keep it read-only:
  1. check_sql() allows exactly one statement, and only read statements
     (SELECT, WITH, VALUES, TABLE, EXPLAIN, SHOW, DESCRIBE).
  2. The statement runs inside a READ ONLY transaction, so the database itself rejects writes
     (including data-changing CTEs and EXPLAIN ANALYZE of a write). A single statement cannot
     switch that transaction back to read-write.
  3. The transaction is always rolled back, and the usual query timeout applies.
"""
import re
import time
import psycopg2
import pymysql
import pymysql.cursors
from db_manager import ApiError, open_conn, is_timeout, timeout_error

MAX_ROWS = 1000
READ_KEYWORDS = {
    "postgresql": {"SELECT", "WITH", "VALUES", "TABLE", "EXPLAIN", "SHOW"},
    "mysql": {"SELECT", "WITH", "VALUES", "TABLE", "EXPLAIN", "SHOW", "DESCRIBE", "DESC"},
}
_DOLLAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$")


def _quoted_end(sql, i, quote, backslash):
    """Index just past the quoted text that starts at sql[i]."""
    j, n = i + 1, len(sql)
    while j < n:
        c = sql[j]
        if backslash and c == "\\":
            j += 2
            continue
        if c == quote:
            if j + 1 < n and sql[j + 1] == quote:  # doubled quote = escaped quote
                j += 2
                continue
            return j + 1
        j += 1
    raise ApiError("Unterminated string or quoted name")


def mask(sql, db_type, mysql_backslash=True):
    """Return sql with the same length, where comments become spaces and strings / quoted names
    become 'x', so what remains is only real SQL code."""
    mysql = db_type == "mysql"
    out, i, n = [], 0, len(sql)
    while i < n:
        c, nxt = sql[i], sql[i + 1:i + 2]
        prev = sql[i - 1] if i else ""
        fill = "x"  # strings and quoted names are content
        if (c == "-" and nxt == "-") or (mysql and c == "#"):
            fill = " "  # comments are whitespace
            end = sql.find("\n", i)
            end = n if end < 0 else end
        elif c == "/" and nxt == "*":
            fill = " "
            if mysql and sql[i + 2:i + 3] == "!":
                raise ApiError("MySQL /*! ... */ comments are not allowed in the console")
            depth, end = 1, i + 2
            while end < n and depth:
                if not mysql and sql.startswith("/*", end):  # PostgreSQL comments nest
                    depth, end = depth + 1, end + 2
                elif sql.startswith("*/", end):
                    depth, end = depth - 1, end + 2
                else:
                    end += 1
            if depth:
                raise ApiError("Unterminated comment")
        elif c == "'":
            if mysql:
                backslash = mysql_backslash
            else:  # PostgreSQL: backslash escapes only in E'...' strings
                before = sql[i - 2] if i >= 2 else ""
                backslash = prev in "eE" and prev != "" and not (before.isalnum() or before == "_")
            end = _quoted_end(sql, i, "'", backslash)
        elif c == '"':
            end = _quoted_end(sql, i, '"', mysql and mysql_backslash)
        elif c == "`" and mysql:
            end = _quoted_end(sql, i, "`", False)
        elif c == "$" and not mysql and not (prev.isalnum() or prev == "_"):
            m = _DOLLAR.match(sql, i)
            if not m:
                out.append(c)
                i += 1
                continue
            close = sql.find(m.group(0), m.end())
            if close < 0:
                raise ApiError("Unterminated $-quoted string")
            end = close + len(m.group(0))
        else:
            out.append(c)
            i += 1
            continue
        out.append(fill * (end - i))
        i = end
    return "".join(out)


def check_sql(sql, db_type, mysql_backslash=True):
    """Validate a console statement and return it without trailing semicolons."""
    code = mask(sql, db_type, mysql_backslash)
    trimmed = code.rstrip()
    while trimmed.endswith(";"):
        trimmed = trimmed[:-1].rstrip()
    end = len(trimmed)
    if not trimmed.strip():
        raise ApiError("Type a query to run")
    if ";" in code[:end]:
        raise ApiError("Run one statement at a time")
    m = re.match(r"[\s(]*([A-Za-z]+)", code[:end])
    keyword = m.group(1).upper() if m else ""
    if keyword not in READ_KEYWORDS[db_type]:
        allowed = ", ".join(sorted(READ_KEYWORDS[db_type]))
        raise ApiError(f"The console is read-only. Statements must start with one of: {allowed}")
    if db_type == "mysql" and re.search(r"\bINTO\s+(OUTFILE|DUMPFILE)\b", code[:end], re.I):
        raise ApiError("SELECT ... INTO OUTFILE is not allowed")
    return sql[:end]


def _unique(names):
    seen, out = {}, []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    return out


def run_query(cfg, sql):
    pg = cfg["db_type"] == "postgresql"
    conn = open_conn(cfg)
    try:
        if pg:
            sql = check_sql(sql, "postgresql")
            conn.autocommit = False
            with conn.cursor() as setup:
                setup.execute("SET TRANSACTION READ ONLY")
            keyword = re.match(r"[\s(]*([A-Za-z]+)", mask(sql, "postgresql")).group(1).upper()
            # Server-side cursor for row-returning queries, so a huge result isn't loaded into memory
            cur = conn.cursor(name="console") if keyword in {"SELECT", "WITH", "VALUES", "TABLE"} else conn.cursor()
        else:
            with conn.cursor() as setup:
                setup.execute("SELECT @@SESSION.sql_mode")
                no_backslash = "NO_BACKSLASH_ESCAPES" in (setup.fetchone()[0] or "")
            sql = check_sql(sql, "mysql", mysql_backslash=not no_backslash)
            conn.cursor().execute("START TRANSACTION READ ONLY")
            cur = conn.cursor(pymysql.cursors.SSCursor)  # unbuffered: stream rows
        started = time.perf_counter()
        cur.execute(sql)
        rows = cur.fetchmany(MAX_ROWS + 1)
        elapsed = round((time.perf_counter() - started) * 1000)
        if cur.description is None:
            return {"columns": [], "rows": [], "row_count": 0, "truncated": False, "elapsed_ms": elapsed}
        cols = _unique([d[0] for d in cur.description])
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {"columns": cols, "rows": [dict(zip(cols, r)) for r in rows],
                "row_count": len(rows), "truncated": truncated, "elapsed_ms": elapsed}
    except ApiError:
        raise
    except Exception as e:
        if is_timeout(e):
            raise timeout_error() from e
        if isinstance(e, (psycopg2.Error, pymysql.MySQLError)):
            raise ApiError(str(e).strip()[:1000])
        raise
    finally:
        # Closing ends the session, which rolls back the read-only transaction.
        try:
            if pg:
                conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
