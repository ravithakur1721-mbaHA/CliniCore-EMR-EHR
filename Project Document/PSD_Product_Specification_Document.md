# Product Specification Document (PSD)
## CliniCore EHR — System Architecture, Database Design & Technical Specification

---

### Document Control
* **Document Title:** Product Specification Document (PSD) / Technical Architecture Document
* **Project Name:** CliniCore EHR
* **Version:** 1.0.0
* **Status:** Approved / Active
* **Date:** November 24, 2026
* **Target Audience:** Backend Developers, DevOps Engineers, System Architects, Security Auditors

---

## 1. System Architecture Overview

CliniCore EHR is built on a **Serverless Decoupled Architecture** where the application runtime, database layer, and static asset distribution are completely isolated for high availability, security, and zero fixed infrastructure cost:

```mermaid
flowchart TD
    subgraph ClientLayer["Client & Device Layer"]
        Browser["Clinician Web Browser<br/>(Desktop / Tablet)"]
        WhatsAppClient["Patient WhatsApp Client<br/>(Mobile / Web)"]
    end

    subgraph VercelEdge["Vercel Global Edge Network"]
        EdgeCDN["Vercel Global Edge CDN<br/>(/public/static/*, /robots.txt, /sitemap.xml)"]
        EdgeRouter["Vercel Edge Router<br/>(Rewrites -> /api/index)"]
    end

    subgraph ServerlessCompute["Serverless Compute Layer (AWS Lambda)"]
        Lambda["Python 3.9+ WSGI Serverless Function<br/>(Flask 3.0.3 + Werkzeug)"]
        CSRFMiddleware["CSRF & Session Security Layer"]
        RateLimiter["Brute-Force Rate Limiter"]
        AppRouting["Application Controllers & Jinja2 Templates"]
    end

    subgraph DatabaseLayer["Cloud Database Layer (AWS Tokyo / ap-northeast-1)"]
        TiDBServerless["TiDB Cloud Serverless Cluster<br/>(MySQL 8.0 Protocol Engine)"]
        TLSEncryption["TLS 1.3 / SSL Encryption Layer"]
        StorageEngine["TiKV Distributed Storage Engine<br/>(Auto-scaling, High Availability)"]
    end

    Browser -->|"HTTPS / TLS 1.3"| EdgeCDN
    Browser -->|"Dynamic Requests"| EdgeRouter
    EdgeRouter --> Lambda
    Lambda --> CSRFMiddleware --> RateLimiter --> AppRouting
    AppRouting -->|"Pure-Python PyMySQL + TLS"| TLSEncryption
    TLSEncryption --> TiDBServerless --> StorageEngine
    AppRouting -.->|"Direct https://wa.me/ link"| WhatsAppClient
```

---

## 2. Technology Stack & Architectural Decisions

| Layer | Component | Version / Specification | Architectural Rationale |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | Flask | `3.0.3` | Lightweight, unbloated micro-framework with near-zero cold start (< 150ms). |
| **WSGI Server** | Werkzeug | `3.1.5` | Battle-tested security utilities (cryptographic hash checks, safe cookies). |
| **Database Driver** | PyMySQL | `1.1.1` | **Pure Python** driver. Eliminates 60MB of C-extension binaries (`mysql-connector-python`), allowing the serverless function package to remain under 2MB. |
| **Cryptography** | Cryptography | `42.0.8` | Supports modern `caching_sha2_password` authentication and secure TLS/SSL handshakes with cloud databases. |
| **Environment Mgmt** | python-dotenv | `1.0.1` | Seamless loading of local `.env` variables for development parity with cloud environments. |
| **Database Engine** | TiDB Cloud Serverless | MySQL `8.0.11` Compatible | Distributed, multi-AZ, auto-scaling, with a permanent 5GB free tier and TLS encryption. |
| **Hosting & Edge** | Vercel Edge Serverless | Build Output API | Global CDN caching for static assets, auto-renewing SSL, zero infrastructure maintenance. |
| **Iconography** | Phosphor Icons | `@phosphor-icons/web` | Clean, professional clinical iconography replacing emojis for an enterprise look. |

---

## 3. Database Schema & Data Dictionary

The database is normalized to 3NF and structured across 8 tables with relational integrity and foreign key constraints:

