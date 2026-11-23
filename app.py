import os
import secrets
import time
import math
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
from whatsapp_service import (
    format_whatsapp_phone,
    build_whatsapp_link,
    compose_prescription_whatsapp_message,
    compose_followup_whatsapp_message,
)

app = Flask(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Cryptographically Secure Secret Key ──────────────────────
def _get_or_create_secret_key():
    # 1. Highest priority: explicit environment variable
    env_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    # 2. On Vercel / serverless: MUST use a stable deterministic key across all lambda instances.
    # Lambda instances have isolated, non-shared filesystems. Generating keys per instance
    # breaks session decryption across multiple requests.
    if os.environ.get("VERCEL") == "1":
        commit_sha = (
            os.environ.get("VERCEL_GIT_COMMIT_SHA")
            or os.environ.get("VERCEL_DEPLOYMENT_ID")
            or "clinicore-production-stable-session-secret-salt-2026"
        )
        return f"clinicore-{commit_sha}-secret-key"

    # 3. Local persistent development: save to .secret_key in project directory
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secret_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if len(k) >= 32:
                    return k
        except Exception:
            pass

    new_key = secrets.token_hex(32)
    try:
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
        return new_key
    except Exception:
        pass

    return "clinicore-local-dev-stable-secret-key-salt-987"

app.secret_key = _get_or_create_secret_key()

# ── Session & Cookie Security Configuration ─────────────────
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("VERCEL") == "1" or os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # Max 2MB request body to prevent DoS
)

# ── Rate Limiting (Brute-Force Attack Defense) ──────────────
_LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300  # 5 minutes

def check_login_rate_limit(ip: str) -> bool:
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    attempts = [t for t in attempts if now - t < LOGIN_LOCKOUT_SECONDS]
    _LOGIN_ATTEMPTS[ip] = attempts
    return len(attempts) >= MAX_LOGIN_ATTEMPTS

def record_failed_login(ip: str):
    now = time.time()
    attempts = _LOGIN_ATTEMPTS.get(ip, [])
    attempts.append(now)
    _LOGIN_ATTEMPTS[ip] = attempts

def clear_login_attempts(ip: str):
    _LOGIN_ATTEMPTS.pop(ip, None)

# ── CSRF Protection Middleware ──────────────────────────────
def generate_csrf_token() -> str:
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = generate_csrf_token

@app.before_request
def csrf_protect():
    # Bypass session overhead for static assets
    if request.path.startswith("/static"):
        return

    session.permanent = True
    # Exempt /login from CSRF abort to prevent lockout during initial cookie negotiation;
    # login is protected by credentials, session rotation (session.clear()), and IP rate limiting.
    if request.path == "/login" or request.endpoint == "login":
        return

    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        expected = session.get("_csrf_token")
        if not expected or not token or not secrets.compare_digest(str(token), str(expected)):
            abort(403)

def verify_action_csrf():
    """Verify CSRF token for destructive or state-changing actions."""
    token = request.args.get("csrf") or request.form.get("csrf_token")
    expected = session.get("_csrf_token")
    if not expected or not token or not secrets.compare_digest(str(token), str(expected)):
        abort(403)

