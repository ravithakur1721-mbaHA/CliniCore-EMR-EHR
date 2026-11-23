# 🏥 CliniCore EHR/EMR Portal

> **A full-featured, web-based Electronic Health Records (EHR) and Electronic Medical Records (EMR) management system for hospitals and clinics.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-lightgrey?logo=flask)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-blue?logo=mysql)](https://www.mysql.com/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Database Setup](#database-setup)
  - [Running the App](#running-the-app)
- [User Roles & Permissions](#user-roles--permissions)
- [Modules](#modules)
- [WhatsApp Integration](#whatsapp-integration)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Default Credentials](#default-credentials)
- [FAQ](#faq)

---

## Overview

**CliniCore EHR/EMR Portal** is a web-based clinical management platform built with **Python (Flask)** and **MySQL**. It allows medical staff to manage the full patient lifecycle — from registration and clinical visits to prescriptions, lab results, billing, and follow-up care — all in one unified system.

The portal enforces **Role-Based Access Control (RBAC)** across three distinct roles: **Admin**, **Doctor**, and **Nurse**, ensuring clinical data governance and least-privilege access.

**Application URL (default):** `http://127.0.0.1:5000` or `http://localhost:5000`

---

## Features

| Feature | Description |
|---|---|
| 🧑‍⚕️ Patient Management | Register, view, edit, and delete patient demographics |
| 🗓️ Visit Tracking | Record and manage clinical encounters per patient |
| 🩺 Diagnosis Management | Log multiple diagnoses (comorbidities) per visit |
| 🧪 Laboratory Results | Add and track lab test results linked to visits |
| 💊 Medications & Prescriptions | Prescribe drugs and generate printable/PDF prescription slips |
| 📅 Follow-Up Care | Schedule, track, and auto-detect overdue follow-up consultations |
| 🧾 Billing & Invoicing | Auto-generate invoices on every visit with detailed fee breakdown |
| 📊 Analytics & Reports | Real-time population health insights and hospital statistics |
| 🔐 RBAC Access Control | Three-tier role system (Admin / Doctor / Nurse) with granular permissions |
| 💬 WhatsApp Integration | Send prescriptions and follow-up reminders directly to patients via WhatsApp |
| 🔍 Search & Pagination | Server-side search and pagination across all list views |

---

## Tech Stack

- **Backend:** Python 3.9+, Flask
- **Database:** MySQL 8.0+
- **Frontend:** HTML, CSS, Jinja2 templating
- **WhatsApp:** WhatsApp Web API link format (no third-party API key required)
- **PDF/Print:** Browser native print (`Ctrl+P` / `Cmd+P`)

---

## Getting Started

### Prerequisites

- Python **3.9** or higher
- MySQL **8.0** or higher
- A modern web browser (Chrome, Firefox, Edge, or Safari)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd "EPIC EMR"
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install flask mysql-connector-python
   ```

### Database Setup

> ⚠️ **Run only once on initial setup.**

1. Open your MySQL client and execute the SQL schema:
   ```sql
   source /path/to/ehr_project.sql
   ```
2. This creates the `ehrs` database with all required tables and seed data.

### Running the App

```bash
python3 app.py
```

The server starts at: **`http://127.0.0.1:5000`**

Navigate to `http://127.0.0.1:5000/login` in your browser to begin.

---

## User Roles & Permissions

CliniCore uses a **Role-Based Access Control (RBAC)** model. Every user is assigned exactly one role.

| Permission | Admin | Doctor | Nurse |
|---|:---:|:---:|:---:|
| `patients.view` | ✅ | ✅ | ✅ |
| `patients.add` | ✅ | ✅ | ❌ |
| `patients.edit` | ✅ | ✅ | ❌ |
| `patients.delete` | ✅ | ❌ | ❌ |
| `visits.view` | ✅ | ✅ | ✅ |
| `visits.add` | ✅ | ✅ | ❌ |
| `diagnoses.view` | ✅ | ✅ | ✅ |
| `diagnoses.add` | ✅ | ✅ | ❌ |
| `labs.view` | ✅ | ✅ | ✅ |
| `labs.add` | ✅ | ✅ | ✅ |
| `medications.view` | ✅ | ✅ | ✅ |
| `medications.add` | ✅ | ✅ | ❌ |
| `follow_ups.view` | ✅ | ✅ | ✅ |
| `follow_ups.add` | ✅ | ✅ | ❌ |
| `follow_ups.edit` | ✅ | ✅ | ✅ |
| `follow_ups.delete` | ✅ | ❌ | ❌ |
| `ehr.view` | ✅ | ✅ | ❌ |
| `analytics.view` | ✅ | ✅ | ❌ |
| `admin.users` | ✅ | ❌ | ❌ |

> 🔒 Unauthorized actions are blocked automatically with an "Access Denied" message.

---

## Modules

### 1. 🏠 Dashboard
Real-time summary cards: Total Patients, Visits, Diagnoses, Lab Results, Medications, Follow-Ups, Overdue count, and Average Patient Age. Also shows gender distribution and top 5 common diseases.

### 2. 🧑 Patient Management (`/patients`)
- View paginated patient list (25/page), search by name or contact
- Register new patients with auto-assigned ID (e.g., `#P0042`)
- Edit demographics; delete with cascading cleanup *(Admin only)*
- **Patient Chart** — a single view of a patient's complete medical history

### 3. 🗓️ Visit Management (`/visits`)
- Record clinical encounters linked to patients and doctors
- Auto-populates doctor's name for the Doctor role
- **Auto-generates a billing invoice** on every new visit (default: Rs. 525.00)

### 4. 🩺 Diagnosis Management (`/diagnoses`)
- Log one or multiple diagnoses (comorbidities) per visit
- Searchable by disease name or patient name

### 5. 🧪 Laboratory Results (`/lab_results`)
- Enter lab test results linked to visits (Nurses can add)
- Supports any test format: value + units, normal/abnormal, etc.

### 6. 💊 Medications & Prescriptions (`/medications`)
- Prescribe drugs with dosage instructions using standard abbreviations (OD, BD, TID…)
- Print-ready **Prescription Slip** at `/prescription/<visit_id>` — includes patient details, diagnoses, medications, lab results, and billing summary

### 7. 📅 Follow-Up Care (`/follow_ups`)
- Schedule follow-ups with type, priority (Normal / High / Urgent), and physician notes
- **Auto-overdue detection**: Scheduled follow-ups past their date are automatically marked Overdue on page load
- Status lifecycle: `Scheduled → Overdue → Completed / Cancelled`
- Filter by status and priority; WhatsApp reminders with one click

### 8. 🧾 Billing & Invoicing (`/bill/<id>`)
- Auto-generated invoice for every visit (format: `INV-XXXXXX`)
- Fee breakdown: Consultation + Pharmacy + Lab + Tax = Total
- Payment status: Paid / Pending / Partially Paid
- Payment method: UPI / Cash / Card / Insurance

### 9. 📂 EHR Registry (`/ehr`)
- Consolidated view of ALL clinical data in one table
- Only shows visits with at least one diagnosis, lab result, AND medication
- *(Admin and Doctor only)*

### 10. 📊 Analytics (`/analytics`)
- Gender distribution chart
- Top 10 most diagnosed diseases
- Age group breakdown (Pediatric / Young Adult / Adult / Middle-Aged / Senior)
- Top 10 prescribed medications
- Summary statistics panel
- *(Admin and Doctor only)*

### 11. 🔧 Admin — User Management (`/admin/users`)
- Create, activate/deactivate, and delete system user accounts *(Admin only)*
- Protected: Primary Admin account (User ID 1) cannot be deactivated or deleted

---

## WhatsApp Integration

CliniCore integrates WhatsApp to send:

- **📄 Prescription messages** — sent from the prescription page or patient chart
- **🔔 Follow-up reminders** — sent from the follow-up list with one click

**How it works:**
1. The system formats the patient's phone number to international E.164 format.
2. A professionally structured message is composed.
3. The browser opens **WhatsApp Web** (or the mobile app) with the message pre-filled.
4. The staff member reviews and clicks **Send** — no automated sending occurs.

**Default country code:** India (`+91`). To change:
```python
# whatsapp_service.py → format_whatsapp_phone()
default_country_code = "971"  # e.g., UAE
```

**Phone number formats handled automatically:**

| Input | WhatsApp Format |
|---|---|
| `9876543210` (10 digits) | `919876543210` |
| `09876543210` (with leading 0) | `919876543210` |
| `919876543210` (12 digits) | `919876543210` |
| `+919876543210` | `919876543210` |

---

## Project Structure

```
EPIC EMR/
├── app.py                  # Main Flask application — all routes and RBAC logic
├── database.py             # MySQL connection helper
├── patient.py              # Patient model/utilities
├── visit.py                # Visit model/utilities
├── analytics.py            # Analytics query logic
├── whatsapp_service.py     # WhatsApp message composition & phone formatting
├── generate_data.py        # Synthetic data generator for testing
├── main.py                 # Entry point (alternative runner)
├── test_db.py              # Database connection test
├── ehr_project.sql         # Full MySQL schema + seed data
├── user_manual.txt         # Comprehensive user manual (v1.0)
├── static/                 # CSS, JS, images
├── templates/              # Jinja2 HTML templates
└── .venv/                  # Python virtual environment
```

---

## Database Schema

The system uses a MySQL database named **`ehrs`** with the following tables:

```
patients          — Patient demographics (id, name, age, gender, contact)
visits            — Clinical encounters (visit_id, patient_id, visit_date, doctor_name)
diagnoses         — Diagnoses per visit (diagnosis_id, visit_id, disease_name)
lab_results       — Lab tests per visit (lab_id, visit_id, test_name, result_value)
medications       — Prescriptions per visit (med_id, visit_id, drug_name, dosage)
follow_ups        — Follow-up schedule (id, patient_id, scheduled_date, type, status, priority, notes, doctor_name)
users             — System users (user_id, username, password, role, is_active)
billing_invoices  — Invoices per visit (invoice_id, visit_id, fees, total, payment_status, payment_method)
```

> All clinical tables use **cascading deletes** — deleting a patient removes all linked records automatically.

---

## Default Credentials

> ⚠️ **Change these immediately after first login in production.**

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Admin |
| `doctor` | `doc123` | Doctor |

---

## FAQ

**Q: Why is a follow-up showing as "Overdue" automatically?**
> This is by design. Every time the Follow-Ups page loads, the system scans all Scheduled follow-ups and marks any past their date as Overdue.

**Q: The EHR Registry shows fewer records than expected — why?**
> The EHR Registry only shows visits that have at least one diagnosis, one lab result, AND one medication. Use individual module pages or the Patient Chart to see all data.

**Q: Can I edit a visit, diagnosis, lab result, or medication after saving?**
> The current version supports add-only for clinical entries. Contact the Admin for database-level corrections.

**Q: How do I change the default consultation fee?**
> Modify the default values in the `add_visit()` route in `app.py` within the `INSERT INTO billing_invoices` statement.

**Q: How do I change the WhatsApp country code?**
> In `whatsapp_service.py`, update the `default_country_code` parameter in `format_whatsapp_phone()`.

---

## 📄 Documentation

For full step-by-step usage instructions, refer to the [User Manual](./user_manual.txt) (v1.0).

---

> *CliniCore EHR/EMR Portal — v1.0 | © 2026 CliniCore General Hospital. All Rights Reserved.*
> *For technical support, contact your system administrator.*
