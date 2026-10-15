from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from database import get_connection
from datetime import datetime, date, timedelta
from functools import wraps
import math
from whatsapp_service import (
    format_whatsapp_phone,
    build_whatsapp_link,
    compose_prescription_whatsapp_message,
    compose_followup_whatsapp_message,
)

app = Flask(__name__)
app.secret_key = "clinicore_ehr_secret_2025"


# ═══════════════════════════════════════════════════════════════
# RBAC: Role Permissions Definition
# ═══════════════════════════════════════════════════════════════

ROLE_PERMISSIONS = {
    "Admin": {
        "patients.view", "patients.add", "patients.edit", "patients.delete",
        "visits.view", "visits.add",
        "diagnoses.view", "diagnoses.add",
        "labs.view", "labs.add",
        "medications.view", "medications.add",
        "follow_ups.view", "follow_ups.add", "follow_ups.edit", "follow_ups.delete",
        "ehr.view",
        "analytics.view",
        "admin.users",
    },
    "Doctor": {
        "patients.view", "patients.add", "patients.edit",
        "visits.view", "visits.add",
        "diagnoses.view", "diagnoses.add",
        "labs.view", "labs.add",
        "medications.view", "medications.add",
        "follow_ups.view", "follow_ups.add", "follow_ups.edit",
        "ehr.view",
        "analytics.view",
    },
    "Nurse": {
        "patients.view",
        "visits.view",
        "diagnoses.view",
        "labs.view", "labs.add",
        "medications.view",
        "follow_ups.view", "follow_ups.edit",
    },
}


def can(permission: str) -> bool:
    role = session.get("role")
    if not role:
        return False
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if not can(permission):
                flash(f"Access Denied: You do not have permission '{permission}'.", "error")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════
# DB Helpers & Pagination
# ═══════════════════════════════════════════════════════════════

def get_stats():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    stats = {}
    cur.execute("SELECT COUNT(*) AS c FROM patients");    stats["patients"]  = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM visits");      stats["visits"]    = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM diagnoses");   stats["diagnoses"] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM lab_results"); stats["labs"]      = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM medications"); stats["meds"]      = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups");  stats["follow_ups"] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups WHERE status = 'Overdue'"); stats["overdue_follow_ups"] = cur.fetchone()["c"]
    cur.execute("SELECT ROUND(AVG(age), 1) AS a FROM patients")
    row = cur.fetchone(); stats["avg_age"] = row["a"] if row["a"] else "—"
    cur.close(); conn.close()
    return stats


def get_patient_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM patients")
    n = cur.fetchone()[0]; cur.close(); conn.close()
    return n


def get_overdue_follow_up_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM follow_ups WHERE status = 'Overdue'")
    n = cur.fetchone()[0]; cur.close(); conn.close()
    return n


def paginate(total_items, page, per_page=25):
    page = max(1, page)
    total_pages = max(1, math.ceil(total_items / per_page))
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    start_p = max(1, page - 2)
    end_p = min(total_pages, page + 2)
    page_range = list(range(start_p, end_p + 1))
    return page, total_pages, offset, page_range


