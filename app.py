"""
Automated Health & Insurance Claims Processing Engine
Flask REST Backend & SQLite Relational Database Engine
"""

import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_SORT_KEYS"] = False


def get_db_connection():
    """Create and return a database connection with dict-like row access."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(reset=False):
    """
    Initialize SQLite tables and populate seed data.
    If reset is True, drops existing tables and re-seeds.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if reset:
        cursor.execute("DROP TABLE IF EXISTS claims;")
        cursor.execute("DROP TABLE IF EXISTS patients;")

    # Table 1: Patients
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            policy_status TEXT NOT NULL CHECK(policy_status IN ('Active', 'Inactive')),
            coverage_limit REAL NOT NULL CHECK(coverage_limit >= 0),
            initial_coverage REAL NOT NULL CHECK(initial_coverage >= 0)
        );
    """)

    # Table 2: Claims
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            claim_amount REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Approved', 'Rejected')),
            remarks TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed initial dummy data if patients table is empty
    cursor.execute("SELECT COUNT(*) FROM patients;")
    patient_count = cursor.fetchone()[0]

    if patient_count == 0:
        seed_patients = [
            ("P101", "John Doe", "Active", 500000.0, 500000.0),
            ("P102", "Jane Smith", "Inactive", 300000.0, 300000.0),
            ("P103", "Robert Taylor", "Active", 50000.0, 50000.0),
            ("P104", "Emily Davis", "Active", 1000000.0, 1000000.0),
        ]
        cursor.executemany("""
            INSERT INTO patients (patient_id, name, policy_status, coverage_limit, initial_coverage)
            VALUES (?, ?, ?, ?, ?);
        """, seed_patients)

        # Seed sample historical claim
        cursor.execute("""
            INSERT INTO claims (patient_id, hospital_name, claim_amount, status, remarks, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', '-2 hours'));
        """, ("P101", "St. Jude Memorial Hospital", 25000.0, "Approved", "Initial consultation & diagnostic scans approved."))
        
        # Deduct initial historical claim from P101
        cursor.execute("UPDATE patients SET coverage_limit = coverage_limit - 25000.0 WHERE patient_id = 'P101';")

    conn.commit()
    conn.close()


# Initialize database on module load
init_db()


@app.route("/")
def index():
    """Serve the single-page application dashboard."""
    return render_template("index.html")


@app.route("/api/patients", methods=["GET"])
def get_patients():
    """Retrieve all patients with their current policy status and coverage limits."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, name, policy_status, coverage_limit, initial_coverage FROM patients ORDER BY patient_id ASC;")
    patients = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "count": len(patients), "patients": patients}), 200


@app.route("/api/claims", methods=["GET"])
def get_claims():
    """Retrieve all submitted claims with approval status and remarks."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.claim_id, c.patient_id, p.name AS patient_name, c.hospital_name,
               c.claim_amount, c.status, c.remarks, c.created_at
        FROM claims c
        LEFT JOIN patients p ON c.patient_id = p.patient_id
        ORDER BY c.claim_id DESC;
    """)
    claims = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "count": len(claims), "claims": claims}), 200


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Retrieve aggregate engine statistics for the dashboard KPI cards."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM claims;")
    total_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'Approved';")
    approved_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'Rejected';")
    rejected_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(claim_amount), 0) FROM claims;")
    total_amount_claimed = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(claim_amount), 0) FROM claims WHERE status = 'Approved';")
    total_amount_approved = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE policy_status = 'Active';")
    active_policies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients;")
    total_patients = cursor.fetchone()[0]

    conn.close()

    approval_rate = round((approved_claims / total_claims * 100), 1) if total_claims > 0 else 0.0

    return jsonify({
        "success": True,
        "total_claims": total_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "approval_rate": approval_rate,
        "total_amount_claimed": float(total_amount_claimed),
        "total_amount_approved": float(total_amount_approved),
        "active_policies": active_policies,
        "total_patients": total_patients
    }), 200


