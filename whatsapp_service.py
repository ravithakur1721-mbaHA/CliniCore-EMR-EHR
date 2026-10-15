import urllib.parse
from datetime import datetime

def format_whatsapp_phone(contact_raw: str, default_country_code: str = "91") -> str:
    """
    Cleans and verifies phone numbers from the patient database into standard international E.164
    format for direct WhatsApp delivery (e.g. 919876543210).
    Guarantees sending only to the registered number.
    """
    if not contact_raw:
        return ""
    digits = "".join(filter(str.isdigit, str(contact_raw).strip()))
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    elif len(digits) > 10 and digits.startswith("0"):
        return f"{default_country_code}{digits[1:]}"
    elif len(digits) >= 11:
        return digits
    return f"{default_country_code}{digits}" if digits else ""


def build_whatsapp_link(phone: str, text: str) -> str:
    """
    Builds direct WhatsApp Web / App API link locked specifically to the patient's registered phone.
    """
    clean_phone = format_whatsapp_phone(phone)
    if not clean_phone:
        return "#"
    encoded_text = urllib.parse.quote(text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"


def compose_prescription_whatsapp_message(patient, visit, diagnoses, meds, invoice=None, portal_url="http://127.0.0.1:5000"):
    """
    Composes a professional, beautifully formatted hospital WhatsApp message
    containing prescription summary, download link for official print slip, and billing summary.
    """
    rx_ref = f"RX-{visit['visit_id']:06d}"
    rx_url = f"{portal_url}/prescription/{visit['visit_id']}"
    
    msg_lines = [
        "🏥 *CLINICORE GENERAL HOSPITAL* — *EHR / EMR PORTAL*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Dear *{patient['name']}*,",
        f"Here is your official *Digital Prescription* & *Visit Summary* for your consultation with *{visit['doctor_name']}* on *{visit['visit_date']}*.",
        "",
        f"📋 *Prescription Ref:* `{rx_ref}`",
        f"👤 *Patient ID:* `#P{patient['patient_id']:04d}`",
    ]

    # Diagnoses
    if diagnoses:
        dx_str = ", ".join([d["disease_name"] for d in diagnoses])
        msg_lines.append(f"🩺 *Clinical Diagnosis:* {dx_str}")
    
    # Medications
    msg_lines.append("")
    msg_lines.append("💊 *PRESCRIBED MEDICATIONS:*")
    if meds:
        for idx, m in enumerate(meds, 1):
            msg_lines.append(f"  {idx}. *{m['drug_name']}* — {m['dosage']}")
            msg_lines.append(f"     _Instructions: Take as directed. Complete full course._")
    else:
        msg_lines.append("  _No active pharmaceutical prescriptions recorded for this visit._")

    # Invoices & Billing
    if invoice:
        msg_lines.append("")
        msg_lines.append("🧾 *BILLING & INVOICE SUMMARY:*")
        msg_lines.append(f"  • *Invoice No:* `{invoice['invoice_number']}`")
        msg_lines.append(f"  • *Consultation Fee:* ₹{float(invoice['consultation_fee']):.2f}")
        if float(invoice.get('pharmacy_fee', 0)) > 0:
            msg_lines.append(f"  • *Pharmacy Charges:* ₹{float(invoice['pharmacy_fee']):.2f}")
        if float(invoice.get('lab_fee', 0)) > 0:
            msg_lines.append(f"  • *Laboratory Charges:* ₹{float(invoice['lab_fee']):.2f}")
        if float(invoice.get('tax_amount', 0)) > 0:
            msg_lines.append(f"  • *Taxes & Surcharges:* ₹{float(invoice['tax_amount']):.2f}")
        msg_lines.append(f"  • *Total Amount:* *₹{float(invoice['total_amount']):.2f}* ({invoice['payment_status']} via {invoice['payment_method']})")
        inv_url = f"{portal_url}/bill/{invoice['invoice_id']}"
        msg_lines.append(f"  🔗 *View Official Tax Invoice:* {inv_url}")

    # Official Print Link
    msg_lines.append("")
    msg_lines.append("🖨️ *DOWNLOAD & PRINT OFFICIAL PRESCRIPTION PDF:*")
    msg_lines.append(f"👉 {rx_url}")
    msg_lines.append("")
    msg_lines.append("⚠️ _Note: This prescription is valid for 30 days. For emergencies, please visit CliniCore ER immediately._")
    msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg_lines.append("📞 Helpline: +91-1234-567890 | 🌐 clinicore.health")

    return "\n".join(msg_lines)


def compose_followup_whatsapp_message(patient, follow_up, portal_url="http://127.0.0.1:5000"):
    """
    Composes a courteous and critical reminder message for patient review.
    """
    fu_ref = f"FU-{follow_up['follow_up_id']:04d}"
    chart_url = f"{portal_url}/patient/{patient['patient_id']}"

    priority_alert = ""
    if follow_up.get("priority") == "Urgent":
        priority_alert = " 🚨 *URGENT MEDICAL REVIEW*"
    elif follow_up.get("priority") == "High":
        priority_alert = " ⚠️ *HIGH PRIORITY REVIEW*"

    msg_lines = [
        "🏥 *CLINICORE GENERAL HOSPITAL* — *CARE MANAGEMENT*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Dear *{patient['name']}*,",
        f"This is an official clinical reminder regarding your upcoming review consultation{priority_alert}.",
        "",
        f"📅 *Scheduled Date:* *{follow_up['scheduled_date']}*",
        f"🩺 *Review Type:* {follow_up['follow_up_type']}",
        f"👨‍⚕️ *Attending Physician:* {follow_up.get('doctor_name', 'Attending Physician')}",
        f"📋 *Reference No:* `{fu_ref}`",
    ]

    if follow_up.get("notes"):
        msg_lines.append(f"📝 *Physician Instructions:* {follow_up['notes']}")

    msg_lines.append("")
    msg_lines.append(f"🔗 *View Your Patient Portal & Chart:* {chart_url}")
    msg_lines.append("")
    msg_lines.append("To reschedule or confirm your arrival time, reply directly to this message or call our appointment desk.")
    msg_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg_lines.append("📞 Appointments Desk: +91-1234-567890 | 🏥 CliniCore Hospital")

    return "\n".join(msg_lines)