```mermaid
erDiagram
    PATIENTS ||--o{ VISITS : "has"
    PATIENTS ||--o{ FOLLOW_UPS : "schedules"
    PATIENTS ||--o{ BILLING_INVOICES : "billed to"
    VISITS ||--o{ DIAGNOSES : "yields"
    VISITS ||--o{ LAB_RESULTS : "orders"
    VISITS ||--o{ MEDICATIONS : "prescribes"
    VISITS ||--o| BILLING_INVOICES : "encounters"

    PATIENTS {
        int patient_id PK
        varchar name
        int age
        varchar gender
        varchar contact
    }

    VISITS {
        int visit_id PK
        int patient_id FK
        date visit_date
        varchar doctor_name
    }

    DIAGNOSES {
        int diagnosis_id PK
        int visit_id FK
        varchar disease_name
    }

    LAB_RESULTS {
        int lab_id PK
        int visit_id FK
        varchar test_name
        varchar result_value
    }

    MEDICATIONS {
        int med_id PK
        int visit_id FK
        varchar drug_name
        varchar dosage
    }

    FOLLOW_UPS {
        int follow_up_id PK
        int patient_id FK
        date scheduled_date
        varchar follow_up_type
        varchar status
        varchar priority
        text notes
        varchar doctor_name
    }

    BILLING_INVOICES {
        int invoice_id PK
        int visit_id FK
        int patient_id FK
        varchar invoice_number UK
        date invoice_date
        decimal consultation_fee
        decimal pharmacy_fee
        decimal lab_fee
        decimal tax_amount
        decimal total_amount
        varchar payment_status
        varchar payment_method
    }

    USERS {
        int user_id PK
        varchar username UK
        varchar password
        varchar role
        tinyint is_active
    }
```

### 3.1 Table Specifications

#### 1. `patients`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `patient_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Unique patient identifier (formatted as `#P0001`). |
| `name` | `VARCHAR(100)` | `NOT NULL` | Patient full legal name. |
| `age` | `INT` | `CHECK (age BETWEEN 1 AND 150)` | Patient age in years. |
| `gender` | `VARCHAR(10)` | `NOT NULL` | Gender (`Male`, `Female`, `Other`). |
| `contact` | `VARCHAR(15)` | `NOT NULL` | Mobile phone number used for WhatsApp notifications. |

#### 2. `visits`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `visit_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Clinical encounter identifier. |
| `patient_id` | `INT` | `FOREIGN KEY -> patients(patient_id)` | Link to patient record. |
| `visit_date` | `DATE` | `NOT NULL` | Date of clinical consultation. |
| `doctor_name` | `VARCHAR(100)` | `NOT NULL` | Attending physician name. |

#### 3. `diagnoses`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `diagnosis_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Diagnosis entry identifier. |
| `visit_id` | `INT` | `FOREIGN KEY -> visits(visit_id)` | Linked clinical visit. |
| `disease_name` | `VARCHAR(100)` | `NOT NULL` | Clinical diagnosis or disease name. |

#### 4. `lab_results`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `lab_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Investigation record ID. |
| `visit_id` | `INT` | `FOREIGN KEY -> visits(visit_id)` | Linked clinical visit. |
| `test_name` | `VARCHAR(100)` | `NOT NULL` | Diagnostic test name (e.g., `HbA1c`, `TSH`, `ECG`). |
| `result_value` | `VARCHAR(50)` | `NOT NULL` | Test reading or clinical finding. |

#### 5. `medications`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `med_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Prescription line item ID. |
| `visit_id` | `INT` | `FOREIGN KEY -> visits(visit_id)` | Linked clinical encounter. |
| `drug_name` | `VARCHAR(100)` | `NOT NULL` | Drug generic or brand name. |
| `dosage` | `VARCHAR(50)` | `NOT NULL` | Clinical dosage and regimen (e.g., `500 mg BD`). |

#### 6. `follow_ups`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `follow_up_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Care plan review identifier. |
| `patient_id` | `INT` | `FOREIGN KEY -> patients(patient_id)` | Target patient. |
| `scheduled_date` | `DATE` | `NOT NULL` | Scheduled review date. |
| `follow_up_type` | `VARCHAR(100)` | `DEFAULT 'Routine Review'` | Review category (`Routine`, `Lab`, `Cardiology`). |
| `status` | `VARCHAR(50)` | `DEFAULT 'Scheduled'` | Status (`Scheduled`, `Completed`, `Cancelled`, `Overdue`). |
| `priority` | `VARCHAR(50)` | `DEFAULT 'Normal'` | Urgency tier (`Urgent`, `High`, `Normal`, `Low`). |
| `notes` | `TEXT` | `NULLABLE` | Clinical clinical instructions or review goals. |
| `doctor_name` | `VARCHAR(100)` | `NOT NULL` | Physician scheduling the follow-up. |