# ── HTTP Security Headers (OWASP Top 10) ────────────────────
@app.after_request
def apply_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.path.startswith("/static"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif "user" in session:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# ── Safe Input Parsing Helper ───────────────────────────────
def safe_int(value, default=1, min_val=1, max_val=1000000) -> int:
    try:
        val = int(value)
        if val < min_val:
            return min_val
        if val > max_val:
            return max_val
        return val
    except (ValueError, TypeError):
        return default

# ── Custom Error Handlers ───────────────────────────────────
@app.errorhandler(403)
def forbidden_error(e):
    return render_template(
        "error.html",
        error_code="403",
        error_icon="ph-shield-warning",
        error_title="403 — Access Denied",
        error_message="Request validation failed or you do not have permission to access this resource."
    ), 403

@app.errorhandler(404)
def not_found_error(e):
    return render_template(
        "error.html",
        error_code="404",
        error_icon="ph-file-dashed",
        error_title="404 — Page Not Found",
        error_message="The requested page or endpoint does not exist or has been moved."
    ), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template(
        "error.html",
        error_code="500",
        error_icon="ph-warning-octagon",
        error_title="500 — Server Error",
        error_message="An unexpected system or database issue occurred. Please check connectivity and try again."
    ), 500


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
# High-Performance DB Helpers, Multi-Query Optimization & In-Memory Caching
# ═══════════════════════════════════════════════════════════════

_STATS_CACHE = {"data": None, "time": 0}
_SIDEBAR_CACHE = {"counts": (0, 0), "time": 0}

def get_stats():
    now = time.time()
    if _STATS_CACHE["data"] is not None and (now - _STATS_CACHE["time"] < 15):
        return _STATS_CACHE["data"]

    stats = {
        "patients": 0, "visits": 0, "diagnoses": 0, "labs": 0,
        "meds": 0, "follow_ups": 0, "overdue_follow_ups": 0, "avg_age": "—"
    }
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        # Combined single query executes all aggregate metrics in 1 network roundtrip
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM patients) AS patients,
                (SELECT COUNT(*) FROM visits) AS visits,
                (SELECT COUNT(*) FROM diagnoses) AS diagnoses,
                (SELECT COUNT(*) FROM lab_results) AS labs,
                (SELECT COUNT(*) FROM medications) AS meds,
                (SELECT COUNT(*) FROM follow_ups) AS follow_ups,
                (SELECT COUNT(*) FROM follow_ups WHERE status = 'Overdue') AS overdue_follow_ups,
                (SELECT ROUND(AVG(age), 1) FROM patients) AS avg_age
        """)
        row = cur.fetchone()
        if row:
            for k in ["patients", "visits", "diagnoses", "labs", "meds", "follow_ups", "overdue_follow_ups"]:
                stats[k] = row.get(k) or 0
            stats["avg_age"] = str(row["avg_age"]) if row.get("avg_age") else "—"
        cur.close(); conn.close()
        _STATS_CACHE["data"] = stats
        _STATS_CACHE["time"] = now
    except Exception:
        if _STATS_CACHE["data"] is not None:
            return _STATS_CACHE["data"]
    return stats


def get_sidebar_counts():
    """Single query to fetch sidebar counts with 20s TTL cache."""
    now = time.time()
    if now - _SIDEBAR_CACHE["time"] < 20:
        return _SIDEBAR_CACHE["counts"]
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM patients) AS p_cnt,
                (SELECT COUNT(*) FROM follow_ups WHERE status = 'Overdue') AS ov_cnt
        """)
        row = cur.fetchone()
        counts = (row[0] if row else 0, row[1] if row else 0)
        _SIDEBAR_CACHE["counts"] = counts
        _SIDEBAR_CACHE["time"] = now
        cur.close(); conn.close()
        return counts
    except Exception:
        return _SIDEBAR_CACHE["counts"]


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
        p_count, ov_count = get_sidebar_counts()
        base["patient_count"] = p_count
        base["overdue_count"] = ov_count
    else:
        base["patient_count"] = 0
        base["overdue_count"] = 0
    return base


# ═══════════════════════════════════════════════════════════════
# SEO & Static Discovery
# ═══════════════════════════════════════════════════════════════

@app.route("/static/<path:filename>")
def static_files(filename):
    static_dir = os.path.join(app.root_path, "static")
    response = send_from_directory(static_dir, filename)
    # 1 year immutable browser & edge CDN cache
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(app.static_folder, "robots.txt", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory(app.static_folder, "sitemap.xml", mimetype="application/xml")


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or "127.0.0.1"
        )
        if check_login_rate_limit(client_ip):
            return render_template(
                "login.html",
                error="Too many failed login attempts. Temporarily locked for 5 minutes."
            )

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            record_failed_login(client_ip)
            return render_template("login.html", error="Username and password are required.")

        try:
            conn = get_connection()
        except Exception:
            record_failed_login(client_ip)
            return render_template("login.html", error="Database service temporarily unavailable. Please try again shortly."), 503

        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND is_active=1",
            (username,)
        )
        user = cur.fetchone()

        authenticated = False
        needs_hash_upgrade = False

        if user:
            stored_pwd = user.get("password", "")
            if stored_pwd.startswith(("scrypt:", "pbkdf2:")):
                authenticated = check_password_hash(stored_pwd, password)
            elif stored_pwd == password:
                authenticated = True
                needs_hash_upgrade = True

        if authenticated:
            clear_login_attempts(client_ip)
            if needs_hash_upgrade:
                try:
                    new_hash = generate_password_hash(password)
                    cur.execute("UPDATE users SET password=%s WHERE user_id=%s", (new_hash, user["user_id"]))
                    conn.commit()
                except Exception:
                    pass
            cur.close()
            conn.close()

            # Prevent session fixation attacks
            session.clear()
            session["user"] = user["username"]
            session["role"] = user["role"]
            generate_csrf_token()
            flash(f"Signed in as {user['username']} ({user['role']}).", "success")
            return redirect(url_for("index"))
        else:
            record_failed_login(client_ip)
            cur.close()
            conn.close()
            return render_template("login.html", error="Invalid credentials or account inactive.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════

@app.route("/")
@login_required
def index():
    recent_patients = []
    gender_dist = []
    common_diseases = []
    try:
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
    except Exception:
        flash("Database service is currently unreachable. Please check connection settings.", "warning")

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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query patients database. Please verify database connectivity.", "warning")
        data = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO patients (name, age, gender, contact) VALUES (%s,%s,%s,%s)",
                (name, age_int, gender, contact)
            )
            conn.commit(); pid = cur.lastrowid; cur.close(); conn.close()
            flash(f"Patient '{name}' registered successfully (#P{pid:04d}) and added to database.", "success")
            return redirect(url_for("patient_chart", pid=pid))
        except Exception:
            flash("Database error occurred while adding patient.", "error")
            return render_template("add_patient.html", error="Database error occurred.", form=request.form)

    return render_template("add_patient.html", form={})


