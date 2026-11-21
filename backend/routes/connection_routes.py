import psycopg2
import pymysql
from flask import Blueprint, jsonify, request
from db_manager import (ApiError, validate, open_conn, list_tables, list_databases, list_schemas,
                        add_connection, get_cfg, remove_connection, public_info)
from sql_console import run_query

bp = Blueprint("connection", __name__, url_prefix="/api")
HDR = "X-Connection-Id"


@bp.post("/databases")
def databases():
    cfg = validate(request.get_json(silent=True) or {}, need_db=False)
    return jsonify(success=True, databases=list_databases(cfg))


@bp.post("/schemas")
def schemas_before_connect():
    """Schemas of a database chosen on the connect form (not saved yet)."""
    cfg = validate(request.get_json(silent=True) or {})
    return jsonify(success=True, schemas=list_schemas(cfg))


@bp.get("/schemas")
def schemas():
    return jsonify(success=True, schemas=list_schemas(get_cfg(request.headers.get(HDR))))


@bp.post("/connect")
def connect():
    cfg = validate(request.get_json(silent=True) or {})
    conn = open_conn(cfg)  # raises ApiError if it fails
    try:
        with conn.cursor() as cur:
            n = len(list_tables(cur, cfg))
    except (psycopg2.Error, pymysql.MySQLError) as e:
        raise ApiError("Connected, but couldn't read the table list: " + str(e).strip()[:400]) from e
    finally:
        conn.close()
    cid = add_connection(cfg)
    return jsonify(success=True, connection_id=cid, info=public_info(cfg, n))


@bp.get("/connection")
def connection():
    return jsonify(success=True, info=public_info(get_cfg(request.headers.get(HDR))))


@bp.post("/connection/schema")
def switch_schema():
    cfg = get_cfg(request.headers.get(HDR))
    schema = str((request.get_json(silent=True) or {}).get("schema") or "").strip()
    if cfg["db_type"] != "postgresql":
        raise ApiError("Only PostgreSQL databases have schemas to switch between")
    if schema not in list_schemas(cfg):
        raise ApiError(f"Schema '{schema}' not found or not accessible", 404)
    cfg["schema"] = schema
    return jsonify(success=True, info=public_info(cfg))


@bp.post("/disconnect")
def disconnect():
    remove_connection(request.headers.get(HDR))
    return jsonify(success=True)


@bp.post("/query")
def query():
    """Read-only SQL console (see sql_console.py for how writes are blocked)."""
    cfg = get_cfg(request.headers.get(HDR))
    sql = str((request.get_json(silent=True) or {}).get("sql") or "")
    return jsonify(success=True, **run_query(cfg, sql))
