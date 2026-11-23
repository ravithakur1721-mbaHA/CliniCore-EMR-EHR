import os
import mysql.connector

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


def get_connection():
    """
    Establish a secure connection to MySQL database.
    Reads credentials from environment variables with safe defaults.
    Supports both MYSQL_* and DB_* environment variables.
    """
    host = os.environ.get("MYSQL_HOST") or os.environ.get("DB_HOST") or "localhost"
    user = os.environ.get("MYSQL_USER") or os.environ.get("DB_USER") or "root"
    password = os.environ.get("MYSQL_PASSWORD") or os.environ.get("DB_PASSWORD") or "ravi1804"
    database = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or "ehrs"
    port = int(os.environ.get("MYSQL_PORT") or os.environ.get("DB_PORT") or 3306)

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        autocommit=False,
    )


def get_table_data(table_name):
    """
    Safely query table data with whitelist validation.
    Prevents SQL injection vulnerabilities on table names.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Access denied: table '{table_name}' is not in the allowed schema.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Table name is verified against static frozen set
    query = f"SELECT * FROM `{table_name}`"
    cursor.execute(query)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return rows
