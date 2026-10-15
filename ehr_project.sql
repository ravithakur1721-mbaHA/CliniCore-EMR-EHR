CREATE DATABASE ehrs;
USE ehrs;

-- 🔹 STEP 2: Create Tables (VERY IMPORTANT)

CREATE TABLE patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    age INT,
    gender VARCHAR(10),
    contact VARCHAR(15)
);

-- 🏥 VISITS TABLE

CREATE TABLE visits (
    visit_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    visit_date DATE,
    doctor_name VARCHAR(100),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- 🦠 DIAGNOSES TABLE

CREATE TABLE diagnoses (
    diagnosis_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    disease_name VARCHAR(100),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- 🧪 LAB RESULTS TABLE

CREATE TABLE lab_results (
    lab_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    test_name VARCHAR(100),
    result_value VARCHAR(50),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- 💊 MEDICATIONS TABLE

CREATE TABLE medications (
    med_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    drug_name VARCHAR(100),
    dosage VARCHAR(50),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

use ehrs;
show tables;

INSERT INTO patients (name, age, gender, contact) VALUES
('Rahul Kumar', 35, 'Male', '9876543210'),
('Anita Sharma', 28, 'Female', '9123456789'),
('Amit Verma', 42, 'Male', '9988776655'),
('Neha Singh', 31, 'Female', '9012345678'),
('Ravi Patel', 50, 'Male', '9090909090'),
('Pooja Gupta', 26, 'Female', '8899776655'),
('Suresh Yadav', 45, 'Male', '9345678123'),
('Kavita Mishra', 38, 'Female', '9876501234'),
('Vikas Malhotra', 29, 'Male', '9765432109'),
('Sunita Roy', 55, 'Female', '9654321876');

INSERT INTO visits (patient_id, visit_date, doctor_name) VALUES
(1, '2025-01-05', 'Dr Sharma'),
(2, '2025-01-07', 'Dr Mehta'),
(3, '2025-01-10', 'Dr Gupta'),
(4, '2025-01-12', 'Dr Rao'),
(5, '2025-01-15', 'Dr Sharma'),
(6, '2025-01-18', 'Dr Mehta'),
(7, '2025-01-20', 'Dr Gupta'),
(8, '2025-01-22', 'Dr Rao'),
(9, '2025-01-25', 'Dr Sharma'),
(10, '2025-01-28', 'Dr Mehta');

INSERT INTO diagnoses (visit_id, disease_name) VALUES
(1, 'Hypertension'),
(2, 'Iron Deficiency Anemia'),
(3, 'Type 2 Diabetes'),
(4, 'Migraine'),
(5, 'Coronary Artery Disease'),
(6, 'Vitamin D Deficiency'),
(7, 'Chronic Bronchitis'),
(8, 'Hypothyroidism'),
(9, 'Gastritis'),
(10, 'Osteoarthritis');

INSERT INTO lab_results (visit_id, test_name, result_value) VALUES
(1, 'Blood Pressure', '150/95 mmHg'),
(2, 'Hemoglobin', '9.8 g/dL'),
(3, 'Fasting Blood Sugar', '165 mg/dL'),
(4, 'MRI Brain', 'Normal'),
(5, 'ECG', 'Abnormal'),
(6, 'Vitamin D', '14 ng/mL'),
(7, 'Chest X-Ray', 'Inflammation'),
(8, 'TSH', '8.2 µIU/mL'),
(9, 'Endoscopy', 'Gastritis'),
(10, 'X-Ray Knee', 'Joint Space Reduced');

INSERT INTO medications (visit_id, drug_name, dosage) VALUES
(1, 'Amlodipine', '5 mg OD'),
(2, 'Ferrous Sulfate', '100 mg BD'),
(3, 'Metformin', '500 mg BD'),
(4, 'Sumatriptan', '50 mg SOS'),
(5, 'Atorvastatin', '20 mg HS'),
(6, 'Cholecalciferol', '60000 IU Weekly'),
(7, 'Salbutamol', '2 puffs SOS'),
(8, 'Levothyroxine', '50 mcg OD'),
(9, 'Omeprazole', '20 mg OD'),
(10, 'Paracetamol', '650 mg TID');


SELECT * FROM patients;
SELECT * FROM visits;
SELECT * FROM diagnoses;
SELECT * FROM lab_results;
SELECT * FROM medications;
use ehrs;

SELECT 
    p.name,
    v.visit_date,
    d.disease_name,
    l.test_name,
    m.drug_name
FROM patients p
JOIN visits v ON p.patient_id = v.patient_id
JOIN diagnoses d ON v.visit_id = d.visit_id
JOIN lab_results l ON v.visit_id = l.visit_id
JOIN medications m ON v.visit_id = m.visit_id;


CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(50),
    role VARCHAR(20)
);

INSERT INTO users (username, password, role)
VALUES ('admin', 'admin123', 'Admin'),
       ('doctor', 'doc123', 'Doctor');

