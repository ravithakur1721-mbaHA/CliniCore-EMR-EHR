from database import get_connection

def add_patient():
    name = input("Name: ")
    age = int(input("Age: "))
    gender = input("Gender: ")
    contact = input("Contact: ")

    if age <= 0:
        print("Invalid age")
        return

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    INSERT INTO patients (name, age, gender, contact)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (name, age, gender, contact))
    conn.commit()

    cursor.close()
    conn.close()
    print("Patient added successfully.")


def view_patients():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients")
    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()

