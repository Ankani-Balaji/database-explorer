import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
import psycopg2
import psycopg2.extensions
import pymysql

DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306}
# Longest a single query may run before the database cancels it (env QUERY_TIMEOUT_MS, 0 = no limit)
QUERY_TIMEOUT_MS = max(int(os.environ.get("QUERY_TIMEOUT_MS", "15000")), 0)
MYSQL_TIMEOUT_CODES = {3024, 1969}  # MySQL max_execution_time, MariaDB max_statement_time
# A saved connection unused for this long is forgotten (env CONNECTION_IDLE_HOURS, 0 = never)
CONNECTION_IDLE_SECONDS = max(float(os.environ.get("CONNECTION_IDLE_HOURS", "8")), 0) * 3600
POOL_MAX_IDLE = 4          # open database connections kept per saved connection
POOL_IDLE_SECONDS = 300    # close pooled database connections unused for 5 minutes
POOL_CHECK_AFTER = 30      # re-check a pooled connection that sat idle this long

_lock = threading.Lock()
_connections = {}  # connection_id -> {"cfg": config, "last_used": time} (server memory only)
_pool = {}         # login key -> [(open connection, idle since)]


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def validate(raw, need_db=True):
    db_type = str(raw.get("db_type", "")).lower()
    if db_type not in DEFAULT_PORTS:
        raise ApiError("Database type must be PostgreSQL or MySQL")
    try:
        port = int(raw.get("port") or DEFAULT_PORTS[db_type])
    except ValueError:
        raise ApiError("Port must be a number")
    cfg = {
        "db_type": db_type,
        "host": str(raw.get("host") or "localhost").strip(),
        "port": port,
        "database": str(raw.get("database") or "").strip(),
        "user": str(raw.get("user") or "").strip(),
        "password": str(raw.get("password") or ""),
    }
    if not cfg["user"] or (need_db and not cfg["database"]):
        raise ApiError("Username and database name are required" if need_db else "Username is required")
    # MySQL: schema == database
    cfg["schema"] = (str(raw.get("schema") or "public").strip()
                     if db_type == "postgresql" else cfg["database"])
    return cfg


def open_conn(cfg):
    """Open a READ-ONLY connection."""
    try:
        if cfg["db_type"] == "postgresql":
            conn = psycopg2.connect(host=cfg["host"], port=cfg["port"], dbname=cfg["database"],
                                    user=cfg["user"], password=cfg["password"], connect_timeout=5,
                                    options=f"-c statement_timeout={QUERY_TIMEOUT_MS}")
            conn.set_session(readonly=True, autocommit=True)
        else:
            conn = pymysql.connect(host=cfg["host"], port=cfg["port"], database=cfg["database"],
                                   user=cfg["user"], password=cfg["password"], connect_timeout=5,
                                   autocommit=True, charset="utf8mb4")
            with conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                _mysql_timeout(cur)
        return conn
    except Exception as e:
        raise ApiError("Connection failed: " + str(e).strip()[:400])


def _mysql_timeout(cur):
    try:
        cur.execute("SET SESSION max_execution_time = %s", (QUERY_TIMEOUT_MS,))  # MySQL 5.7.8+
    except pymysql.MySQLError:
        try:
            cur.execute("SET SESSION max_statement_time = %s", (QUERY_TIMEOUT_MS / 1000,))  # MariaDB
        except pymysql.MySQLError:
            pass  # old server without either setting: browse without a limit


def is_timeout(e):
    if isinstance(e, psycopg2.extensions.QueryCanceledError):
        return True
    return isinstance(e, pymysql.MySQLError) and bool(e.args) and e.args[0] in MYSQL_TIMEOUT_CODES


def timeout_error():
    return ApiError(f"The query took longer than {QUERY_TIMEOUT_MS / 1000:g}s and was cancelled. "
                    "Try a narrower search or a smaller page size.", 504)


# ---------- saved connections ----------

def _close_quietly(conn):
    try:
        conn.close()
    except Exception:
        pass


def _key(cfg):
    """Pooled database connections are shared by saved connections with the same login."""
    return (cfg["db_type"], cfg["host"], cfg["port"], cfg["database"], cfg["user"], cfg["password"])


def _drop_unused_pools():
    """Remove pools no saved connection uses any more. Call with _lock held; returns conns to close."""
    used = {_key(e["cfg"]) for e in _connections.values()}
    closing = []
    for key in [k for k in _pool if k not in used]:
        closing += [c for c, _ in _pool.pop(key)]
    return closing


