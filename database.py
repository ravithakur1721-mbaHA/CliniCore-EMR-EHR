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


import os
import time
import urllib.parse
import ssl

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from flask import g, has_app_context
except ImportError:
    has_app_context = lambda: False
    g = None

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


# ═══════════════════════════════════════════════════════════════
# High-Performance Serverless Connection Manager
# ═══════════════════════════════════════════════════════════════

class _WarmConnectionManager:
    """
    Maintains a healthy warm TLS connection across serverless invocations.
    - Reconnects proactively if idle for more than 15 seconds to prevent
      hanging on dead TCP sockets dropped by cloud NAT gateways.
    - Sets strict safety timeouts so connection attempts never block a request.
    """
    def __init__(self):
        self._raw_conn = None
        self._last_used = 0

    def get_raw_connection(self):
        now = time.time()
        # If connection is alive and was active within the last 15 seconds
        if self._raw_conn is not None and (now - self._last_used < 15):
            try:
                self._raw_conn.ping(reconnect=False)
                self._last_used = now
                return self._raw_conn
            except Exception:
                try:
                    self._raw_conn.close()
                except Exception:
                    pass
                self._raw_conn = None

        # Clean up stale connection
        if self._raw_conn is not None:
            try:
                self._raw_conn.close()
            except Exception:
                pass
            self._raw_conn = None

        # Establish fresh connection with safety timeouts
        params = get_db_params()

        try:
            import pymysql

            connect_kwargs = {
                "host": params["host"],
                "user": params["user"],
                "password": params["password"],
                "database": params["database"],
                "port": params["port"],
                "autocommit": True,
                "connect_timeout": 8,
                "read_timeout": 6,
                "write_timeout": 6,
            }

            if params["host"] not in ("localhost", "127.0.0.1") or params.get("ssl_disabled") is False:
                connect_kwargs["ssl"] = ssl.create_default_context()

            self._raw_conn = pymysql.connect(**connect_kwargs)
            self._last_used = time.time()
            return self._raw_conn
        except ImportError:
            pass

        # Fallback for local setups
        import mysql.connector
        connect_args = {
            "host": params["host"],
            "user": params["user"],
            "password": params["password"],
            "database": params["database"],
            "port": params["port"],
            "autocommit": True,
            "connection_timeout": 8,
        }
        if "ssl_disabled" in params:
            connect_args["ssl_disabled"] = params["ssl_disabled"]

        self._raw_conn = mysql.connector.connect(**connect_args)
        self._last_used = time.time()
        return self._raw_conn


_WARM_MANAGER = _WarmConnectionManager()


class RequestScopedConnection:
    """
    Wraps a database connection so that multiple queries within a single HTTP request
    reuse the active connection without re-handshaking TLS across the internet.
    When code inside the request calls conn.close(), it is treated as a no-op;
    the actual connection is managed by _WARM_MANAGER.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self, dictionary=False):
        if dictionary:
            import pymysql.cursors
            return self._conn.cursor(pymysql.cursors.DictCursor)
        return self._conn.cursor()

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def ping(self, reconnect=False):
        return self._conn.ping(reconnect=reconnect)

    def close(self):
        # Kept open for subsequent queries within this request context
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection():
    """
    Establish or reuse a secure, high-performance MySQL connection.
    - Within a single HTTP request: Reuses g._db_conn (0ms extra handshake).
    - Across warm requests: Reuses warm TCP socket if active within 15 seconds.
    - Never hangs for > 8s under any circumstance.
    """
    if has_app_context() and getattr(g, "_db_conn", None) is not None:
        return g._db_conn

    raw = _WARM_MANAGER.get_raw_connection()
    scoped = RequestScopedConnection(raw)

    if has_app_context():
        g._db_conn = scoped

    return scoped



def get_table_data(table_name):
    """
    Safely query table data with whitelist validation.
    Prevents SQL injection vulnerabilities on table names.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Access denied: table '{table_name}' is not in the allowed schema.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


    query = f"SELECT * FROM `{table_name}`"
    cursor.execute(query)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return rows
