import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="ravi1804",   # keep your actual password
        database="ehrs"
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
