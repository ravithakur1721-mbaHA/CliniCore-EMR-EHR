CREATE DATABASE IF NOT EXISTS ehrs;
USE ehrs;

-- 🔹 STEP 2: Create Tables (VERY IMPORTANT)

CREATE TABLE IF NOT EXISTS patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    age INT,
    gender VARCHAR(10),
    contact VARCHAR(15)
);

-- 🏥 VISITS TABLE

CREATE TABLE IF NOT EXISTS visits (
    visit_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    visit_date DATE,
    doctor_name VARCHAR(100),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- 🦠 DIAGNOSES TABLE

CREATE TABLE IF NOT EXISTS diagnoses (
    diagnosis_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    disease_name VARCHAR(100),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- 🧪 LAB RESULTS TABLE

CREATE TABLE IF NOT EXISTS lab_results (
    lab_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    test_name VARCHAR(100),
    result_value VARCHAR(50),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- 💊 MEDICATIONS TABLE

CREATE TABLE IF NOT EXISTS medications (
    med_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    drug_name VARCHAR(100),
    dosage VARCHAR(50),
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

-- 📅 FOLLOW-UPS TABLE

CREATE TABLE IF NOT EXISTS follow_ups (
    follow_up_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    scheduled_date DATE,
    follow_up_type VARCHAR(100) DEFAULT 'Routine Review',
    status VARCHAR(50) DEFAULT 'Scheduled',
    priority VARCHAR(50) DEFAULT 'Normal',
    notes TEXT,
    doctor_name VARCHAR(100),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- 🧾 BILLING INVOICES TABLE

CREATE TABLE IF NOT EXISTS billing_invoices (
    invoice_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT,
    patient_id INT,
    invoice_number VARCHAR(50) UNIQUE,
    invoice_date DATE,
    consultation_fee DECIMAL(10,2) DEFAULT 500.00,
    pharmacy_fee DECIMAL(10,2) DEFAULT 0.00,
    lab_fee DECIMAL(10,2) DEFAULT 0.00,
    tax_amount DECIMAL(10,2) DEFAULT 25.00,
    total_amount DECIMAL(10,2) DEFAULT 525.00,
    payment_status VARCHAR(50) DEFAULT 'Paid',
    payment_method VARCHAR(50) DEFAULT 'UPI',
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- 🔐 USERS TABLE (Authentication & RBAC)

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_active TINYINT(1) DEFAULT 1
);

-- Sample Data Seeding

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

INSERT INTO follow_ups (patient_id, scheduled_date, follow_up_type, status, priority, notes, doctor_name) VALUES
(1, '2025-02-10', 'Routine Review', 'Completed', 'Normal', 'Blood pressure stabilized.', 'Dr Sharma'),
(3, '2025-03-01', 'Lab Review', 'Overdue', 'High', 'Check HbA1c and fasting blood sugar.', 'Dr Gupta'),
(5, '2025-03-15', 'Cardiology Check', 'Scheduled', 'High', 'Review ECG and lipid panel.', 'Dr Sharma'),
(8, '2025-03-20', 'Endocrine Check', 'Scheduled', 'Normal', 'Monitor TSH levels and dosage.', 'Dr Rao');

INSERT INTO billing_invoices (visit_id, patient_id, invoice_number, invoice_date, consultation_fee, pharmacy_fee, lab_fee, tax_amount, total_amount, payment_status, payment_method) VALUES
(1, 1, 'INV-000001', '2025-01-05', 500.00, 150.00, 200.00, 42.50, 892.50, 'Paid', 'UPI'),
(2, 2, 'INV-000002', '2025-01-07', 500.00, 120.00, 350.00, 48.50, 1018.50, 'Paid', 'Cash'),
(3, 3, 'INV-000003', '2025-01-10', 500.00, 240.00, 180.00, 46.00, 966.00, 'Paid', 'Card');

INSERT INTO users (username, password, role) VALUES
('admin', 'admin123', 'Admin'),
('doctor', 'doc123', 'Doctor'),
('nurse', 'nurse123', 'Nurse');

