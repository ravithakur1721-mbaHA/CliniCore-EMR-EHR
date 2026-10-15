import random
from datetime import datetime, timedelta
from database import get_connection

# Comprehensive Indian & International names
FIRST_NAMES_MALE = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Shaurya", "Atharv", "Dhruv", "Kabir", "Rohan", "Rahul", "Amit", "Vikram", "Suresh", "Ramesh",
    "Anand", "Rajesh", "Pradeep", "Manoj", "Sanjay", "Deepak", "Sunil", "Karan", "Alok", "Naveen",
    "Gaurav", "Manish", "Varun", "Abhishek", "Harish", "Ashok", "Kishore", "Ajay", "Dev", "Raghav",
    "Sameer", "Nitin", "Tarun", "Praveen", "Kunal", "Rakesh", "Sachin", "Mohan", "Gopal", "Dinesh",
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"
]

FIRST_NAMES_FEMALE = [
    "Aadhya", "Ananya", "Diya", "Saanvi", "Ira", "Pari", "Anushka", "Navya", "Angel", "Myra",
    "Sneha", "Pooja", "Priya", "Anjali", "Riya", "Kavita", "Sunita", "Anita", "Geeta", "Rekha",
    "Deepika", "Shweta", "Meera", "Swati", "Neha", "Divya", "Preeti", "Kiran", "Nisha", "Ritu",
    "Seema", "Suman", "Vandana", "Rashmi", "Usha", "Mamta", "Sarita", "Bhavna", "Asha", "Lakshmi",
    "Sonal", "Pallavi", "Shilpa", "Payal", "Archana", "Madhu", "Jyoti", "Manju", "Komal", "Tanvi",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Singh", "Kumar", "Mishra", "Joshi", "Yadav", "Trivedi",
    "Deshmukh", "Kulkarni", "Nair", "Pillai", "Reddy", "Rao", "Choudhury", "Bose", "Chatterjee", "Banerjee",
    "Iyer", "Iyengar", "Menon", "Bhat", "Hegde", "Shetty", "Malhotra", "Kapoor", "Khanna", "Bhatia",
    "Mehta", "Shah", "Pandey", "Dubey", "Tiwari", "Shukla", "Agrawal", "Saxena", "Srivastava", "Mathur",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Garcia", "Rodriguez", "Wilson"
]

DOCTORS = [
    ("Dr. Rajesh Gupta", "Cardiology"),
    ("Dr. Sunita Mehta", "Internal Medicine"),
    ("Dr. Vikram Rao", "Endocrinology"),
    ("Dr. Priya Nair", "Pulmonology"),
    ("Dr. Anita Deshmukh", "Neurology"),
    ("Dr. Amit Verma", "General Practice"),
    ("Dr. Shalini Kapoor", "Nephrology"),
    ("Dr. Arvind Menon", "Gastroenterology"),
    ("Dr. Deepa Iyer", "Rheumatology"),
    ("Dr. Harish Patel", "Infectious Diseases"),
    ("Dr. Meenakshi Sundaram", "Oncology"),
    ("Dr. Sanjay Kulkarni", "Orthopedics")
]