#### 7. `billing_invoices`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `invoice_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Unique invoice primary key. |
| `visit_id` | `INT` | `FOREIGN KEY -> visits(visit_id)` | Encounter billed. |
| `patient_id` | `INT` | `FOREIGN KEY -> patients(patient_id)` | Billed patient ID. |
| `invoice_number` | `VARCHAR(50)` | `UNIQUE`, `NOT NULL` | Alphanumeric invoice code (`INV-000001`). |
| `invoice_date` | `DATE` | `NOT NULL` | Invoice generation date. |
| `consultation_fee` | `DECIMAL(10,2)` | `DEFAULT 500.00` | Physician fee. |
| `pharmacy_fee` | `DECIMAL(10,2)` | `DEFAULT 0.00` | Medication cost. |
| `lab_fee` | `DECIMAL(10,2)` | `DEFAULT 0.00` | Diagnostic test charges. |
| `tax_amount` | `DECIMAL(10,2)` | `DEFAULT 25.00` | Applicable tax. |
| `total_amount` | `DECIMAL(10,2)` | `DEFAULT 525.00` | Gross invoice amount. |
| `payment_status` | `VARCHAR(50)` | `DEFAULT 'Paid'` | Status (`Paid`, `Pending`, `Waived`). |
| `payment_method` | `VARCHAR(50)` | `DEFAULT 'UPI'` | Method (`UPI`, `Cash`, `Card`, `NetBanking`). |

#### 8. `users`
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `user_id` | `INT` | `AUTO_INCREMENT`, `PRIMARY KEY` | Staff user account identifier. |
| `username` | `VARCHAR(50)` | `UNIQUE`, `NOT NULL` | Staff login username. |
| `password` | `VARCHAR(255)` | `NOT NULL` | Cryptographic salted hash (`pbkdf2:sha256` or `scrypt`). |
| `role` | `VARCHAR(20)` | `NOT NULL` | RBAC Role (`Admin`, `Doctor`, `Nurse`). |
| `is_active` | `TINYINT(1)` | `DEFAULT 1` | Account state flag (1 = Active, 0 = Suspended). |

---

## 4. Security Architecture Specification

### 4.1 Cryptographic Password Storage & Auto-Upgrading
When users authenticate, passwords are verified using `werkzeug.security.check_password_hash`. If legacy unhashed records are encountered, the system automatically computes a modern salted hash and updates the database record on the fly:
```python
if stored_pwd.startswith(("scrypt:", "pbkdf2:")):
    authenticated = check_password_hash(stored_pwd, password)
elif stored_pwd == password:
    authenticated = True
    # Immediately upgrade plaintext to salted hash
    new_hash = generate_password_hash(password)
    cur.execute("UPDATE users SET password=%s WHERE user_id=%s", (new_hash, user["user_id"]))
    conn.commit()
```

### 4.2 Cross-Site Request Forgery (CSRF) Defense
* **Token Issuance:** Cryptographically random 32-byte hexadecimal token (`secrets.token_hex(32)`) generated per user session.
* **Timing-Attack Resistance:** Validated with `secrets.compare_digest(str(token), str(expected))`.
* **Login Exemption:** The `/login` endpoint is exempted from CSRF abortion to prevent lockouts during initial cookie negotiation; all subsequent state-changing operations require valid tokens.
* **Action CSRF:** Critical GET links (such as patient deletion or user activation toggles) require query parameter verification (`?csrf=<token>`).

### 4.3 Brute-Force Rate Limiting & Proxy IP Resolution
To protect against credential-stuffing attacks without false positives behind cloud reverse proxies:
```python
client_ip = (
    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    or request.remote_addr
    or "127.0.0.1"
)
```
Failed attempts are recorded in an in-memory sliding window. 5 failed attempts result in an automatic 300-second lockout.

