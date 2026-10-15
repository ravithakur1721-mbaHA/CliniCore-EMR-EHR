from patient import add_patient, view_patients
from visit import add_visit, add_diagnosis, add_lab, add_medication
from analytics import total_patients, common_disease, view_full_ehr, gender_distribution, average_age

while True:
    print("""
    ===== EHR SYSTEM MENU =====
    1. Add Patient
    2. View Patients
    3. Add Visit
    4. Add Diagnosis
    5. Add Lab Result
    6. Add Medication
    7. Analytics
    8. View Full EHR Record
    0. Exit
    """)

    choice = input("Enter your choice: ")

    if choice == "1":
        add_patient()

    elif choice == "2":
        view_patients()

    elif choice == "3":
        add_visit()

    elif choice == "4":
        add_diagnosis()

    elif choice == "5":
        add_lab()

    elif choice == "6":
        add_medication()

    elif choice == "7":
        total_patients()
        common_disease()
        gender_distribution()
        average_age()

    elif choice == "8":
        view_full_ehr()

    elif choice == "0":
        print("Exiting EHR System.")
        break

    else:
        print("Invalid choice. Please try again.")
