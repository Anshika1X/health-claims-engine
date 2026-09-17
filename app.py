"""
Automated Health & Insurance Claims Processing Engine
Enterprise Edition — Python Flask REST API & SQLite Relational Ledger
"""

import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_SORT_KEYS"] = False


def get_db_connection(immediate=False):
    """
    Establish a connection to the SQLite database with dict-like row access.
    Enforces foreign-key constraints.
    If immediate=True, initiates a BEGIN IMMEDIATE transaction to prevent write-write race conditions.
    """
    # isolation_level=None allows manual transaction management (BEGIN IMMEDIATE / COMMIT / ROLLBACK)
    conn = sqlite3.connect(DATABASE_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if immediate:
        conn.execute("BEGIN IMMEDIATE;")
    return conn


def cents_to_dollars(cents):
    """Convert integer cents to floating-point dollar representation."""
    return round(cents / 100.0, 2)


def dollars_to_cents(dollars):
    """Safely convert dollar input to exact integer cents."""
    return int(round(float(dollars) * 100))


def init_db(reset=False):
    """
    Initialize SQLite relational tables and populate seed data.
    Uses integer cents for all financial figures to guarantee mathematical accuracy.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if reset:
        cursor.execute("DROP TABLE IF EXISTS audit_logs;")
        cursor.execute("DROP TABLE IF EXISTS claims;")
        cursor.execute("DROP TABLE IF EXISTS policies;")

    # Table 1: Policies (Policy holders & coverage ledger)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id TEXT PRIMARY KEY,
            patient_name TEXT NOT NULL,
            policy_type TEXT NOT NULL,
            policy_status TEXT NOT NULL CHECK(policy_status IN ('Active', 'Inactive')),
            coverage_limit_cents INTEGER NOT NULL CHECK(coverage_limit_cents >= 0),
            coverage_used_cents INTEGER NOT NULL DEFAULT 0 CHECK(coverage_used_cents >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Table 2: Claims (Processed claim transactions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT NOT NULL,
            hospital_name TEXT NOT NULL,
            claim_category TEXT NOT NULL DEFAULT 'Inpatient Medical',
            claim_amount_cents INTEGER NOT NULL CHECK(claim_amount_cents > 0),
            status TEXT NOT NULL CHECK(status IN ('Approved', 'Rejected')),
            rejection_reason TEXT,
            rule_1_passed INTEGER NOT NULL CHECK(rule_1_passed IN (0, 1)),
            rule_2_passed INTEGER NOT NULL CHECK(rule_2_passed IN (0, 1)),
            previous_coverage_cents INTEGER NOT NULL,
            new_coverage_cents INTEGER NOT NULL,
            remarks TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (policy_id) REFERENCES policies(policy_id) ON DELETE CASCADE
        );
    """)

    # Table 3: Audit Logs (Append-only audit trail for compliance)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            policy_id TEXT,
            claim_id INTEGER,
            event_details TEXT NOT NULL,
            ip_address TEXT DEFAULT '127.0.0.1',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE SET NULL
        );
    """)

    # Check if seed policies exist
    cursor.execute("SELECT COUNT(*) FROM policies;")
    count = cursor.fetchone()[0]

    if count == 0:
        # Seed policies: amounts in exact integer cents
        seed_policies = [
            ("P101", "John Doe", "Comprehensive Gold", "Active", 50000000, 2500000),       # Limit: $500k, Used: $25k, Remaining: $475k
            ("P102", "Jane Smith", "Standard Silver", "Inactive", 30000000, 0),             # Limit: $300k, Used: $0, Remaining: $300k (Inactive)
            ("P103", "Robert Taylor", "Emergency Care", "Active", 5000000, 0),              # Limit: $50k, Used: $0, Remaining: $50k
            ("P104", "Emily Davis", "Platinum Family", "Active", 100000000, 0),             # Limit: $1M, Used: $0, Remaining: $1M
        ]
        cursor.executemany("""
            INSERT INTO policies (policy_id, patient_name, policy_type, policy_status, coverage_limit_cents, coverage_used_cents)
            VALUES (?, ?, ?, ?, ?, ?);
        """, seed_policies)

        # Seed initial historical approved claim for P101
        cursor.execute("""
            INSERT INTO claims (
                policy_id, hospital_name, claim_category, claim_amount_cents,
                status, rejection_reason, rule_1_passed, rule_2_passed,
                previous_coverage_cents, new_coverage_cents, remarks, created_at
            ) VALUES (
                'P101', 'St. Jude Memorial Hospital', 'Inpatient Medical', 2500000,
                'Approved', NULL, 1, 1,
                50000000, 47500000,
                'Initial consultation & diagnostic scans approved under automated adjudication.',
                datetime('now', '-2 hours')
            );
        """)
        claim_id = cursor.lastrowid

        # Insert audit log for the initial seed claim
        cursor.execute("""
            INSERT INTO audit_logs (event_type, policy_id, claim_id, event_details)
            VALUES (
                'INITIAL_CLAIM_SETTLED',
                'P101',
                ?,
                'Initial seed claim #1 of $25,000.00 approved and coverage deducted.'
            );
        """, (claim_id,))

        cursor.execute("""
            INSERT INTO audit_logs (event_type, policy_id, event_details)
            VALUES ('SYSTEM_INIT', NULL, 'Database initialized and seeded with enterprise test policies.');
        """)

    conn.close()


# Initialize database on module startup
init_db()


@app.route("/")
def index():
    """Serve the single-page application dashboard."""
    return render_template("index.html")


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """
    Retrieve live aggregate statistics directly from SQLite for the executive KPI dashboard.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM claims;")
    total_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'Approved';")
    approved_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'Rejected';")
    rejected_claims = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(claim_amount_cents), 0) FROM claims;")
    total_claimed_cents = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(claim_amount_cents), 0) FROM claims WHERE status = 'Approved';")
    total_approved_cents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM policies WHERE policy_status = 'Active';")
    active_policies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM policies;")
    total_policies = cursor.fetchone()[0]

    conn.close()

    approval_rate = round((approved_claims / total_claims * 100), 1) if total_claims > 0 else 0.0

    return jsonify({
        "success": True,
        "total_claims": total_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "approval_rate": approval_rate,
        "total_amount_claimed": cents_to_dollars(total_claimed_cents),
        "total_amount_approved": cents_to_dollars(total_approved_cents),
        "active_policies": active_policies,
        "total_policies": total_policies
    }), 200