def _expire(now):
    """Forget saved connections idle too long. Call with _lock held; returns conns to close."""
    if CONNECTION_IDLE_SECONDS:
        for cid in [c for c, e in _connections.items() if now - e["last_used"] > CONNECTION_IDLE_SECONDS]:
            del _connections[cid]
    return _drop_unused_pools()


def add_connection(cfg):
    cid = uuid.uuid4().hex
    with _lock:
        closing = _expire(time.monotonic())
        _connections[cid] = {"cfg": cfg, "last_used": time.monotonic()}
    for c in closing:
        _close_quietly(c)
    return cid


def get_cfg(cid):
    now = time.monotonic()
    with _lock:
        closing = _expire(now)
        entry = _connections.get(cid or "")
        if entry:
            entry["last_used"] = now
    for c in closing:
        _close_quietly(c)
    if not entry:
        raise ApiError("Not connected (or the connection expired). Please connect to a database.", 401)
    return entry["cfg"]


def remove_connection(cid):
    with _lock:
        _connections.pop(cid or "", None)
        closing = _drop_unused_pools()
    for c in closing:
        _close_quietly(c)


# ---------- connection pool ----------

def _alive(cfg, conn):
    try:
        if cfg["db_type"] == "postgresql":
            if conn.closed:
                return False
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        else:
            conn.ping(reconnect=False)  # reconnecting would lose the read-only session settings
        return True
    except Exception:
        return False


@contextmanager
def pooled_conn(cfg):
    """A read-only connection reused across requests. If the work fails, the connection is
    closed instead of returned, so a broken connection is never reused."""
    key, now, conn, stale = _key(cfg), time.monotonic(), None, []
    with _lock:
        idle = _pool.get(key, [])
        while idle and conn is None:
            c, since = idle.pop()
            if now - since > POOL_IDLE_SECONDS:
                stale.append(c)
            else:
                conn, idle_for = c, now - since
    for c in stale:
        _close_quietly(c)
    if conn is not None and idle_for > POOL_CHECK_AFTER and not _alive(cfg, conn):
        _close_quietly(conn)
        conn = None
    if conn is None:
        conn = open_conn(cfg)

    ok = False
    try:
        yield conn
        ok = True
    finally:
        keep = False
        if ok:
            with _lock:
                in_use = any(_key(e["cfg"]) == key for e in _connections.values())
                idle = _pool.setdefault(key, [])
                if in_use and len(idle) < POOL_MAX_IDLE:
                    idle.append((conn, time.monotonic()))
                    keep = True
                elif not idle:
                    _pool.pop(key, None)
        if not keep:
            _close_quietly(conn)


def public_info(cfg, table_count=None):
    info = {k: cfg[k] for k in ("db_type", "host", "port", "database", "schema", "user")}
    if table_count is not None:
        info["table_count"] = table_count
    return info


def quote(cfg, name):
    if cfg["db_type"] == "postgresql":
        return '"' + name.replace('"', '""') + '"'
    return "`" + name.replace("`", "``") + "`"


def table_ref(cfg, table):
    return f"{quote(cfg, cfg['schema'])}.{quote(cfg, table)}"


def col_ref(cfg, name):
    return "t." + quote(cfg, name)  # every query aliases the table as 't'


# ---------- catalog ----------

def list_objects(cur, cfg, name=None):
    """Tables and views in the current schema (or just the one called `name`),
    with row estimates and sizes."""
    params = [cfg["schema"]] + ([name] if name is not None else [])
    if cfg["db_type"] == "postgresql":
        cur.execute(
            "SELECT c.relname, CASE WHEN c.relkind IN ('v', 'm') THEN 'view' ELSE 'table' END, "
            "       CASE WHEN c.relkind = 'v' OR c.reltuples < 0 THEN NULL ELSE c.reltuples::bigint END, "
            "       CASE WHEN c.relkind = 'v' THEN NULL ELSE pg_total_relation_size(c.oid) END "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'v', 'm') "
            "  AND has_table_privilege(c.oid, 'SELECT') "
            + ("AND c.relname = %s " if name is not None else "") +
            "ORDER BY c.relname", params)
    else:
        cur.execute(
            "SELECT table_name, CASE WHEN table_type = 'VIEW' THEN 'view' ELSE 'table' END, "
            "       table_rows, data_length + index_length "
            "FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type IN ('BASE TABLE', 'VIEW') "
            + ("AND table_name = %s " if name is not None else "") +
            "ORDER BY table_name", params)
    return [{"name": r[0], "kind": r[1], "rows_estimate": r[2], "size_bytes": r[3]}
            for r in cur.fetchall()]