@app.route("/api/claims/process", methods=["POST"])
def process_claim():
    """
    Automated Claims Processing Engine
    
    Validates incoming claims based on two core business rules:
    - Rule 1: Patient policy status must be 'Active'.
    - Rule 2: Claim amount must not exceed remaining coverage limit.
    
    If both rules pass:
      - Claim is Approved.
      - Claim amount is deducted from coverage limit.
      - Database is updated.
    If any rule fails:
      - Claim is Rejected with specific reason recorded.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request. Expected application/json body."
        }), 400

    patient_id = str(data.get("patient_id", "")).strip().upper()
    hospital_name = str(data.get("hospital_name", "")).strip()
    claim_amount_raw = data.get("claim_amount")

    # Basic input validations
    if not patient_id:
        return jsonify({"success": False, "error": "Field 'patient_id' is required."}), 400
    if not hospital_name:
        return jsonify({"success": False, "error": "Field 'hospital_name' is required."}), 400
    if claim_amount_raw is None:
        return jsonify({"success": False, "error": "Field 'claim_amount' is required."}), 400

    try:
        claim_amount = float(claim_amount_raw)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Field 'claim_amount' must be a valid numeric amount."}), 400

    if claim_amount <= 0:
        return jsonify({"success": False, "error": "Field 'claim_amount' must be greater than zero."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch patient record
    cursor.execute("SELECT patient_id, name, policy_status, coverage_limit, initial_coverage FROM patients WHERE patient_id = ?;", (patient_id,))
    patient = cursor.fetchone()

    now_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # If patient not found in database
    if not patient:
        rejection_reason = f"Patient ID '{patient_id}' not found in registered policy database."
        cursor.execute("""
            INSERT INTO claims (patient_id, hospital_name, claim_amount, status, remarks, created_at)
            VALUES (?, ?, ?, 'Rejected', ?, ?);
        """, (patient_id, hospital_name, claim_amount, rejection_reason, now_timestamp))
        claim_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "status": "Rejected",
            "claim_id": claim_id,
            "patient_id": patient_id,
            "patient_name": "Unknown",
            "hospital_name": hospital_name,
            "claim_amount": claim_amount,
            "previous_coverage": 0.0,
            "remaining_coverage": 0.0,
            "rule_evaluations": {
                "rule_1_policy_active": {
                    "passed": False,
                    "status": "NotFound",
                    "message": "Patient not found in system."
                },
                "rule_2_within_limit": {
                    "passed": False,
                    "claim_amount": claim_amount,
                    "available_limit": 0.0,
                    "message": "Cannot evaluate coverage limit for non-existent patient."
                }
            },
            "remarks": rejection_reason,
            "timestamp": now_timestamp
        }), 200

    policy_status = patient["policy_status"]
    current_limit = float(patient["coverage_limit"])
    patient_name = patient["name"]

    # Rule 1: Check policy status
    rule_1_passed = (policy_status == "Active")

    # Rule 2: Check coverage limit
    rule_2_passed = (claim_amount <= current_limit)

    # Decision Matrix
    if not rule_1_passed:
        status = "Rejected"
        rejection_reason = f"Policy status is '{policy_status}'. Claim rejected under Rule 1 (Active Policy Required)."
        rule_1_msg = f"Policy is {policy_status}, expected Active."
        rule_2_msg = "Skipped/Failed due to inactive policy."
        remaining_coverage = current_limit

        cursor.execute("""
            INSERT INTO claims (patient_id, hospital_name, claim_amount, status, remarks, created_at)
            VALUES (?, ?, ?, 'Rejected', ?, ?);
        """, (patient_id, hospital_name, claim_amount, rejection_reason, now_timestamp))
        claim_id = cursor.lastrowid
        conn.commit()

    elif not rule_2_passed:
        status = "Rejected"
        rejection_reason = (
            f"Claim amount (${claim_amount:,.2f}) exceeds remaining coverage limit (${current_limit:,.2f}). "
            f"Claim rejected under Rule 2 (Coverage Limit Check)."
        )
        rule_1_msg = "Policy is Active."
        rule_2_msg = f"Claim amount (${claim_amount:,.2f}) exceeds remaining limit (${current_limit:,.2f})."
        remaining_coverage = current_limit

        cursor.execute("""
            INSERT INTO claims (patient_id, hospital_name, claim_amount, status, remarks, created_at)
            VALUES (?, ?, ?, 'Rejected', ?, ?);
        """, (patient_id, hospital_name, claim_amount, rejection_reason, now_timestamp))
        claim_id = cursor.lastrowid
        conn.commit()

    else:
        # Both rules passed!
        status = "Approved"
        remaining_coverage = round(current_limit - claim_amount, 2)
        remarks = (
            f"Claim approved successfully. Claim amount (${claim_amount:,.2f}) "
            f"deducted from remaining coverage. New balance: ${remaining_coverage:,.2f}."
        )
        rule_1_msg = "Policy is Active."
        rule_2_msg = f"Claim amount (${claim_amount:,.2f}) is within limit (${current_limit:,.2f})."

        # Update patient coverage limit
        cursor.execute("""
            UPDATE patients
            SET coverage_limit = ?
            WHERE patient_id = ?;
        """, (remaining_coverage, patient_id))

        # Record approved claim
        cursor.execute("""
            INSERT INTO claims (patient_id, hospital_name, claim_amount, status, remarks, created_at)
            VALUES (?, ?, ?, 'Approved', ?, ?);
        """, (patient_id, hospital_name, claim_amount, remarks, now_timestamp))
        claim_id = cursor.lastrowid
        conn.commit()

    conn.close()

    return jsonify({
        "success": True,
        "status": status,
        "claim_id": claim_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "hospital_name": hospital_name,
        "claim_amount": claim_amount,
        "previous_coverage": current_limit,
        "remaining_coverage": remaining_coverage,
        "rule_evaluations": {
            "rule_1_policy_active": {
                "passed": rule_1_passed,
                "status": policy_status,
                "message": rule_1_msg
            },
            "rule_2_within_limit": {
                "passed": rule_2_passed,
                "claim_amount": claim_amount,
                "available_limit": current_limit,
                "message": rule_2_msg
            }
        },
        "remarks": rejection_reason if status == "Rejected" else remarks,
        "timestamp": now_timestamp
    }), 200


@app.route("/api/reset", methods=["POST"])
def reset_database():
    """Reset database to fresh seed values for demonstration and testing."""
    init_db(reset=True)
    return jsonify({
        "success": True,
        "message": "Database successfully reset to initial seed data."
    }), 200


if __name__ == "__main__":
    # Run development server
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting Automated Health Claims Engine on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
