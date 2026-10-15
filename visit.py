from database import get_connection

def add_visit():
    conn = get_connection()
    cursor = conn.cursor()

    patient_id = int(input("Patient ID: "))
    visit_date = input("Visit Date (YYYY-MM-DD): ")
    doctor = input("Doctor Name: ")

    query = """
    INSERT INTO visits (patient_id, visit_date, doctor_name)
    VALUES (%s, %s, %s)
    """
    cursor.execute(query, (patient_id, visit_date, doctor))
    conn.commit()

    cursor.close()
    conn.close()
    print("Visit added successfully.")


def add_diagnosis():
    conn = get_connection()
    cursor = conn.cursor()

    visit_id = int(input("Visit ID: "))
    disease = input("Disease Name: ")

    cursor.execute(
        "INSERT INTO diagnoses (visit_id, disease_name) VALUES (%s, %s)",
        (visit_id, disease)
    )
    conn.commit()

    cursor.close()
    conn.close()
    print("Diagnosis added.")


def add_lab():
    conn = get_connection()
    cursor = conn.cursor()

    visit_id = int(input("Visit ID: "))
    test = input("Test Name: ")
    result = input("Result: ")

    cursor.execute(
        "INSERT INTO lab_results (visit_id, test_name, result_value) VALUES (%s, %s, %s)",
        (visit_id, test, result)
    )
    conn.commit()

    cursor.close()
    conn.close()
    print("Lab result added.")


def add_medication():
    conn = get_connection()
    cursor = conn.cursor()

    visit_id = int(input("Visit ID: "))
    drug = input("Drug Name: ")
    dosage = input("Dosage: ")

    cursor.execute(
        "INSERT INTO medications (visit_id, drug_name, dosage) VALUES (%s, %s, %s)",
        (visit_id, drug, dosage)
    )
    conn.commit()

    cursor.close()
    conn.close()
    print("Medication added.")