def list_tables(cur, cfg):
    return [o["name"] for o in list_objects(cur, cfg)]


def find_object(cur, cfg, name):
    # MySQL compares names case-insensitively on some systems, so check the exact name too
    return next((o for o in list_objects(cur, cfg, name) if o["name"] == name), None)


def table_columns(cur, cfg, table):
    if cfg["db_type"] == "postgresql":
        # pg_catalog also covers materialized views, which information_schema leaves out
        cur.execute(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull, "
            "       pg_get_expr(d.adbin, d.adrelid) "
            "FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
            "WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped "
            "ORDER BY a.attnum", (table_ref(cfg, table),))
    else:
        cur.execute(
            "SELECT column_name, column_type, is_nullable = 'YES', column_default "
            "FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position", (cfg["schema"], table))
    return [{"name": r[0], "type": r[1], "nullable": bool(r[2]), "default": r[3]}
            for r in cur.fetchall()]


def primary_key(cur, cfg, table):
    if cfg["db_type"] == "postgresql":
        # pg_catalog, not information_schema: the latter hides constraints from SELECT-only users
        cur.execute("SELECT a.attname FROM pg_index i "
                    "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
                    "WHERE i.indrelid = %s::regclass AND i.indisprimary "
                    "ORDER BY array_position(i.indkey::int2[], a.attnum)",
                    (table_ref(cfg, table),))
    else:
        cur.execute("SELECT column_name FROM information_schema.key_column_usage "
                    "WHERE table_schema = %s AND table_name = %s AND constraint_name = 'PRIMARY' "
                    "ORDER BY ordinal_position", (cfg["schema"], table))
    return [r[0] for r in cur.fetchall()]


def foreign_keys(cur, cfg, table):
    if cfg["db_type"] == "postgresql":
        cur.execute(
            "SELECT con.conname, a.attname, rn.nspname, rc.relname, ra.attname "
            "FROM pg_constraint con "
            "CROSS JOIN LATERAL unnest(con.conkey, con.confkey) WITH ORDINALITY AS k(col, refcol, pos) "
            "JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.col "
            "JOIN pg_class rc ON rc.oid = con.confrelid "
            "JOIN pg_namespace rn ON rn.oid = rc.relnamespace "
            "JOIN pg_attribute ra ON ra.attrelid = con.confrelid AND ra.attnum = k.refcol "
            "WHERE con.conrelid = %s::regclass AND con.contype = 'f' "
            "ORDER BY con.conname, k.pos", (table_ref(cfg, table),))
    else:
        cur.execute(
            "SELECT constraint_name, column_name, referenced_table_schema, referenced_table_name, "
            "       referenced_column_name "
            "FROM information_schema.key_column_usage "
            "WHERE table_schema = %s AND table_name = %s AND referenced_table_name IS NOT NULL "
            "ORDER BY constraint_name, ordinal_position", (cfg["schema"], table))
    fks = {}
    for name, col, ref_schema, ref_table, ref_col in cur.fetchall():
        fk = fks.setdefault(name, {"name": name, "columns": [], "ref_schema": ref_schema,
                                   "ref_table": ref_table, "ref_columns": [],
                                   "same_schema": ref_schema == cfg["schema"]})
        fk["columns"].append(col)
        fk["ref_columns"].append(ref_col)
    return list(fks.values())


def indexes(cur, cfg, table):
    if cfg["db_type"] == "postgresql":
        cur.execute(
            "SELECT ic.relname, i.indisunique, i.indisprimary, "
            "       ARRAY(SELECT pg_get_indexdef(i.indexrelid, k, true) "
            "             FROM generate_series(1, i.indnkeyatts) AS k ORDER BY k) "
            "FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid "
            "WHERE i.indrelid = %s::regclass ORDER BY i.indisprimary DESC, ic.relname",
            (table_ref(cfg, table),))
        return [{"name": r[0], "unique": r[1], "primary": r[2], "columns": list(r[3])}
                for r in cur.fetchall()]
    cur.execute(
        "SELECT index_name, non_unique, column_name FROM information_schema.statistics "
        "WHERE table_schema = %s AND table_name = %s "
        "ORDER BY index_name = 'PRIMARY' DESC, index_name, seq_in_index", (cfg["schema"], table))
    idx = {}
    for name, non_unique, col in cur.fetchall():
        i = idx.setdefault(name, {"name": name, "unique": not non_unique,
                                  "primary": name == "PRIMARY", "columns": []})
        i["columns"].append(col or "(expression)")
    return list(idx.values())