@app.route("/patient/<int:pid>")
@require_permission("patients.view")
def patient_chart(pid):
    try:
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
    except Exception:
        flash("Database connection error while retrieving patient chart.", "error")
        return redirect(url_for("patients"))


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
    verify_action_csrf()
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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query visits database. Please verify database connectivity.", "warning")
        data = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query follow-ups database. Please verify database connectivity.", "warning")
        rows = []
        counts = {"total": 0, "scheduled": 0, "overdue": 0, "completed": 0}
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    verify_action_csrf()
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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query diagnoses database. Please verify database connectivity.", "warning")
        data = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query lab results database. Please verify database connectivity.", "warning")
        data = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    page = safe_int(request.args.get("page", 1))
    per_page = 25

    try:
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
    except Exception:
        flash("Unable to query medications database. Please verify database connectivity.", "warning")
        data = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    page = safe_int(request.args.get("page", 1))
    per_page = 20

    try:
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
    except Exception:
        flash("Unable to load electronic health records. Please verify database connectivity.", "warning")
        records = []
        total_items = 0
        page, total_pages, offset, page_range = 1, 1, 0, [1]

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
    try:
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
    except Exception:
        flash("Unable to load analytics data. Please verify database connectivity.", "warning")
        gender_dist, top_diseases, age_groups, top_meds = [], [], [], []

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
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users ORDER BY user_id")
        users = cur.fetchall(); cur.close(); conn.close()
    except Exception:
        flash("Unable to query user accounts database.", "warning")
        users = []
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/add", methods=["POST"])
@require_permission("admin.users")
def admin_add_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role     = request.form.get("role", "").strip()

    if not username or not password or not role:
        flash("All fields required.", "error")
        return redirect(url_for("admin_users"))

    if len(password) < 8:
        flash("Password must be at least 8 characters long for security.", "error")
        return redirect(url_for("admin_users"))

    if role not in ROLE_PERMISSIONS:
        flash(f"Invalid role. Allowed roles: {', '.join(ROLE_PERMISSIONS.keys())}", "error")
        return redirect(url_for("admin_users"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        hashed_password = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password, role, is_active) VALUES (%s, %s, %s, 1)",
            (username, hashed_password, role)
        )
        conn.commit()
        flash(f"User '{username}' created with role '{role}'.", "success")
    except Exception:
        flash("Error creating user: username may already exist.", "error")
    finally:
        cur.close(); conn.close()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/toggle/<int:uid>")
@require_permission("admin.users")
def admin_toggle_user(uid):
    verify_action_csrf()
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
    verify_action_csrf()
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
    try:
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
    except Exception:
        flash("Database error while fetching prescription details.", "error")
        return redirect(url_for("patients"))

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
    try:
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
    except Exception:
        flash("Database error occurred while fetching billing invoice.", "error")
        return redirect(url_for("patients"))

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
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT invoice_id FROM billing_invoices WHERE visit_id = %s", (vid,))
        row = cur.fetchone()
        cur.close(); conn.close()

        if row:
            return redirect(url_for("view_bill", inv_id=row["invoice_id"]))
    except Exception:
        pass
    flash("No invoice found for this visit.", "error")
    return redirect(url_for("patient_chart", pid=vid))



# ═══════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, port=5000)