# Clinical scenarios mapping disease -> typical labs, typical meds, and typical follow up reason
CLINICAL_PROFILES = [
    {
        "disease": "Type 2 Diabetes Mellitus",
        "labs": [
            ("HbA1c", lambda: f"{random.uniform(6.5, 11.2):.1f} %"),
            ("Fasting Blood Sugar", lambda: f"{random.randint(126, 260)} mg/dL"),
            ("Post Prandial Glucose", lambda: f"{random.randint(180, 340)} mg/dL"),
            ("Serum Creatinine", lambda: f"{random.uniform(0.7, 1.4):.2f} mg/dL")
        ],
        "meds": [
            ("Metformin 500mg", "1 Tab BD with Meals"),
            ("Glimepiride 2mg", "1 Tab OD before Breakfast"),
            ("Sitagliptin 100mg", "1 Tab OD"),
            ("Empagliflozin 10mg", "1 Tab OD morning"),
            ("Insulin Glargine 10 IU", "1 Dose SubQ HS")
        ],
        "fu_type": "HbA1c Monitoring",
        "fu_notes": "Review repeat 3-month HbA1c, fasting lipids, and diabetic foot check.",
        "fu_interval_days": (60, 90)
    },
    {
        "disease": "Essential Hypertension",
        "labs": [
            ("Blood Pressure", lambda: f"{random.randint(140, 185)}/{random.randint(90, 115)} mmHg"),
            ("Serum Potassium", lambda: f"{random.uniform(3.5, 5.1):.1f} mEq/L"),
            ("Serum Creatinine", lambda: f"{random.uniform(0.8, 1.3):.2f} mg/dL"),
            ("Lipid Profile (Total Chol)", lambda: f"{random.randint(180, 260)} mg/dL")
        ],
        "meds": [
            ("Amlodipine 5mg", "1 Tab OD morning"),
            ("Telmisartan 40mg", "1 Tab OD morning"),
            ("Hydrochlorothiazide 12.5mg", "1 Tab OD morning"),
            ("Metoprolol Succinate 25mg", "1 Tab OD"),
            ("Losartan 50mg", "1 Tab OD")
        ],
        "fu_type": "BP Check & Titration",
        "fu_notes": "Evaluate home BP log, ambulatory pressure monitoring, and renal function.",
        "fu_interval_days": (14, 45)
    },
    {
        "disease": "Bronchial Asthma",
        "labs": [
            ("Peak Expiratory Flow (PEFR)", lambda: f"{random.randint(280, 480)} L/min"),
            ("Spirometry FEV1/FVC", lambda: f"{random.uniform(60, 75):.1f} %"),
            ("Absolute Eosinophil Count", lambda: f"{random.randint(350, 950)} cells/mcL")
        ],
        "meds": [
            ("Budesonide + Formoterol Inhaler (200/6)", "2 Puffs BD with Spacer"),
            ("Montelukast 10mg", "1 Tab OD at Bedtime"),
            ("Levosalbutamol Inhaler (50mcg)", "2 Puffs SOS for Wheezing"),
            ("Fluticasone Nasal Spray", "1 Spray each nostril OD")
        ],
        "fu_type": "Pulmonary Review",
        "fu_notes": "Assess inhaler technique, ACT score, and nocturnal asthma control.",
        "fu_interval_days": (30, 60)
    },
    {
        "disease": "Dyslipidemia & Atherosclerosis",
        "labs": [
            ("Total Cholesterol", lambda: f"{random.randint(220, 310)} mg/dL"),
            ("LDL Cholesterol", lambda: f"{random.randint(140, 210)} mg/dL"),
            ("Triglycerides", lambda: f"{random.randint(180, 380)} mg/dL"),
            ("HDL Cholesterol", lambda: f"{random.randint(30, 42)} mg/dL")
        ],
        "meds": [
            ("Atorvastatin 20mg", "1 Tab HS at Night"),
            ("Rosuvastatin 10mg", "1 Tab HS at Night"),
            ("Fenofibrate 145mg", "1 Tab OD with dinner"),
            ("Ezetimibe 10mg", "1 Tab OD morning")
        ],
        "fu_type": "Lipid Re-evaluation",
        "fu_notes": "Check repeat fasting lipid profile after 6-8 weeks statin therapy.",
        "fu_interval_days": (45, 75)
    },
    {
        "disease": "Acute Bacterial Pharyngitis",
        "labs": [
            ("Complete Blood Count (WBC)", lambda: f"{random.randint(11000, 16500)} /mcL"),
            ("C-Reactive Protein (CRP)", lambda: f"{random.uniform(18.0, 52.0):.1f} mg/L"),
            ("Throat Swab Rapid Antigen", lambda: "Positive Group A Strep")
        ],
        "meds": [
            ("Amoxicillin + Clavulanic Acid 625mg", "1 Tab BD x 7 Days"),
            ("Paracetamol 650mg", "1 Tab TID SOS fever/pain"),
            ("Chlorhexidine Gargle 0.2%", "15 ml TID warm rinse"),
            ("Cetirizine 10mg", "1 Tab HS x 5 Days")
        ],
        "fu_type": "Infection Resolution",
        "fu_notes": "Confirm symptom resolution and fever clearance post-antibiotic cycle.",
        "fu_interval_days": (7, 10)
    },
    {
        "disease": "Gastroesophageal Reflux Disease (GERD)",
        "labs": [
            ("H. Pylori Stool Antigen", lambda: random.choice(["Negative", "Non-reactive", "Equivocal"])),
            ("Hemoglobin", lambda: f"{random.uniform(12.5, 15.5):.1f} g/dL"),
            ("Serum Ferritin", lambda: f"{random.randint(45, 180)} ng/mL")
        ],
        "meds": [
            ("Pantoprazole 40mg", "1 Tab OD 30 min before Breakfast"),
            ("Domperidone + Esomeprazole", "1 Cap OD morning empty stomach"),
            ("Sucralfate Suspension", "10 ml TID after meals"),
            ("Antacid Gel with Simethicone", "10 ml SOS heartburn")
        ],
        "fu_type": "GI Review",
        "fu_notes": "Assess heartburn severity, dietary modification response, consider endoscopy if unresolved.",
        "fu_interval_days": (21, 45)
    },
    {
        "disease": "Hypothyroidism (Primary)",
        "labs": [
            ("TSH (Thyroid Stimulating Hormone)", lambda: f"{random.uniform(6.8, 18.5):.2f} uIU/mL"),
            ("Free T4", lambda: f"{random.uniform(0.5, 0.85):.2f} ng/dL"),
            ("Anti-TPO Antibodies", lambda: f"{random.randint(85, 340)} IU/mL")
        ],
        "meds": [
            ("Levothyroxine Sodium 50mcg", "1 Tab OD Empty Stomach early morning"),
            ("Levothyroxine Sodium 75mcg", "1 Tab OD Empty Stomach early morning"),
            ("Calcium Citrate + Vitamin D3", "1 Tab OD with lunch (separate from thyroxine)")
        ],
        "fu_type": "Thyroid Titration",
        "fu_notes": "Repeat fasting TSH after 6 weeks on current levothyroxine dosage.",
        "fu_interval_days": (42, 60)
    },
    {
        "disease": "Osteoarthritis (Bilateral Knees)",
        "labs": [
            ("ESR (Westergren)", lambda: f"{random.randint(22, 45)} mm/hr"),
            ("Serum Uric Acid", lambda: f"{random.uniform(4.0, 6.2):.1f} mg/dL"),
            ("Rheumatoid Factor (RF)", lambda: "Negative (< 14 IU/mL)")
        ],
        "meds": [
            ("Aceclofenac + Paracetamol (100/325)", "1 Tab BD SOS pain after food"),
            ("Diacerein + Glucosamine", "1 Tab OD morning"),
            ("Topical Diclofenac Gel 1.16%", "Apply gently to both knees TID"),
            ("Calcium + Vitamin D3 Tablet", "1 Tab OD")
        ],
        "fu_type": "Joint Mobility Check",
        "fu_notes": "Evaluate pain scale (VAS score), functional mobility, physical therapy compliance.",
        "fu_interval_days": (30, 60)
    },
    {
        "disease": "Iron Deficiency Anemia",
        "labs": [
            ("Hemoglobin (Hb)", lambda: f"{random.uniform(7.5, 10.2):.1f} g/dL"),
            ("Serum Ferritin", lambda: f"{random.randint(6, 18)} ng/mL"),
            ("Total Iron Binding Capacity (TIBC)", lambda: f"{random.randint(380, 490)} mcg/dL"),
            ("Peripheral Smear", lambda: "Microcytic Hypochromic")
        ],
        "meds": [
            ("Ferrous Ascorbate + Folic Acid", "1 Tab BD after meals"),
            ("Vitamin C 500mg", "1 Tab OD with iron for absorption"),
            ("Deworming Albendazole 400mg", "1 Tab Stat")
        ],
        "fu_type": "Hemoglobin Recheck",
        "fu_notes": "Repeat CBC and reticulocyte count after 30 days of oral iron therapy.",
        "fu_interval_days": (28, 42)
    },
    {
        "disease": "Chronic Kidney Disease - Stage 3",
        "labs": [
            ("Estimated GFR (eGFR)", lambda: f"{random.randint(35, 54)} mL/min/1.73m2"),
            ("Serum Creatinine", lambda: f"{random.uniform(1.8, 2.6):.2f} mg/dL"),
            ("Blood Urea Nitrogen (BUN)", lambda: f"{random.randint(32, 58)} mg/dL"),
            ("Urine Albumin/Creatinine Ratio", lambda: f"{random.randint(120, 380)} mg/g")
        ],
        "meds": [
            ("Torsemide 10mg", "1 Tab OD morning"),
            ("Sodium Bicarbonate 500mg", "1 Tab BD"),
            ("Calcitriol 0.25mcg", "1 Cap OD"),
            ("Telmisartan 20mg", "1 Tab OD (Renoprotection monitored)")
        ],
        "fu_type": "Renal Panel Review",
        "fu_notes": "Strict monitoring of serum K+, Cr, proteinuria and dietary protein restriction.",
        "fu_interval_days": (21, 45)
    },
    {
        "disease": "Major Depressive Disorder",
        "labs": [
            ("Vitamin B12", lambda: f"{random.randint(140, 220)} pg/mL"),
            ("Vitamin D3 (25-OH)", lambda: f"{random.uniform(12.0, 22.0):.1f} ng/mL"),
            ("Serum TSH", lambda: f"{random.uniform(1.2, 3.4):.2f} uIU/mL")
        ],
        "meds": [
            ("Escitalopram 10mg", "1 Tab OD morning"),
            ("Clonazepam 0.25mg", "1 Tab SOS bedtime x 7 days only"),
            ("Cholecalciferol 60,000 IU", "1 Sachet weekly x 8 weeks"),
            ("Methylcobalamin 1500mcg", "1 Tab OD")
        ],
        "fu_type": "Psychiatric Evaluation",
        "fu_notes": "Assess PHQ-9 depression score, sleep cycle, appetite, medication tolerability.",
        "fu_interval_days": (14, 28)
    },
    {
        "disease": "Urinary Tract Infection (UTI)",
        "labs": [
            ("Urine Routine (Pus Cells)", lambda: f"{random.randint(25, 60)} /hpf"),
            ("Urine Culture & Sensitivity", lambda: "E. Coli > 10^5 CFU/mL"),
            ("Urine Nitrite", lambda: "Positive")
        ],
        "meds": [
            ("Nitrofurantoin 100mg SR", "1 Tab BD x 7 Days with meals"),
            ("Phenazopyridine 200mg", "1 Tab TID x 2 Days (urinary analgesic)"),
            ("Disodium Hydrogen Citrate Syrup", "2 Tsp TID in glass of water")
        ],
        "fu_type": "Urine Culture Clearance",
        "fu_notes": "Repeat urine routine microscopy if dysuria persists; ensure hydration.",
        "fu_interval_days": (7, 14)
    }
]