### 4.4 HTTP Security Headers
Every HTTP response outgoing from CliniCore includes OWASP-recommended hardening headers:
```http
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self';
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## 5. API & Route Specification

| Route Path | HTTP Methods | Required Permission | Description |
| :--- | :---: | :---: | :--- |
| `/login` | `GET`, `POST` | Public | Authentication endpoint with rate limiting. |
| `/logout` | `GET` | Authenticated | Clears session and redirects to login. |
| `/` | `GET` | Authenticated | Clinical dashboard with overview statistics and charts. |
| `/patients` | `GET` | `patients.view` | Patient list with query search (`?q=`) and pagination (`?page=`). |
| `/patients/add` | `GET`, `POST` | `patients.add` | Demographic registration form. |
| `/patient/<pid>` | `GET` | `patients.view` | Comprehensive 360-degree patient chart view. |
| `/edit_patient/<pid>` | `GET`, `POST` | `patients.edit` | Demographic modification form. |
| `/delete_patient/<pid>` | `GET` | `patients.delete` | Hard deletion of patient record (requires action CSRF). |
| `/visits` | `GET` | `visits.view` | Encounter history with doctor search and pagination. |
| `/visits/add` | `GET`, `POST` | `visits.add` | Record clinical encounter and auto-create billing record. |
| `/diagnoses` | `GET` | `diagnoses.view` | Disease diagnoses log and pagination. |
| `/diagnoses/add` | `GET`, `POST` | `diagnoses.add` | Associate a new disease diagnosis with an encounter. |
| `/lab_results` | `GET` | `labs.view` | Diagnostic investigation log. |
| `/lab_results/add` | `GET`, `POST` | `labs.add` | Log a new lab test reading. |
| `/medications` | `GET` | `medications.view` | Prescription and drug registry. |
| `/medications/add` | `GET`, `POST` | `medications.add` | Add a prescribed drug with dosage. |
| `/follow_ups` | `GET` | `follow_ups.view` | Care plan queue with priority/status filters and auto-overdue update. |
| `/follow_ups/add` | `GET`, `POST` | `follow_ups.add` | Schedule a future follow-up consultation. |
| `/follow_up/status/<fuid>` | `GET` | `follow_ups.edit` | Toggle status (`Completed`, `Cancelled`, `Scheduled`). |
| `/follow_up/whatsapp/<fuid>`| `GET` | `follow_ups.view` | Generate and redirect to pre-composed WhatsApp follow-up reminder. |
| `/prescription/<vid>` | `GET` | `medications.view` | Clinical prescription printable layout. |
| `/prescription/whatsapp/<vid>`| `GET` | `medications.view` | Generate and launch WhatsApp prescription link. |
| `/bill/<inv_id>` | `GET` | `patients.view` | Formal patient invoice and billing print receipt. |
| `/ehr` | `GET` | `ehr.view` | Full multi-table joined Electronic Health Record view. |
| `/analytics` | `GET` | `analytics.view` | Population health reports and demographic visualizations. |
| `/admin/users` | `GET` | `admin.users` | User management administration panel. |
| `/admin/users/add` | `POST` | `admin.users` | Register staff account with assigned RBAC role. |
| `/admin/users/toggle/<uid>` | `GET` | `admin.users` | Activate/Deactivate staff account. |
| `/admin/users/delete/<uid>` | `GET` | `admin.users` | Remove staff user account. |
| `/robots.txt` | `GET` | Public | SEO crawler rules. |
| `/sitemap.xml` | `GET` | Public | Search engine indexing XML map. |

---

## 6. Deployment & Serverless Specification

### 6.1 Vercel Zero-Config Configuration (`vercel.json`)
```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/api/index"
    }
  ]
}
```
* **Edge Static Assets:** Assets in `/public/` are served by Vercel CDN globally without serverless execution.
* **Serverless Entrypoint:** Dynamic traffic routes to `/api/index.py`, which exposes the Flask `app` object.

### 6.2 Environment Variables Reference
| Variable Name | Required | Default / Example | Purpose |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | **Yes** | `mysql://user:pass@host:4000/ehrs?ssl=true` | Unified connection string for TiDB Cloud Serverless. |
| `FLASK_SECRET_KEY` | Recommended | `clinicore-super-secure-production-secret...` | Session cryptographic signing key. |
| `VERCEL` | Auto | `1` | Automatically set by Vercel runtime to trigger secure cookie flags. |

---

## 7. Local Development Runbook

### 7.1 Prerequisites
* Python 3.9+ installed (`python3 --version`)
* Access to MySQL 8+ or TiDB Cloud Serverless instance

### 7.2 Installation Steps
```bash
# 1. Clone repository
git clone https://github.com/ravithakur1721-mbaHA/CliniCore-EMR-EHR.git
cd CliniCore-EMR-EHR

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure local environment variables (.env)
cp .env.example .env  # Or paste DATABASE_URL in .env

# 5. Run local development server
python3 app.py
```
Open `http://localhost:5000` in your browser. Default demo credentials:
* **Admin:** `admin` / `admin123`
* **Doctor:** `doctor` / `doc123`
