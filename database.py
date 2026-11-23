import os
import urllib.parse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Allowed database tables for dynamic lookups (strictly whitelisted against SQL injection)
ALLOWED_TABLES = frozenset({
    "patients",
    "visits",
    "diagnoses",
    "lab_results",
    "medications",
    "follow_ups",
    "billing_invoices",
    "users",
})


def get_db_params():
    """
    Parse database connection parameters from environment.
    Supports standard cloud DATABASE_URL / MYSQL_URL connection strings
    as well as individual environment variables (MYSQL_* or DB_*).
    """
    raw_url = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")
    if raw_url:
        p = urllib.parse.urlparse(raw_url)
        params = {
            "host": p.hostname or "localhost",
            "user": p.username or "root",
            "password": p.password or "",
            "database": p.path.lstrip("/") or "ehrs",
            "port": p.port or 3306,
        }
        # Detect cloud SSL parameters in connection string
        query = p.query.lower()
        if "ssl" in query or "require" in query:
            params["ssl_disabled"] = False
        return params

    return {
        "host": os.environ.get("MYSQL_HOST") or os.environ.get("DB_HOST") or "localhost",
        "user": os.environ.get("MYSQL_USER") or os.environ.get("DB_USER") or "root",
        "password": os.environ.get("MYSQL_PASSWORD") or os.environ.get("DB_PASSWORD") or "ravi1804",
        "database": os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or "ehrs",
        "port": int(os.environ.get("MYSQL_PORT") or os.environ.get("DB_PORT") or 3306),
    }


_POOL_CONN = None


def get_connection():
    """
    Establish a secure, high-performance MySQL connection.
    Primary driver: pymysql with serverless persistent connection reuse and TLS encryption.
    Fallback driver: mysql.connector.
    """
    global _POOL_CONN

    # Reuse persistent warm connection in serverless container if alive
    if _POOL_CONN is not None:
        try:
            _POOL_CONN.ping(reconnect=True)
            return _POOL_CONN
        except Exception:
            _POOL_CONN = None

    params = get_db_params()

    # Attempt 1: pymysql (lightweight, pure Python, pooled & TLS compliant)
    try:
        import pymysql
        import pymysql.cursors

        class PyMySQLWrapper:
            """Wrapper providing interface parity with mysql.connector and warm socket persistence."""
            def __init__(self, raw_conn, is_pooled=False):
                self._conn = raw_conn
                self._is_pooled = is_pooled

            def cursor(self, dictionary=False):
                if dictionary:
                    return self._conn.cursor(pymysql.cursors.DictCursor)
                return self._conn.cursor()

            def commit(self):
                return self._conn.commit()

            def rollback(self):
                return self._conn.rollback()

            def ping(self, reconnect=True):
                return self._conn.ping(reconnect=reconnect)

            def close(self):
                # In serverless, keep the underlying TCP/TLS connection alive across requests
                if not self._is_pooled:
                    try:
                        self._conn.close()
                    except Exception:
                        pass

            def __getattr__(self, name):
                return getattr(self._conn, name)

        connect_kwargs = {
            "host": params["host"],
            "user": params["user"],
            "password": params["password"],
            "database": params["database"],
            "port": params["port"],
            "autocommit": True,
            "connect_timeout": 10,
        }
        # Enable TLS/SSL for cloud database (e.g. TiDB, Supabase, PlanetScale, Aiven)
        if params["host"] not in ("localhost", "127.0.0.1") or params.get("ssl_disabled") is False:
            import ssl
            connect_kwargs["ssl"] = ssl.create_default_context()

        raw = pymysql.connect(**connect_kwargs)
        _POOL_CONN = PyMySQLWrapper(raw, is_pooled=True)
        return _POOL_CONN
    except ImportError:
        pass
    except Exception:
        pass

    # Attempt 2: mysql.connector fallback
    try:
        import mysql.connector
        connect_args = {
            "host": params["host"],
            "user": params["user"],
            "password": params["password"],
            "database": params["database"],
            "port": params["port"],
            "autocommit": True,
            "connection_timeout": 10,
        }
        if "ssl_disabled" in params:
            connect_args["ssl_disabled"] = params["ssl_disabled"]

        return mysql.connector.connect(**connect_args)
    except ImportError:
        pass

    # If both failed, re-attempt pymysql to bubble the specific connection error
    import pymysql
    connect_kwargs = {
        "host": params["host"],
        "user": params["user"],
        "password": params["password"],
        "database": params["database"],
        "port": params["port"],
        "autocommit": True,
        "connect_timeout": 10,
    }
    if params["host"] not in ("localhost", "127.0.0.1") or params.get("ssl_disabled") is False:
        import ssl
        connect_kwargs["ssl"] = ssl.create_default_context()
    raw = pymysql.connect(**connect_kwargs)
    _POOL_CONN = PyMySQLWrapper(raw, is_pooled=True)
    return _POOL_CONN


def get_table_data(table_name):
    """
    Safely query table data with whitelist validation.
    Prevents SQL injection vulnerabilities on table names.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Access denied: table '{table_name}' is not in the allowed schema.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT * FROM `{table_name}`"
    cursor.execute(query)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return rows
