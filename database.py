import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "ehrs"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
    )

def get_table_data(table_name):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT * FROM {table_name}"
    cursor.execute(query)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows
