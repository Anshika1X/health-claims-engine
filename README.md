# 🛡️ Automated Health & Insurance Claims Processing Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask Framework](https://img.shields.io/badge/framework-Flask%203.x-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/database-SQLite3-green.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![API Testing](https://img.shields.io/badge/Postman-Ready-orange.svg)](https://www.postman.com/)

An enterprise-grade, automated medical insurance claims adjudication engine built with **Python (Flask)**, **SQLite**, and a **Single-Page Reactive Dashboard (Vanilla HTML5 / CSS3 / Fetch API)**. The engine evaluates incoming hospital and patient claims in real time against strict policy and coverage business rules, manages atomic financial settlements, and maintains an immutable audit ledger.

---

## 🎯 Executive Overview & Business Logic

The engine automates the manual claims review process by enforcing a deterministic two-rule evaluation matrix:

```
                  ┌───────────────────────────────┐
                  │   Incoming Claim Submission   │
                  │ (Patient ID, Hospital, Amount)│
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                ┌───────────────────────────────────┐
                │ Rule 1: Policy Status Active?    │
                └─────────────────┬─────────────────┘
                         NO       │       YES
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
┌───────────────────────┐             ┌───────────────────────────────────┐
│ REJECT CLAIM (Rule 1) │             │ Rule 2: Amount <= Remaining Limit?│
│  "Policy Inactive"    │             └─────────────────┬─────────────────┘
└───────────────────────┘                      NO       │       YES
                                  ┌─────────────────────┴─────────────────────┐
                                  ▼                                           ▼
                      ┌───────────────────────┐             ┌───────────────────────────────────┐
                      │ REJECT CLAIM (Rule 2) │             │       APPROVE CLAIM & SETTLE      │
                      │   "Exceeds Coverage"  │             │ • Deduct Amount from Policy Limit │
                      └───────────────────────┘             │ • Insert Approved Claim into DB   │
                                                            │ • Commit Atomic Transaction       │
                                                            └───────────────────────────────────┘
```

1. **Rule 1 — Policy Active Status**: Verifies that the patient's policy is active. If marked `Inactive`, the claim is rejected immediately.
2. **Rule 2 — Coverage Limit Ceiling**: Checks whether the requested claim amount is within the patient's available coverage. If the amount exceeds remaining coverage, the claim is rejected.
3. **Automated Settlement & Ledger Update**: When both rules pass, the claim is approved, the claim amount is deducted from the patient's coverage balance via an atomic SQLite transaction, and the full audit trail is recorded.

---

## ✨ Key Capabilities & Engineering Highlights

- **Executive KPI Dashboard**: Live tracking of total claims processed, settled payout totals, approval ratios, and active insured registry health.
- **Live Policy Auto-Lookup & Warning Preview**: Dynamically searches the database as the user types a `Patient ID`, calculating projected post-claim coverage before submission.
- **Visual 4-Stage Adjudication Pipeline**: Step-by-step visual feedback for payload sanitization, Rule 1 check, Rule 2 check, and ledger commitment.
- **Interactive Directory & Audit Log**: Search and filter records in real time by status, patient ID, name, or hospital provider.
- **Adjudication Slip Modal**: Generates a printable voucher slip and JSON view for any processed claim.
- **Zero-Dependency Frontend**: Pure vanilla HTML5, CSS3, and JavaScript Fetch API with zero external UI framework bloat.
- **Comprehensive Test Suite**: 9 unit and integration tests covering positive settlements, rule rejections, boundary limits, and input sanitization.

---

## 📂 Project Architecture

```
health_claims_engine/
├── app.py                             # Flask application, REST endpoints, and SQLite engine
├── database.db                        # SQLite database (auto-generated & seeded on startup)
├── requirements.txt                   # Project dependencies (Flask >= 3.0.0)
├── test_engine.py                     # Automated unit and integration test suite
├── POSTMAN_GUIDE.md                   # Full Postman guide with exact JSON request/response bodies
├── claims_engine_postman_collection.json # 1-click import collection for Postman
├── .gitignore                         # Git ignore rules for clean repository hygiene
├── LICENSE                            # MIT License
├── README.md                          # Documentation & guide
└── templates/
    └── index.html                     # Enterprise single-page application dashboard
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+ / Flask 3.1 | REST API development, routing, and business logic |
| **Database** | SQLite3 (`sqlite3` module) | ACID-compliant relational data store with foreign key enforcement |
| **Frontend** | HTML5, Modern CSS3, Vanilla JS | Reactive, accessible single-page UI powered by Fetch API |
| **API Testing** | Postman / cURL | Comprehensive integration testing suite (Postman v2.1 collection) |
| **Unit Testing**| Python `unittest` | Automated regression and rule verification suite |

---

## 🚀 Quickstart & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/health-claims-engine.git
cd health-claims-engine
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Running Automated Tests

Run the test suite to verify all rules, endpoints, and database interactions:

```bash
python -m unittest test_engine.py -v
```

Expected output:
```
test_01_index_page ... ok
test_02_get_patients ... ok
test_03_successful_claim_approval ... ok
test_04_rejected_inactive_policy ... ok
test_05_rejected_exceeded_limit ... ok
test_06_rejected_unregistered_patient ... ok
test_07_invalid_input_validation ... ok
test_08_claims_audit_log ... ok
test_09_database_reset ... ok

Ran 9 tests in 0.28s -- OK
```

---

## 📡 REST API Reference

### 1. Process Claim (`POST /api/claims/process`)
Evaluates a claim against business rules and updates the database.

**Request Body**:
```json
{
  "patient_id": "P101",
  "hospital_name": "City General Hospital",
  "claim_amount": 50000.0
}
```

**Approval Response (`200 OK`)**:
```json
{
  "success": true,
  "status": "Approved",
  "claim_id": 2,
  "patient_id": "P101",
  "patient_name": "John Doe",
  "hospital_name": "City General Hospital",
  "claim_amount": 50000.0,
  "previous_coverage": 475000.0,
  "remaining_coverage": 425000.0,
  "rule_evaluations": {
    "rule_1_policy_active": { "passed": true, "status": "Active" },
    "rule_2_within_limit": { "passed": true, "claim_amount": 50000.0, "available_limit": 475000.0 }
  },
  "remarks": "Claim approved successfully. Claim amount deducted from remaining coverage.",
  "timestamp": "2026-09-12 17:09:31"
}
```

### 2. Retrieve Patients (`GET /api/patients`)
Returns all registered patients, policy statuses, and remaining limits.

### 3. Retrieve Claims History (`GET /api/claims`)
Returns the complete audit log of all processed claims.

### 4. Aggregate Statistics (`GET /api/stats`)
Returns total claims count, settled amount, and approval ratios for KPI metrics.

### 5. Reset Database (`POST /api/reset`)
Restores the database to default initial seed records.

---

## 📝 Pre-Seeded Sample Data

| Patient ID | Name | Policy Status | Initial Coverage | Description |
| :--- | :--- | :--- | :--- | :--- |
| `P101` | John Doe | **Active** | \$500,000.00 | Ideal for testing valid approvals |
| `P102` | Jane Smith | **Inactive** | \$300,000.00 | Tests Rule 1 rejection (inactive policy) |
| `P103` | Robert Taylor | **Active** | \$50,000.00 | Tests Rule 2 rejection (exceeding limit) |
| `P104` | Emily Davis | **Active** | \$1,000,000.00 | High-limit policy for large claims |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
