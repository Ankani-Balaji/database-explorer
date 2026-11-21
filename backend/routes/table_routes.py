import csv
import datetime
import decimal
import io
import json
from urllib.parse import quote as url_quote
import psycopg2
import pymysql
from flask import Blueprint, Response, jsonify, request
from db_manager import (ApiError, get_cfg, pooled_conn, list_objects, find_object, table_columns,
                        primary_key, foreign_keys, indexes, table_ref, where_clause, order_clause,
                        parse_filters, is_timeout, timeout_error)

bp = Blueprint("tables", __name__, url_prefix="/api")

JS_SAFE_INT = 2**53 - 1  # larger integers lose precision as JavaScript numbers
EXPORT_MAX_ROWS = 50_000
# Unfiltered tables with more rows than this (by the database's statistics) show an estimated
# total instead of running COUNT(*), which reads the whole table
ESTIMATE_COUNT_ABOVE = 100_000


def js_safe(v):
    if isinstance(v, int) and not isinstance(v, bool) and abs(v) > JS_SAFE_INT:
        return str(v)
    return v


def with_conn(fn):
    cfg = get_cfg(request.headers.get("X-Connection-Id"))
    try:
        with pooled_conn(cfg) as conn, conn.cursor() as cur:
            return fn(cur, cfg)
    except (psycopg2.Error, pymysql.MySQLError) as e:
        if is_timeout(e):
            raise timeout_error() from e
        # e.g. sorting by a column type the database can't sort
        raise ApiError("Database error: " + str(e).strip()[:600]) from e


def with_table(table_name, fn):
    def run(cur, cfg):
        # Validate against the real table list before building any SQL
        obj = find_object(cur, cfg, table_name)
        if not obj:
            raise ApiError(f"Table '{table_name}' not found in '{cfg['schema']}'", 404)
        return fn(cur, cfg, obj)
    return with_conn(run)


def query_parts(cur, cfg, obj, with_order=True):
    """Columns, WHERE and ORDER BY from the request's search / filters / sort parameters."""
    cols = table_columns(cur, cfg, obj["name"])
    w, p = where_clause(cfg, cols, request.args.get("search", "").strip(),
                        parse_filters(request.args.get("filters")))
    o = order_clause(cur, cfg, obj, cols, request.args.get("sort", ""),
                     request.args.get("dir", "asc")) if with_order else ""
    return w, p, o


@bp.get("/tables")
def tables():
    def run(cur, cfg):
        objects = list_objects(cur, cfg)
        return jsonify(success=True, db_type=cfg["db_type"], database=cfg["database"],
                       schema=cfg["schema"], count=len(objects), tables=objects)
    return with_conn(run)


@bp.get("/tables/<table_name>/schema")
def schema(table_name):
    def run(cur, cfg, obj):
        pk = primary_key(cur, cfg, table_name)
        fks = foreign_keys(cur, cfg, table_name)
        fk_cols = {c for fk in fks for c in fk["columns"]}
        cols = [{**c, "primary_key": c["name"] in pk, "foreign_key": c["name"] in fk_cols}
                for c in table_columns(cur, cfg, table_name)]
        return jsonify(success=True, table=table_name, kind=obj["kind"], columns=cols,
                       primary_key=pk, foreign_keys=fks, indexes=indexes(cur, cfg, table_name))
    return with_table(table_name, run)


@bp.get("/tables/<table_name>/count")
def count(table_name):
    def run(cur, cfg, obj):
        w, p, _ = query_parts(cur, cfg, obj, with_order=False)
        cur.execute(f"SELECT COUNT(*) FROM {table_ref(cfg, table_name)} t{w}", p)
        return jsonify(success=True, table=table_name, count=cur.fetchone()[0])
    return with_table(table_name, run)


@bp.get("/tables/<table_name>/data")
def data(table_name):
    page = max(request.args.get("page", 1, type=int), 1)
    limit = min(max(request.args.get("limit", 25, type=int), 1), 500)

    def run(cur, cfg, obj):
        ref = table_ref(cfg, table_name)
        w, p, o = query_parts(cur, cfg, obj)
        estimate = obj["rows_estimate"]
        estimated = (not w and obj["kind"] == "table" and estimate is not None
                     and estimate > ESTIMATE_COUNT_ABOVE)
        if estimated:
            total = int(estimate)
        else:
            cur.execute(f"SELECT COUNT(*) FROM {ref} t{w}", p)
            total = cur.fetchone()[0]
        cur.execute(f"SELECT t.* FROM {ref} t{w}{o} LIMIT %s OFFSET %s",
                    p + [limit, (page - 1) * limit])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, map(js_safe, r))) for r in cur.fetchall()]
        return jsonify(success=True, table=table_name, columns=cols, rows=rows,
                       total=total, total_estimated=estimated, page=page, limit=limit,
                       total_pages=max((total + limit - 1) // limit, 1))
    return with_table(table_name, run)


def csv_value(v):
    if v is None:
        return ""
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "\\x" + bytes(v).hex()
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str, ensure_ascii=False)
    if isinstance(v, decimal.Decimal):
        return str(v)
    return v


@bp.get("/tables/<table_name>/export")
def export(table_name):
    """CSV of the rows matching the current search, filters and sort (up to EXPORT_MAX_ROWS)."""
    def run(cur, cfg, obj):
        w, p, o = query_parts(cur, cfg, obj)
        cur.execute(f"SELECT t.* FROM {table_ref(cfg, table_name)} t{w}{o} LIMIT %s",
                    p + [EXPORT_MAX_ROWS + 1])
        rows = cur.fetchall()
        truncated = len(rows) > EXPORT_MAX_ROWS
        out = io.StringIO()
        out.write("﻿")  # BOM so Excel reads the file as UTF-8
        writer = csv.writer(out)
        writer.writerow(d[0] for d in cur.description)
        for r in rows[:EXPORT_MAX_ROWS]:
            writer.writerow(csv_value(v) for v in r)
        return Response(out.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{url_quote(table_name)}.csv",
            "X-Export-Truncated": "1" if truncated else "0",
            "X-Export-Rows": str(min(len(rows), EXPORT_MAX_ROWS)),
        })
    return with_table(table_name, run)