@app.route("/api/policies", methods=["GET"])
def get_policies():
    """
    Retrieve all registered policies with real-time calculated remaining coverage.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT policy_id, patient_name, policy_type, policy_status,
               coverage_limit_cents, coverage_used_cents,
               (coverage_limit_cents - coverage_used_cents) AS remaining_coverage_cents,
               created_at
        FROM policies
        ORDER BY policy_id ASC;
    """)
    rows = cursor.fetchall()
    conn.close()

    policies = []
    for r in rows:
        rem_cents = r["remaining_coverage_cents"]
        limit_cents = r["coverage_limit_cents"]
        used_cents = r["coverage_used_cents"]
        pct = round((rem_cents / limit_cents * 100), 1) if limit_cents > 0 else 0.0

        policies.append({
            "policy_id": r["policy_id"],
            "patient_name": r["patient_name"],
            "policy_type": r["policy_type"],
            "policy_status": r["policy_status"],
            "coverage_limit": cents_to_dollars(limit_cents),
            "coverage_used": cents_to_dollars(used_cents),
            "remaining_coverage": cents_to_dollars(rem_cents),
            "remaining_percent": pct,
            "created_at": r["created_at"]
        })

    return jsonify({"success": True, "count": len(policies), "policies": policies}), 200


@app.route("/api/policies/<policy_id>", methods=["GET"])
def get_policy(policy_id):
    """
    Look up an individual policy from SQLite. Used by the frontend for live pre-submission preview.
    """
    p_id = str(policy_id).strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT policy_id, patient_name, policy_type, policy_status,
               coverage_limit_cents, coverage_used_cents,
               (coverage_limit_cents - coverage_used_cents) AS remaining_coverage_cents,
               created_at
        FROM policies
        WHERE policy_id = ?;
    """, (p_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({
            "success": False,
            "error": f"Policy '{p_id}' not found in registered policy database."
        }), 404

    rem_cents = row["remaining_coverage_cents"]
    limit_cents = row["coverage_limit_cents"]
    pct = round((rem_cents / limit_cents * 100), 1) if limit_cents > 0 else 0.0

    return jsonify({
        "success": True,
        "policy": {
            "policy_id": row["policy_id"],
            "patient_name": row["patient_name"],
            "policy_type": row["policy_type"],
            "policy_status": row["policy_status"],
            "coverage_limit": cents_to_dollars(limit_cents),
            "coverage_used": cents_to_dollars(row["coverage_used_cents"]),
            "remaining_coverage": cents_to_dollars(rem_cents),
            "remaining_percent": pct,
            "created_at": row["created_at"]
        }
    }), 200


@app.route("/api/claims", methods=["GET"])
def get_claims():
    """
    Retrieve all processed claims ordered by latest submission.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.claim_id, c.policy_id, p.patient_name, c.hospital_name,
               c.claim_category, c.claim_amount_cents, c.status,
               c.rejection_reason, c.rule_1_passed, c.rule_2_passed,
               c.previous_coverage_cents, c.new_coverage_cents,
               c.remarks, c.created_at
        FROM claims c
        LEFT JOIN policies p ON c.policy_id = p.policy_id
        ORDER BY c.claim_id DESC;
    """)
    rows = cursor.fetchall()
    conn.close()

    claims = []
    for r in rows:
        claims.append({
            "claim_id": r["claim_id"],
            "policy_id": r["policy_id"],
            "patient_name": r["patient_name"] or "Unknown",
            "hospital_name": r["hospital_name"],
            "claim_category": r["claim_category"],
            "claim_amount": cents_to_dollars(r["claim_amount_cents"]),
            "status": r["status"],
            "rejection_reason": r["rejection_reason"],
            "rule_1_passed": bool(r["rule_1_passed"]),
            "rule_2_passed": bool(r["rule_2_passed"]),
            "previous_coverage": cents_to_dollars(r["previous_coverage_cents"]),
            "remaining_coverage": cents_to_dollars(r["new_coverage_cents"]),
            "remarks": r["remarks"],
            "created_at": r["created_at"]
        })

    return jsonify({"success": True, "count": len(claims), "claims": claims}), 200


@app.route("/api/claims/<int:claim_id>", methods=["GET"])
def get_claim_detail(claim_id):
    """
    Retrieve full details for an individual claim, including its append-only audit trail.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, p.patient_name, p.policy_type, p.policy_status
        FROM claims c
        LEFT JOIN policies p ON c.policy_id = p.policy_id
        WHERE c.claim_id = ?;
    """, (claim_id,))
    claim = cursor.fetchone()

    if not claim:
        conn.close()
        return jsonify({"success": False, "error": f"Claim #{claim_id} not found."}), 404

    # Fetch audit logs associated with this claim or policy
    cursor.execute("""
        SELECT log_id, event_type, event_details, timestamp
        FROM audit_logs
        WHERE claim_id = ? OR (policy_id = ? AND timestamp <= ?)
        ORDER BY log_id DESC
        LIMIT 10;
    """, (claim_id, claim["policy_id"], claim["created_at"]))
    audit_logs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "success": True,
        "claim": {
            "claim_id": claim["claim_id"],
            "policy_id": claim["policy_id"],
            "patient_name": claim["patient_name"] or "Unknown",
            "policy_type": claim["policy_type"] or "N/A",
            "policy_status": claim["policy_status"] or "Unknown",
            "hospital_name": claim["hospital_name"],
            "claim_category": claim["claim_category"],
            "claim_amount": cents_to_dollars(claim["claim_amount_cents"]),
            "status": claim["status"],
            "rejection_reason": claim["rejection_reason"],
            "rule_1_passed": bool(claim["rule_1_passed"]),
            "rule_2_passed": bool(claim["rule_2_passed"]),
            "previous_coverage": cents_to_dollars(claim["previous_coverage_cents"]),
            "remaining_coverage": cents_to_dollars(claim["new_coverage_cents"]),
            "remarks": claim["remarks"],
            "created_at": claim["created_at"]
        },
        "audit_logs": audit_logs
    }), 200


@app.route("/api/claims/process", methods=["POST"])
def process_claim():
    """
    Automated Claims Processing & Adjudication Engine
    
    Adjudication Flow:
    1. Input sanitization & monetary conversion to integer cents.
    2. Atomic lock via BEGIN IMMEDIATE transaction on SQLite.
    3. Policy lookup in database.
    4. Rule 1 Check: Policy status must be 'Active'.
    5. Rule 2 Check: Claim amount must not exceed remaining coverage.
    6. If Approved:
       - Update policy coverage_used_cents += claim_amount_cents
       - Insert claim record (Status = 'Approved')
       - Insert append-only audit log entry
       - Commit transaction
    7. If Rejected:
       - Insert claim record (Status = 'Rejected')
       - Store exact rejection reason
       - Insert append-only audit log entry
       - Coverage is NOT modified
       - Commit transaction
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request. Expected application/json body."
        }), 400

    policy_id = str(data.get("policy_id") or data.get("patient_id") or "").strip().upper()
    hospital_name = str(data.get("hospital_name", "")).strip()
    claim_category = str(data.get("claim_category", "Inpatient Medical")).strip()
    claim_amount_raw = data.get("claim_amount")

    # Basic Validation
    if not policy_id:
        return jsonify({"success": False, "error": "Field 'policy_id' (or 'patient_id') is required."}), 400
    if not hospital_name:
        return jsonify({"success": False, "error": "Field 'hospital_name' is required."}), 400
    if claim_amount_raw is None:
        return jsonify({"success": False, "error": "Field 'claim_amount' is required."}), 400

    try:
        claim_amount_float = float(claim_amount_raw)
        if claim_amount_float <= 0:
            return jsonify({"success": False, "error": "Claim amount must be strictly greater than $0.00."}), 400
        claim_amount_cents = dollars_to_cents(claim_amount_float)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Field 'claim_amount' must be a valid numeric amount."}), 400

    # Start atomic transaction with immediate write lock
    conn = get_db_connection(immediate=True)
    cursor = conn.cursor()

    try:
        # 1. Fetch policy with write intent
        cursor.execute("""
            SELECT policy_id, patient_name, policy_type, policy_status,
                   coverage_limit_cents, coverage_used_cents
            FROM policies
            WHERE policy_id = ?;
        """, (policy_id,))
        policy = cursor.fetchone()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip = request.remote_addr or "127.0.0.1"

        # Case A: Policy Not Registered
        if not policy:
            rejection_reason = f"Policy ID '{policy_id}' not found in registered policy database."
            
            # Since foreign key policy_id is required, we do not violate foreign key:
            # We record an audit log for the unregistered attempt
            cursor.execute("""
                INSERT INTO audit_logs (event_type, policy_id, event_details, ip_address, timestamp)
                VALUES ('CLAIM_REJECTED_UNREGISTERED', ?, ?, ?, ?);
            """, (policy_id, rejection_reason, client_ip, now_str))

            conn.execute("COMMIT;")
            conn.close()

            return jsonify({
                "success": True,
                "status": "Rejected",
                "claim_id": None,
                "policy_id": policy_id,
                "patient_name": "Unregistered",
                "hospital_name": hospital_name,
                "claim_amount": cents_to_dollars(claim_amount_cents),
                "previous_coverage": 0.0,
                "remaining_coverage": 0.0,
                "rule_evaluations": {
                    "rule_1_policy_active": {
                        "passed": False,
                        "status": "NotFound",
                        "message": "Policy record not found in system."
                    },
                    "rule_2_within_limit": {
                        "passed": False,
                        "claim_amount": cents_to_dollars(claim_amount_cents),
                        "available_limit": 0.0,
                        "message": "Cannot evaluate coverage limit for non-existent policy."
                    }
                },
                "remarks": rejection_reason,
                "timestamp": now_str
            }), 200

        # Extract values
        patient_name = policy["patient_name"]
        policy_status = policy["policy_status"]
        limit_cents = policy["coverage_limit_cents"]
        used_cents = policy["coverage_used_cents"]
        available_cents = limit_cents - used_cents

        # Evaluate Rule 1: Policy must be Active
        rule_1_passed = (policy_status == "Active")

        # Evaluate Rule 2: Claim amount must not exceed available remaining coverage
        rule_2_passed = (claim_amount_cents <= available_cents)

        # Decision Matrix
        if not rule_1_passed:
            status = "Rejected"
            rejection_reason = f"Policy status is '{policy_status}'. Claim rejected under Rule 1 (Active Policy Required)."
            new_coverage_cents = available_cents
            remarks = rejection_reason
            rule_1_msg = f"Policy status is {policy_status}, expected Active."
            rule_2_msg = "Skipped/Failed due to inactive policy status."

            cursor.execute("""
                INSERT INTO claims (
                    policy_id, hospital_name, claim_category, claim_amount_cents,
                    status, rejection_reason, rule_1_passed, rule_2_passed,
                    previous_coverage_cents, new_coverage_cents, remarks, created_at
                ) VALUES (?, ?, ?, ?, 'Rejected', ?, 0, ?, ?, ?, ?, ?);
            """, (
                policy_id, hospital_name, claim_category, claim_amount_cents,
                rejection_reason, 1 if rule_2_passed else 0,
                available_cents, new_coverage_cents, remarks, now_str
            ))
            claim_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO audit_logs (event_type, policy_id, claim_id, event_details, ip_address, timestamp)
                VALUES ('CLAIM_REJECTED_RULE_1', ?, ?, ?, ?, ?);
            """, (policy_id, claim_id, rejection_reason, client_ip, now_str))

            conn.execute("COMMIT;")

        elif not rule_2_passed:
            status = "Rejected"
            rejection_reason = (
                f"Claim amount (${cents_to_dollars(claim_amount_cents):,.2f}) exceeds remaining "
                f"coverage limit (${cents_to_dollars(available_cents):,.2f}). "
                f"Claim rejected under Rule 2 (Coverage Ceiling Check)."
            )
            new_coverage_cents = available_cents
            remarks = rejection_reason
            rule_1_msg = "Policy is Active."
            rule_2_msg = (
                f"Claim amount (${cents_to_dollars(claim_amount_cents):,.2f}) exceeds "
                f"remaining limit (${cents_to_dollars(available_cents):,.2f})."
            )

            cursor.execute("""
                INSERT INTO claims (
                    policy_id, hospital_name, claim_category, claim_amount_cents,
                    status, rejection_reason, rule_1_passed, rule_2_passed,
                    previous_coverage_cents, new_coverage_cents, remarks, created_at
                ) VALUES (?, ?, ?, ?, 'Rejected', ?, 1, 0, ?, ?, ?, ?);
            """, (
                policy_id, hospital_name, claim_category, claim_amount_cents,
                rejection_reason, available_cents, new_coverage_cents, remarks, now_str
            ))
            claim_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO audit_logs (event_type, policy_id, claim_id, event_details, ip_address, timestamp)
                VALUES ('CLAIM_REJECTED_RULE_2', ?, ?, ?, ?, ?);
            """, (policy_id, claim_id, rejection_reason, client_ip, now_str))

            conn.execute("COMMIT;")

        else:
            # Both Rules Passed -> Atomic Approval & Settlement
            status = "Approved"
            rejection_reason = None
            new_used_cents = used_cents + claim_amount_cents
            new_coverage_cents = available_cents - claim_amount_cents
            remarks = (
                f"Claim approved successfully. Claim amount (${cents_to_dollars(claim_amount_cents):,.2f}) "
                f"settled and deducted from remaining coverage. New balance: ${cents_to_dollars(new_coverage_cents):,.2f}."
            )
            rule_1_msg = "Policy verified Active in database."
            rule_2_msg = f"Claim amount (${cents_to_dollars(claim_amount_cents):,.2f}) is within limit (${cents_to_dollars(available_cents):,.2f})."

            # 1. Update policy coverage_used_cents atomically
            cursor.execute("""
                UPDATE policies
                SET coverage_used_cents = ?
                WHERE policy_id = ?;
            """, (new_used_cents, policy_id))

            # 2. Insert Approved claim record
            cursor.execute("""
                INSERT INTO claims (
                    policy_id, hospital_name, claim_category, claim_amount_cents,
                    status, rejection_reason, rule_1_passed, rule_2_passed,
                    previous_coverage_cents, new_coverage_cents, remarks, created_at
                ) VALUES (?, ?, ?, ?, 'Approved', NULL, 1, 1, ?, ?, ?, ?);
            """, (
                policy_id, hospital_name, claim_category, claim_amount_cents,
                available_cents, new_coverage_cents, remarks, now_str
            ))
            claim_id = cursor.lastrowid

            # 3. Record append-only audit log entry
            audit_msg = (
                f"Claim #{claim_id} approved for ${cents_to_dollars(claim_amount_cents):,.2f}. "
                f"Policy balance adjusted from ${cents_to_dollars(available_cents):,.2f} to ${cents_to_dollars(new_coverage_cents):,.2f}."
            )
            cursor.execute("""
                INSERT INTO audit_logs (event_type, policy_id, claim_id, event_details, ip_address, timestamp)
                VALUES ('CLAIM_APPROVED_SETTLED', ?, ?, ?, ?, ?);
            """, (policy_id, claim_id, audit_msg, client_ip, now_str))

            conn.execute("COMMIT;")

        conn.close()

        return jsonify({
            "success": True,
            "status": status,
            "claim_id": claim_id,
            "policy_id": policy_id,
            "patient_name": patient_name,
            "hospital_name": hospital_name,
            "claim_category": claim_category,
            "claim_amount": cents_to_dollars(claim_amount_cents),
            "previous_coverage": cents_to_dollars(available_cents),
            "remaining_coverage": cents_to_dollars(new_coverage_cents),
            "rule_evaluations": {
                "rule_1_policy_active": {
                    "passed": rule_1_passed,
                    "status": policy_status,
                    "message": rule_1_msg
                },
                "rule_2_within_limit": {
                    "passed": rule_2_passed,
                    "claim_amount": cents_to_dollars(claim_amount_cents),
                    "available_limit": cents_to_dollars(available_cents),
                    "message": rule_2_msg
                }
            },
            "remarks": remarks,
            "timestamp": now_str
        }), 200

    except Exception as e:
        conn.execute("ROLLBACK;")
        conn.close()
        return jsonify({
            "success": False,
            "error": f"Database transaction failed: {str(e)}"
        }), 500


@app.route("/api/reset", methods=["POST"])
def reset_database():
    """
    Factory reset database to clean initial seed data for testing.
    """
    init_db(reset=True)
    return jsonify({
        "success": True,
        "message": "Database successfully reset to initial enterprise seed data."
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting Enterprise Health Claims Engine on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