# ---------- building queries ----------

# PostgreSQL types with no sort order (ORDER BY on them fails)
PG_UNSORTABLE = re.compile(r"^(json|xml|point|line|lseg|box|path|polygon|circle)\b")


def _default_order(cur, cfg, obj, cols):
    """A deterministic order so rows don't move between pages."""
    pk = primary_key(cur, cfg, obj["name"])
    if pk:
        return [col_ref(cfg, c) for c in pk]
    if cfg["db_type"] == "postgresql":
        if obj["kind"] == "table":
            return ["t.ctid"]  # physical row id: unique, and works for every column type
        return [col_ref(cfg, c["name"]) for c in cols if not PG_UNSORTABLE.match(c["type"])]
    return [col_ref(cfg, c["name"]) for c in cols]


def order_clause(cur, cfg, obj, cols, sort="", direction="asc"):
    exprs = _default_order(cur, cfg, obj, cols)
    if sort:
        if sort not in {c["name"] for c in cols}:
            raise ApiError(f"Unknown column '{sort}'")
        ref = col_ref(cfg, sort)
        exprs = [f"{ref} {'DESC' if direction == 'desc' else 'ASC'}"] + [e for e in exprs if e != ref]
    return " ORDER BY " + ", ".join(exprs) if exprs else ""


def _like(value):
    """Match `value` literally inside LIKE: escape the wildcards."""
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def parse_filters(raw):
    if not raw:
        return {}
    try:
        filters = json.loads(raw)
    except ValueError:
        raise ApiError("Filters must be a JSON object")
    if not isinstance(filters, dict):
        raise ApiError("Filters must be a JSON object")
    return {str(k): str(v) for k, v in filters.items() if v is not None and str(v) != ""}


def where_clause(cfg, cols, search="", filters=None):
    """Search across all columns, plus per-column filters.

    A filter value starting with '=' is an exact match; anything else is 'contains'
    (case-insensitive)."""
    pg = cfg["db_type"] == "postgresql"
    parts, params = [], []
    if search:
        if pg:
            parts.append("t::text ILIKE %s")
        else:
            parts.append("CONCAT_WS(' ', " + ", ".join(col_ref(cfg, c["name"]) for c in cols) + ") LIKE %s")
        params.append(_like(search))
    names = {c["name"] for c in cols}
    for col, value in (filters or {}).items():
        if col not in names:
            raise ApiError(f"Unknown column '{col}'")
        text = f"{col_ref(cfg, col)}::text" if pg else f"CAST({col_ref(cfg, col)} AS CHAR)"
        if value.startswith("="):
            parts.append(f"{text} = %s")
            params.append(value[1:])
        else:
            parts.append(f"{text} {'ILIKE' if pg else 'LIKE'} %s")
            params.append(_like(value))
    return (" WHERE " + " AND ".join(parts) if parts else ""), params


# ---------- server-level lists (before a connection is saved) ----------

MYSQL_SYSTEM = {"information_schema", "performance_schema", "mysql", "sys"}


def _fetch_names(conn, query):
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_databases(cfg):
    """Connect to the server (no database chosen yet) and list user databases."""
    if cfg["db_type"] == "postgresql":
        conn, last = None, None
        for name in ("postgres", "template1"):  # a maintenance DB to log in with
            try:
                conn = open_conn({**cfg, "database": name})
                break
            except ApiError as e:
                last = e
        if conn is None:
            raise last
        return _fetch_names(conn, "SELECT datname FROM pg_database "
                                  "WHERE NOT datistemplate AND datallowconn ORDER BY datname")
    names = _fetch_names(open_conn({**cfg, "database": ""}), "SHOW DATABASES")
    return [n for n in names if n.lower() not in MYSQL_SYSTEM]


def list_schemas(cfg):
    """PostgreSQL schemas the user can open. MySQL has one schema per database."""
    if cfg["db_type"] != "postgresql":
        return [cfg["database"]]
    return _fetch_names(open_conn(cfg),
                        "SELECT nspname FROM pg_namespace "
                        "WHERE nspname !~ '^pg_' AND nspname <> 'information_schema' "
                        "  AND has_schema_privilege(oid, 'USAGE') ORDER BY nspname")