def generate_patients(target_count=1000):
    print(f"Connecting to database to seed {target_count} patients with complete clinical history...")
    conn = get_connection()
    cur = conn.cursor()

    base_date = datetime.now()

    # Generate phone numbers sequentially or randomly
    used_phones = set()

    for idx in range(1, target_count + 1):
        is_female = random.random() < 0.48
        gender = "Female" if is_female else "Male"
        first_name = random.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        age = random.choices(
            population=[random.randint(18, 30), random.randint(31, 50), random.randint(51, 75), random.randint(76, 90)],
            weights=[20, 35, 35, 10]
        )[0]

        # Generate realistic 10-digit phone number
        while True:
            contact = f"{random.choice(['9', '8', '7', '6'])}{random.randint(100000000, 999999999)}"
            if contact not in used_phones:
                used_phones.add(contact)
                break

        # 1. Insert patient
        cur.execute(
            "INSERT INTO patients (name, age, gender, contact) VALUES (%s, %s, %s, %s)",
            (name, age, gender, contact)
        )
        patient_id = cur.lastrowid

        # Pick 1-3 clinical profiles for realistic co-morbidities (e.g. Diabetes + Hypertension)
        num_conditions = random.choices([1, 2, 3], weights=[60, 32, 8])[0]
        profiles = random.sample(CLINICAL_PROFILES, num_conditions)

        # Generate 1 to 3 visits across past 180 days
        num_visits = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
        
        # Pick a primary doctor
        doctor_name, specialty = random.choice(DOCTORS)

        for v_i in range(num_visits):
            # Days in the past
            days_ago = (num_visits - v_i) * random.randint(15, 60)
            visit_date = (base_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            cur.execute(
                "INSERT INTO visits (patient_id, visit_date, doctor_name) VALUES (%s, %s, %s)",
                (patient_id, visit_date, doctor_name)
            )
            visit_id = cur.lastrowid

            # For each profile, add diagnoses, labs, and medications
            for prof in profiles:
                cur.execute(
                    "INSERT INTO diagnoses (visit_id, disease_name) VALUES (%s, %s)",
                    (visit_id, prof["disease"])
                )

                # Pick 1 or 2 labs from profile
                selected_labs = random.sample(prof["labs"], min(len(prof["labs"]), random.choice([1, 2])))
                for test_name, result_fn in selected_labs:
                    cur.execute(
                        "INSERT INTO lab_results (visit_id, test_name, result_value) VALUES (%s, %s, %s)",
                        (visit_id, test_name, result_fn())
                    )

                # Pick 1 to 3 meds from profile
                num_meds = min(len(prof["meds"]), random.choice([1, 2, 3]))
                selected_meds = random.sample(prof["meds"], num_meds)
                for drug_name, dosage in selected_meds:
                    cur.execute(
                        "INSERT INTO medications (visit_id, drug_name, dosage) VALUES (%s, %s, %s)",
                        (visit_id, drug_name, dosage)
                    )

            # Generate follow-up for the most recent visit
            if v_i == num_visits - 1:
                lead_prof = profiles[0]
                min_days, max_days = lead_prof["fu_interval_days"]
                interval = random.randint(min_days, max_days)
                fu_date_dt = (base_date - timedelta(days=days_ago)) + timedelta(days=interval)
                fu_date = fu_date_dt.strftime("%Y-%m-%d")

                # Status based on date comparison with today
                if fu_date_dt < base_date:
                    # Date in past
                    status = random.choices(["Completed", "Overdue", "Cancelled"], weights=[65, 30, 5])[0]
                else:
                    status = "Scheduled"

                priority = random.choices(["Normal", "High", "Urgent"], weights=[70, 24, 6])[0]

                cur.execute("""
                    INSERT INTO follow_ups 
                    (patient_id, visit_id, scheduled_date, follow_up_type, status, priority, notes, doctor_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    patient_id,
                    visit_id,
                    fu_date,
                    lead_prof["fu_type"],
                    status,
                    priority,
                    lead_prof["fu_notes"],
                    doctor_name
                ))

        if idx % 100 == 0:
            conn.commit()
            print(f"Generated {idx}/{target_count} patients with records...")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully generated {target_count} patients with complete EMR records!")

if __name__ == "__main__":
    generate_patients(1000)
