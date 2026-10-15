from database import get_connection

def total_patients():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM patients")
    print("Total Patients:", cursor.fetchone()[0])

    cursor.close()
    conn.close()


def common_disease():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT disease_name, COUNT(*) 
        FROM diagnoses 
        GROUP BY disease_name 
        ORDER BY COUNT(*) DESC
    """)

    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()


def view_full_ehr():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.patient_id,
            p.name,
            v.visit_date,
            d.disease_name,
            l.test_name,
            m.drug_name
        FROM patients p
        JOIN visits v ON p.patient_id = v.patient_id
        JOIN diagnoses d ON v.visit_id = d.visit_id
        JOIN lab_results l ON v.visit_id = l.visit_id
        JOIN medications m ON v.visit_id = m.visit_id
    """)

    records = cursor.fetchall()

    print("\n===== FULL EHR RECORD =====")
    for r in records:
        print(f"""
Patient ID   : {r['patient_id']}
Name         : {r['name']}
Visit Date   : {r['visit_date']}
Diagnosis    : {r['disease_name']}
Lab Test     : {r['test_name']}
Medication   : {r['drug_name']}
------------------------------
""")

    cursor.close()
    conn.close()


def gender_distribution():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT gender, COUNT(*) FROM patients GROUP BY gender")
    print("\nGender Distribution:")
    for row in cursor.fetchall():
        print(row)

    cursor.close()
    conn.close()


def average_age():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT AVG(age) FROM patients")
    print("Average Patient Age:", round(cursor.fetchone()[0], 2))

    cursor.close()
    conn.close()