# Inject globals into every template
@app.context_processor
def inject_globals():
    base = {
        "now": datetime.now().strftime("%d %b %Y, %H:%M"),
        "can": can,
    }
    if "user" in session:
        base["patient_count"] = get_patient_count()
        base["overdue_count"] = get_overdue_follow_up_count()
    else:
        base["patient_count"] = 0
        base["overdue_count"] = 0
    return base


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s AND is_active=1",
            (username, password)
        )
        user = cur.fetchone(); cur.close(); conn.close()

        if user:
            session["user"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome, {user['username']}! Signed in as {user['role']}.", "success")
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials or account inactive.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM patients ORDER BY patient_id DESC LIMIT 7")
    recent_patients = cur.fetchall()
    cur.execute("SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender")
    gender_dist = cur.fetchall()
    cur.execute("""
        SELECT disease_name AS disease, COUNT(*) AS count
        FROM diagnoses GROUP BY disease_name ORDER BY count DESC LIMIT 5
    """)
    common_diseases = list(enumerate(cur.fetchall()))
    cur.close(); conn.close()

    return render_template("index.html",
        stats=get_stats(),
        recent_patients=recent_patients,
        gender_dist=gender_dist,
        common_diseases=common_diseases,
    )


# ═══════════════════════════════════════════════════════════════
# Patients (with Server-side Pagination & Search)
# ═══════════════════════════════════════════════════════════════

@app.route("/patients")
@require_permission("patients.view")
def patients():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if q:
        query_like = f"%{q}%"
        cur.execute("SELECT COUNT(*) AS cnt FROM patients WHERE name LIKE %s OR contact LIKE %s", (query_like, query_like))
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT * FROM patients 
            WHERE name LIKE %s OR contact LIKE %s 
            ORDER BY patient_id DESC LIMIT %s OFFSET %s
        """, (query_like, query_like, per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM patients")
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("SELECT * FROM patients ORDER BY patient_id DESC LIMIT %s OFFSET %s", (per_page, offset))

    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("patients.html",
        patients=data, q=q,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


@app.route("/patients/add", methods=["GET", "POST"])
@require_permission("patients.add")
def add_patient():
    if request.method == "POST":
        name    = request.form["name"].strip()
        age     = request.form["age"].strip()
        gender  = request.form["gender"]
        contact = request.form["contact"].strip()

        if not all([name, age, gender, contact]):
            return render_template("add_patient.html", error="All fields are required.", form=request.form)
        try:
            age_int = int(age)
            if not (1 <= age_int <= 150): raise ValueError
        except ValueError:
            return render_template("add_patient.html", error="Age must be 1–150.", form=request.form)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO patients (name, age, gender, contact) VALUES (%s,%s,%s,%s)",
            (name, age_int, gender, contact)
        )
        conn.commit(); pid = cur.lastrowid; cur.close(); conn.close()
        flash(f"Patient '{name}' registered successfully (#P{pid:04d}) and added to database.", "success")
        return redirect(url_for("patient_chart", pid=pid))

    return render_template("add_patient.html", form={})


@app.route("/patient/<int:pid>")
@require_permission("patients.view")
def patient_chart(pid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM patients WHERE patient_id=%s", (pid,))
    patient = cur.fetchone()
    if not patient:
        cur.close(); conn.close()
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))

    cur.execute("SELECT * FROM visits WHERE patient_id=%s ORDER BY visit_date DESC", (pid,))
    visits_data = cur.fetchall()
    cur.execute("SELECT d.* FROM diagnoses d JOIN visits v ON d.visit_id=v.visit_id WHERE v.patient_id=%s", (pid,))
    diagnoses_data = cur.fetchall()
    cur.execute("SELECT l.* FROM lab_results l JOIN visits v ON l.visit_id=v.visit_id WHERE v.patient_id=%s", (pid,))
    labs_data = cur.fetchall()
    cur.execute("SELECT m.* FROM medications m JOIN visits v ON m.visit_id=v.visit_id WHERE v.patient_id=%s", (pid,))
    meds_data = cur.fetchall()
    cur.execute("SELECT * FROM follow_ups WHERE patient_id=%s ORDER BY scheduled_date DESC", (pid,))
    follow_ups_data = cur.fetchall()
    cur.close(); conn.close()

    return render_template("patient_chart.html",
        patient=patient, visits=visits_data, diagnoses=diagnoses_data,
        labs=labs_data, meds=meds_data, follow_ups=follow_ups_data
    )


@app.route("/edit_patient/<int:pid>", methods=["GET", "POST"])
@require_permission("patients.edit")
def edit_patient(pid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM patients WHERE patient_id=%s", (pid,))
    patient = cur.fetchone()
    if not patient:
        cur.close(); conn.close()
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))

    if request.method == "POST":
        name    = request.form["name"].strip()
        age     = int(request.form["age"])
        gender  = request.form["gender"]
        contact = request.form["contact"].strip()
        cur.execute(
            "UPDATE patients SET name=%s,age=%s,gender=%s,contact=%s WHERE patient_id=%s",
            (name, age, gender, contact, pid)
        )
        conn.commit(); cur.close(); conn.close()
        flash(f"Patient '{name}' updated.", "success")
        return redirect(url_for("patients"))

    cur.close(); conn.close()
    return render_template("edit_patient.html", patient=patient)


@app.route("/delete_patient/<int:pid>")
@require_permission("patients.delete")
def delete_patient(pid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT name FROM patients WHERE patient_id=%s", (pid,))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM patients WHERE patient_id=%s", (pid,))
        conn.commit()
        flash(f"Patient '{row['name']}' permanently deleted.", "success")
    cur.close(); conn.close()
    return redirect(url_for("patients"))


# ═══════════════════════════════════════════════════════════════
# Visits (with Pagination & Search)
# ═══════════════════════════════════════════════════════════════

@app.route("/visits")
@require_permission("visits.view")
def visits():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if q:
        query_like = f"%{q}%"
        cur.execute("""
            SELECT COUNT(*) AS cnt 
            FROM visits v JOIN patients p ON v.patient_id = p.patient_id
            WHERE p.name LIKE %s OR v.doctor_name LIKE %s
        """, (query_like, query_like))
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT v.*, p.name AS patient_name, p.gender
            FROM visits v JOIN patients p ON v.patient_id = p.patient_id
            WHERE p.name LIKE %s OR v.doctor_name LIKE %s
            ORDER BY v.visit_date DESC LIMIT %s OFFSET %s
        """, (query_like, query_like, per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM visits")
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT v.*, p.name AS patient_name, p.gender
            FROM visits v JOIN patients p ON v.patient_id = p.patient_id
            ORDER BY v.visit_date DESC LIMIT %s OFFSET %s
        """, (per_page, offset))

    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("visits.html",
        visits=data, q=q,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


@app.route("/visits/add", methods=["GET", "POST"])
@require_permission("visits.add")
def add_visit():
    if request.method == "POST":
        patient_id  = int(request.form["patient_id"])
        visit_date  = request.form["visit_date"]
        doctor_name = request.form["doctor_name"].strip()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO visits (patient_id,visit_date,doctor_name) VALUES (%s,%s,%s)",
            (patient_id, visit_date, doctor_name)
        )
        conn.commit()
        vid = cur.lastrowid

        # Also auto-create a billing invoice record for the new visit encounter
        inv_number = f"INV-{vid:06d}"
        cur.execute("""
            INSERT IGNORE INTO billing_invoices 
            (visit_id, patient_id, invoice_number, invoice_date, consultation_fee, pharmacy_fee, lab_fee, tax_amount, total_amount, payment_status, payment_method)
            VALUES (%s, %s, %s, %s, 500.00, 0.00, 0.00, 25.00, 525.00, 'Paid', 'UPI')
        """, (vid, patient_id, inv_number, visit_date))
        conn.commit()
        cur.close(); conn.close()
        flash("Visit recorded successfully and added to EHR registry.", "success")
        return redirect(url_for("patient_chart", pid=patient_id))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    # Order by patient_id DESC so newly registered patients appear at the top!
    cur.execute("SELECT patient_id, name, age, gender, contact FROM patients ORDER BY patient_id DESC")
    patient_list = cur.fetchall(); cur.close(); conn.close()
    default_pid = request.args.get("patient_id", "")
    today_date = date.today().strftime("%Y-%m-%d")
    default_doc = session.get("user") if session.get("role") == "Doctor" else "Dr. Rajesh Gupta"
    return render_template("add_visit.html",
        patients=patient_list,
        default_pid=default_pid,
        today_date=today_date,
        default_doctor=default_doc
    )


# ═══════════════════════════════════════════════════════════════
# Follow-Up Care Tracking
# ═══════════════════════════════════════════════════════════════

@app.route("/follow_ups")
@require_permission("follow_ups.view")
def follow_ups():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "All").strip()
    priority_filter = request.args.get("priority", "All").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 1. Update any overdue status automatically (scheduled_date < CURDATE() and status='Scheduled')
    cur.execute("UPDATE follow_ups SET status = 'Overdue' WHERE status = 'Scheduled' AND scheduled_date < CURDATE()")
    conn.commit()

    # 2. Status counts
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups"); total_c = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups WHERE status = 'Scheduled'"); sched_c = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups WHERE status = 'Overdue'"); over_c = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM follow_ups WHERE status = 'Completed'"); comp_c = cur.fetchone()["c"]
    counts = {"total": total_c, "scheduled": sched_c, "overdue": over_c, "completed": comp_c}

    # 3. Dynamic filter building
    where_clauses = []
    params = []

    if status_filter != "All":
        where_clauses.append("f.status = %s")
        params.append(status_filter)
    if priority_filter != "All":
        where_clauses.append("f.priority = %s")
        params.append(priority_filter)
    if q:
        where_clauses.append("(p.name LIKE %s OR p.contact LIKE %s OR f.doctor_name LIKE %s)")
        q_like = f"%{q}%"
        params.extend([q_like, q_like, q_like])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Total matching items
    count_sql = f"""
        SELECT COUNT(*) AS cnt
        FROM follow_ups f
        JOIN patients p ON f.patient_id = p.patient_id
        {where_sql}
    """
    cur.execute(count_sql, tuple(params))
    total_items = cur.fetchone()["cnt"]

    page, total_pages, offset, page_range = paginate(total_items, page, per_page)

    # Query page items
    fetch_sql = f"""
        SELECT f.*, p.name AS patient_name, p.gender, p.contact
        FROM follow_ups f
        JOIN patients p ON f.patient_id = p.patient_id
        {where_sql}
        ORDER BY 
          CASE WHEN f.status = 'Overdue' THEN 1 WHEN f.status = 'Scheduled' THEN 2 ELSE 3 END,
          f.scheduled_date ASC
        LIMIT %s OFFSET %s
    """
    params.extend([per_page, offset])
    cur.execute(fetch_sql, tuple(params))
    rows = cur.fetchall()
    cur.close(); conn.close()

    return render_template("follow_ups.html",
        follow_ups=rows, counts=counts,
        status_filter=status_filter, priority_filter=priority_filter, q=q,
        page=page, total_pages=total_pages, total_items=total_items,
        per_page=per_page, page_range=page_range
    )


@app.route("/follow_ups/add", methods=["GET", "POST"])
@require_permission("follow_ups.add")
def add_follow_up():
    if request.method == "POST":
        patient_id     = int(request.form["patient_id"])
        scheduled_date = request.form["scheduled_date"]
        follow_up_type = request.form.get("follow_up_type", "Routine Review")
        priority       = request.form.get("priority", "Normal")
        notes          = request.form.get("notes", "").strip()
        doctor_name    = request.form.get("doctor_name", "").strip()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO follow_ups (patient_id, scheduled_date, follow_up_type, status, priority, notes, doctor_name)
            VALUES (%s, %s, %s, 'Scheduled', %s, %s, %s)
        """, (patient_id, scheduled_date, follow_up_type, priority, notes, doctor_name))
        conn.commit(); cur.close(); conn.close()
        flash("Follow-up consultation successfully scheduled.", "success")
        return redirect(url_for("follow_ups"))

    selected_pid = request.args.get("patient_id", type=int)
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT patient_id, name, age, gender, contact FROM patients ORDER BY patient_id DESC")
    patients_list = cur.fetchall(); cur.close(); conn.close()
    default_date = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
    default_doc = session.get("user") if session.get("role") == "Doctor" else "Dr. Rajesh Gupta"

    return render_template("add_follow_up.html",
        patients=patients_list,
        selected_patient_id=selected_pid,
        default_date=default_date,
        default_doctor=default_doc
    )


@app.route("/follow_up/status/<int:fuid>")
@require_permission("follow_ups.edit")
def toggle_follow_up_status(fuid):
    new_status = request.args.get("new_status", "Completed")
    redirect_to = request.args.get("redirect", "list")
    if new_status not in ["Scheduled", "Completed", "Cancelled", "Overdue"]:
        flash("Invalid status.", "error")
        return redirect(url_for("follow_ups"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT patient_id FROM follow_ups WHERE follow_up_id = %s", (fuid,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE follow_ups SET status = %s WHERE follow_up_id = %s", (new_status, fuid))
        conn.commit()
        flash(f"Follow-up #FU{fuid:04d} marked as {new_status}.", "success")
    cur.close(); conn.close()

    if redirect_to == "chart" and row:
        return redirect(url_for("patient_chart", pid=row["patient_id"]))
    return redirect(url_for("follow_ups"))


# ═══════════════════════════════════════════════════════════════
# Diagnoses (with Pagination & Search)
# ═══════════════════════════════════════════════════════════════

@app.route("/diagnoses")
@require_permission("diagnoses.view")
def diagnoses():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if q:
        q_like = f"%{q}%"
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM diagnoses d
            JOIN visits v ON d.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE d.disease_name LIKE %s OR p.name LIKE %s
        """, (q_like, q_like))
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT d.*, p.name AS patient_name, p.patient_id, p.gender
            FROM diagnoses d
            JOIN visits v ON d.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE d.disease_name LIKE %s OR p.name LIKE %s
            ORDER BY d.diagnosis_id DESC LIMIT %s OFFSET %s
        """, (q_like, q_like, per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM diagnoses")
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT d.*, p.name AS patient_name, p.patient_id, p.gender
            FROM diagnoses d
            JOIN visits v ON d.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            ORDER BY d.diagnosis_id DESC LIMIT %s OFFSET %s
        """, (per_page, offset))

    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("diagnoses.html",
        diagnoses=data, q=q,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


@app.route("/diagnoses/add", methods=["GET", "POST"])
@require_permission("diagnoses.add")
def add_diagnosis():
    if request.method == "POST":
        visit_id     = int(request.form["visit_id"])
        disease_name = request.form["disease_name"].strip()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO diagnoses (visit_id,disease_name) VALUES (%s,%s)", (visit_id, disease_name))
        conn.commit(); cur.close(); conn.close()
        flash("Diagnosis added.", "success")
        return redirect(url_for("diagnoses"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT v.*, p.name AS patient_name, p.gender
        FROM visits v JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id DESC LIMIT 500
    """)
    recent_visits = cur.fetchall(); cur.close(); conn.close()
    return render_template("add_diagnosis.html", visits=recent_visits)


# ═══════════════════════════════════════════════════════════════
# Lab Results (with Pagination & Search)
# ═══════════════════════════════════════════════════════════════

@app.route("/lab_results")
@require_permission("labs.view")
def lab_results():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if q:
        q_like = f"%{q}%"
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM lab_results l
            JOIN visits v ON l.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE l.test_name LIKE %s OR p.name LIKE %s
        """, (q_like, q_like))
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT l.*, p.name AS patient_name, p.patient_id, p.gender
            FROM lab_results l
            JOIN visits v ON l.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE l.test_name LIKE %s OR p.name LIKE %s
            ORDER BY l.lab_id DESC LIMIT %s OFFSET %s
        """, (q_like, q_like, per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM lab_results")
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT l.*, p.name AS patient_name, p.patient_id, p.gender
            FROM lab_results l
            JOIN visits v ON l.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            ORDER BY l.lab_id DESC LIMIT %s OFFSET %s
        """, (per_page, offset))

    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("lab_results.html",
        labs=data, q=q,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


@app.route("/lab_results/add", methods=["GET", "POST"])
@require_permission("labs.add")
def add_lab():
    if request.method == "POST":
        visit_id     = int(request.form["visit_id"])
        test_name    = request.form["test_name"].strip()
        result_value = request.form["result_value"].strip()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lab_results (visit_id,test_name,result_value) VALUES (%s,%s,%s)",
            (visit_id, test_name, result_value)
        )
        conn.commit(); cur.close(); conn.close()
        flash("Lab result added.", "success")
        return redirect(url_for("lab_results"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT v.*, p.name AS patient_name, p.gender
        FROM visits v JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id DESC LIMIT 500
    """)
    recent_visits = cur.fetchall(); cur.close(); conn.close()
    return render_template("add_lab.html", visits=recent_visits)


# ═══════════════════════════════════════════════════════════════
# Medications (with Pagination & Search)
# ═══════════════════════════════════════════════════════════════

@app.route("/medications")
@require_permission("medications.view")
def medications():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 25

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if q:
        q_like = f"%{q}%"
        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM medications m
            JOIN visits v ON m.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE m.drug_name LIKE %s OR p.name LIKE %s
        """, (q_like, q_like))
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT m.*, p.name AS patient_name, p.patient_id, p.gender
            FROM medications m
            JOIN visits v ON m.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            WHERE m.drug_name LIKE %s OR p.name LIKE %s
            ORDER BY m.med_id DESC LIMIT %s OFFSET %s
        """, (q_like, q_like, per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS cnt FROM medications")
        total_items = cur.fetchone()["cnt"]
        page, total_pages, offset, page_range = paginate(total_items, page, per_page)
        cur.execute("""
            SELECT m.*, p.name AS patient_name, p.patient_id, p.gender
            FROM medications m
            JOIN visits v ON m.visit_id=v.visit_id
            JOIN patients p ON v.patient_id=p.patient_id
            ORDER BY m.med_id DESC LIMIT %s OFFSET %s
        """, (per_page, offset))

    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("medications.html",
        meds=data, q=q,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


@app.route("/medications/add", methods=["GET", "POST"])
@require_permission("medications.add")
def add_medication():
    if request.method == "POST":
        visit_id  = int(request.form["visit_id"])
        drug_name = request.form["drug_name"].strip()
        dosage    = request.form["dosage"].strip()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO medications (visit_id,drug_name,dosage) VALUES (%s,%s,%s)",
            (visit_id, drug_name, dosage)
        )
        conn.commit(); cur.close(); conn.close()
        flash("Medication prescribed.", "success")
        return redirect(url_for("medications"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT v.*, p.name AS patient_name, p.gender
        FROM visits v JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id DESC LIMIT 500
    """)
    recent_visits = cur.fetchall(); cur.close(); conn.close()
    return render_template("add_medication.html", visits=recent_visits)


# ═══════════════════════════════════════════════════════════════
# Full EHR (with Pagination)
# ═══════════════════════════════════════════════════════════════

@app.route("/ehr")
@require_permission("ehr.view")
def ehr():
    page = int(request.args.get("page", 1))
    per_page = 20

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM patients p
        JOIN visits v      ON p.patient_id = v.patient_id
        JOIN diagnoses d   ON v.visit_id   = d.visit_id
        JOIN lab_results l ON v.visit_id   = l.visit_id
        JOIN medications m ON v.visit_id   = m.visit_id
    """)
    total_items = cur.fetchone()["cnt"]
    page, total_pages, offset, page_range = paginate(total_items, page, per_page)

    cur.execute("""
        SELECT
            p.patient_id, p.name, p.age, p.gender,
            v.visit_id, v.visit_date, v.doctor_name,
            d.disease_name,
            l.test_name, l.result_value,
            m.drug_name, m.dosage
        FROM patients p
        JOIN visits v      ON p.patient_id = v.patient_id
        JOIN diagnoses d   ON v.visit_id   = d.visit_id
        JOIN lab_results l ON v.visit_id   = l.visit_id
        JOIN medications m ON v.visit_id   = m.visit_id
        ORDER BY v.visit_date DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    records = cur.fetchall(); cur.close(); conn.close()

    return render_template("ehr.html",
        records=records,
        page=page, total_pages=total_pages,
        total_items=total_items, per_page=per_page,
        page_range=page_range
    )


# ═══════════════════════════════════════════════════════════════
# Analytics
# ═══════════════════════════════════════════════════════════════

@app.route("/analytics")
@require_permission("analytics.view")
def analytics():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT gender, COUNT(*) AS count FROM patients GROUP BY gender ORDER BY count DESC")
    gender_dist = cur.fetchall()
    cur.execute("""
        SELECT disease_name AS disease, COUNT(*) AS count
        FROM diagnoses GROUP BY disease_name ORDER BY count DESC LIMIT 10
    """)
    top_diseases = cur.fetchall()
    cur.execute("""
        SELECT
          CASE
            WHEN age < 18  THEN '0–17  Pediatric'
            WHEN age < 30  THEN '18–29 Young Adult'
            WHEN age < 45  THEN '30–44 Adult'
            WHEN age < 60  THEN '45–59 Middle-Aged'
            ELSE                '60+   Senior'
          END AS `group`,
          COUNT(*) AS count
        FROM patients GROUP BY `group` ORDER BY MIN(age)
    """)
    age_groups = cur.fetchall()
    cur.execute("""
        SELECT drug_name AS drug, COUNT(*) AS count
        FROM medications GROUP BY drug_name ORDER BY count DESC LIMIT 10
    """)
    top_meds = list(enumerate(cur.fetchall()))
    cur.close(); conn.close()

    return render_template("analytics.html",
        stats=get_stats(), gender_dist=gender_dist,
        top_diseases=top_diseases, age_groups=age_groups, top_meds=top_meds
    )


# ═══════════════════════════════════════════════════════════════
# Admin – User Management
# ═══════════════════════════════════════════════════════════════

@app.route("/admin/users")
@require_permission("admin.users")
def admin_users():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users ORDER BY user_id")
    users = cur.fetchall(); cur.close(); conn.close()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@require_permission("admin.users")
def admin_add_user():
    username = request.form["username"].strip()
    password = request.form["password"].strip()
    role     = request.form["role"].strip()

    if not username or not password or not role:
        flash("All fields required.", "error")
        return redirect(url_for("admin_users"))

    if role not in ROLE_PERMISSIONS:
        flash(f"Invalid role. Allowed roles: {', '.join(ROLE_PERMISSIONS.keys())}", "error")
        return redirect(url_for("admin_users"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, role, is_active) VALUES (%s, %s, %s, 1)",
            (username, password, role)
        )
        conn.commit()
        flash(f"User '{username}' created with role '{role}'.", "success")
    except Exception as e:
        flash(f"Error creating user: {e}", "error")
    finally:
        cur.close(); conn.close()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/toggle/<int:uid>")
@require_permission("admin.users")
def admin_toggle_user(uid):
    if uid == 1:
        flash("Cannot deactivate the primary admin account.", "error")
        return redirect(url_for("admin_users"))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT username, is_active FROM users WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    if row:
        new_state = 0 if row["is_active"] else 1
        cur.execute("UPDATE users SET is_active=%s WHERE user_id=%s", (new_state, uid))
        conn.commit()
        state_label = "activated" if new_state else "deactivated"
        flash(f"User '{row['username']}' {state_label}.", "success")
    cur.close(); conn.close()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:uid>")
@require_permission("admin.users")
def admin_delete_user(uid):
    if uid == 1:
        flash("Cannot delete the primary admin account.", "error")
        return redirect(url_for("admin_users"))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT username FROM users WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))
        conn.commit()
        flash(f"User '{row['username']}' deleted.", "success")
    cur.close(); conn.close()
    return redirect(url_for("admin_users"))


# ═══════════════════════════════════════════════════════════════
# Prescription / Print Route
# ═══════════════════════════════════════════════════════════════

@app.route("/prescription/<int:vid>")
@require_permission("medications.view")
def print_prescription(vid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT v.visit_id, v.visit_date, v.doctor_name,
               p.patient_id, p.name, p.age, p.gender, p.contact
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE v.visit_id = %s
    """, (vid,))
    visit_row = cur.fetchone()

    if not visit_row:
        cur.close(); conn.close()
        flash("Visit record not found.", "error")
        return redirect(url_for("patients"))

    patient = {
        "patient_id": visit_row["patient_id"],
        "name": visit_row["name"],
        "age": visit_row["age"],
        "gender": visit_row["gender"],
        "contact": visit_row["contact"],
    }
    visit = {
        "visit_id": visit_row["visit_id"],
        "visit_date": visit_row["visit_date"],
        "doctor_name": visit_row["doctor_name"],
    }

    cur.execute("SELECT disease_name FROM diagnoses WHERE visit_id = %s", (vid,))
    diagnoses = cur.fetchall()

    cur.execute("SELECT drug_name, dosage FROM medications WHERE visit_id = %s", (vid,))
    meds_list = cur.fetchall()
    medications = list(enumerate(meds_list))

    cur.execute("SELECT test_name, result_value FROM lab_results WHERE visit_id = %s", (vid,))
    labs = cur.fetchall()

    # Fetch billing invoice if exists
    cur.execute("SELECT * FROM billing_invoices WHERE visit_id = %s", (vid,))
    invoice = cur.fetchone()

    cur.close(); conn.close()

    portal_url = request.host_url.rstrip("/")
    wa_msg = compose_prescription_whatsapp_message(patient, visit, diagnoses, meds_list, invoice, portal_url=portal_url)
    whatsapp_link = build_whatsapp_link(patient["contact"], wa_msg)

    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return render_template(
        "prescription_print.html",
        patient=patient,
        visit=visit,
        diagnoses=diagnoses,
        medications=medications,
        labs=labs,
        invoice=invoice,
        whatsapp_link=whatsapp_link,
        now=now_str
    )


# ═══════════════════════════════════════════════════════════════
# Direct WhatsApp Send Triggers
# ═══════════════════════════════════════════════════════════════

@app.route("/prescription/whatsapp/<int:vid>")
@require_permission("medications.view")
def send_prescription_whatsapp(vid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT v.visit_id, v.visit_date, v.doctor_name,
               p.patient_id, p.name, p.age, p.gender, p.contact
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        WHERE v.visit_id = %s
    """, (vid,))
    visit_row = cur.fetchone()
    if not visit_row:
        cur.close(); conn.close()
        flash("Visit record not found.", "error")
        return redirect(url_for("patients"))

    patient = {
        "patient_id": visit_row["patient_id"],
        "name": visit_row["name"],
        "contact": visit_row["contact"],
    }
    visit = {
        "visit_id": visit_row["visit_id"],
        "visit_date": visit_row["visit_date"],
        "doctor_name": visit_row["doctor_name"],
    }

    cur.execute("SELECT disease_name FROM diagnoses WHERE visit_id = %s", (vid,))
    diagnoses = cur.fetchall()
    cur.execute("SELECT drug_name, dosage FROM medications WHERE visit_id = %s", (vid,))
    meds_list = cur.fetchall()
    cur.execute("SELECT * FROM billing_invoices WHERE visit_id = %s", (vid,))
    invoice = cur.fetchone()
    cur.close(); conn.close()

    portal_url = request.host_url.rstrip("/")
    if not patient["contact"] or not "".join(filter(str.isdigit, str(patient["contact"]))):
        flash(f"Patient {patient['name']} does not have a registered contact number. Please update their chart demographics.", "error")
        return redirect(url_for("patient_chart", pid=patient["patient_id"]))

    msg = compose_prescription_whatsapp_message(patient, visit, diagnoses, meds_list, invoice, portal_url=portal_url)
    wa_url = build_whatsapp_link(patient["contact"], msg)
    return redirect(wa_url)


@app.route("/follow_up/whatsapp/<int:fuid>")
@require_permission("follow_ups.view")
def send_followup_whatsapp(fuid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT f.*, p.name, p.contact, p.patient_id
        FROM follow_ups f
        JOIN patients p ON f.patient_id = p.patient_id
        WHERE f.follow_up_id = %s
    """, (fuid,))
    row = cur.fetchone()
    cur.close(); conn.close()

    if not row:
        flash("Follow-up record not found.", "error")
        return redirect(url_for("follow_ups"))

    patient = {
        "name": row["name"],
        "contact": row["contact"],
        "patient_id": row["patient_id"],
    }
    follow_up = {
        "follow_up_id": row["follow_up_id"],
        "scheduled_date": row["scheduled_date"],
        "follow_up_type": row["follow_up_type"],
        "priority": row["priority"],
        "doctor_name": row["doctor_name"],
        "notes": row["notes"],
    }

    if not patient["contact"] or not "".join(filter(str.isdigit, str(patient["contact"]))):
        flash(f"Patient {patient['name']} does not have a registered phone number. Please update demographics.", "error")
        return redirect(url_for("follow_ups"))

    portal_url = request.host_url.rstrip("/")
    msg = compose_followup_whatsapp_message(patient, follow_up, portal_url=portal_url)
    wa_url = build_whatsapp_link(patient["contact"], msg)
    return redirect(wa_url)


# ═══════════════════════════════════════════════════════════════
# Hospital Billing & Invoices
# ═══════════════════════════════════════════════════════════════

@app.route("/bill/<int:inv_id>")
@require_permission("patients.view")
def view_bill(inv_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT i.*, p.name, p.age, p.gender, p.contact, v.doctor_name, v.visit_date
        FROM billing_invoices i
        JOIN patients p ON i.patient_id = p.patient_id
        JOIN visits v ON i.visit_id = v.visit_id
        WHERE i.invoice_id = %s
    """, (inv_id,))
    row = cur.fetchone()

    if not row:
        cur.close(); conn.close()
        flash("Invoice not found.", "error")
        return redirect(url_for("patients"))

    cur.execute("SELECT disease_name FROM diagnoses WHERE visit_id = %s", (row["visit_id"],))
    diagnoses = cur.fetchall()
    cur.execute("SELECT drug_name, dosage FROM medications WHERE visit_id = %s", (row["visit_id"],))
    meds_list = cur.fetchall()
    cur.close(); conn.close()

    patient = {
        "patient_id": row["patient_id"],
        "name": row["name"],
        "age": row["age"],
        "gender": row["gender"],
        "contact": row["contact"],
    }
    visit = {
        "visit_id": row["visit_id"],
        "visit_date": row["visit_date"],
        "doctor_name": row["doctor_name"],
    }

    portal_url = request.host_url.rstrip("/")
    wa_msg = compose_prescription_whatsapp_message(patient, visit, diagnoses, meds_list, row, portal_url=portal_url)
    whatsapp_link = build_whatsapp_link(patient["contact"], wa_msg)

    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    return render_template(
        "bill_print.html",
        invoice=row,
        patient=patient,
        visit=visit,
        whatsapp_link=whatsapp_link,
        now=now_str
    )


@app.route("/bill/visit/<int:vid>")
@require_permission("patients.view")
def view_bill_by_visit(vid):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT invoice_id FROM billing_invoices WHERE visit_id = %s", (vid,))
    row = cur.fetchone()
    cur.close(); conn.close()

    if row:
        return redirect(url_for("view_bill", inv_id=row["invoice_id"]))
    flash("No invoice found for this visit.", "error")
    return redirect(url_for("patient_chart", pid=vid))



# ═══════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)
