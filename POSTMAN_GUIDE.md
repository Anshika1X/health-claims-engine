# Postman API Testing Guide
### Automated Health & Insurance Claims Processing Engine

This guide provides step-by-step instructions for testing the REST API endpoints using **Postman**, **cURL**, or any HTTP client.

---

## 1. Quick Start / Prerequisites

1. **Start the Flask Server**:
   ```bash
   python app.py
   ```
   The server will run on `http://127.0.0.1:5000`.

2. **Import Postman Collection (Optional 1-Click Setup)**:
   - In Postman, click **Import**.
   - Select the file `claims_engine_postman_collection.json` located inside this workspace.
   - The collection will load with all predefined requests and variables.

---

## 2. Pre-seeded Patient Test Data

The database is automatically initialized with the following dummy patients:

| Patient ID | Name | Policy Status | Initial Coverage | Remaining Coverage | Test Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`P101`** | John Doe | **Active** | \$500,000.00 | \$475,000.00 | **Approval Testing** (Rule 1 & Rule 2 Pass) |
| **`P102`** | Jane Smith | **Inactive** | \$300,000.00 | \$300,000.00 | **Rejection Testing** (Rule 1 Fail: Inactive Policy) |
| **`P103`** | Robert Taylor | **Active** | \$50,000.00 | \$50,000.00 | **Rejection Testing** (Rule 2 Fail: Exceeds Limit) |
| **`P104`** | Emily Davis | **Active** | \$1,000,000.00 | \$1,000,000.00 | **Large Claim Testing** (High Coverage) |

---

## 3. Test Scenarios & Exact JSON Payloads

---

### Scenario A: Successful Claim Approval (Rule 1 & Rule 2 Pass)

- **Method**: `POST`
- **URL**: `http://127.0.0.1:5000/api/claims/process`
- **Headers**:
  ```http
  Content-Type: application/json
  ```
- **Request Body (JSON)**:
  ```json
  {
    "patient_id": "P101",
    "hospital_name": "City General Hospital",
    "claim_amount": 50000.0
  }
  ```
- **Expected Status Code**: `200 OK`
- **Expected Response Body (JSON)**:
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
      "rule_1_policy_active": {
        "passed": true,
        "status": "Active",
        "message": "Policy is Active."
      },
      "rule_2_within_limit": {
        "passed": true,
        "claim_amount": 50000.0,
        "available_limit": 475000.0,
        "message": "Claim amount ($50,000.00) is within limit ($475,000.00)."
      }
    },
    "remarks": "Claim approved successfully. Claim amount ($50,000.00) deducted from remaining coverage. New balance: $425,000.00.",
    "timestamp": "2026-09-12 16:55:00"
  }
  ```

---

### Scenario B: Claim Rejection - Rule 1 Fail (Inactive Policy)

- **Method**: `POST`
- **URL**: `http://127.0.0.1:5000/api/claims/process`
- **Headers**:
  ```http
  Content-Type: application/json
  ```
- **Request Body (JSON)**:
  ```json
  {
    "patient_id": "P102",
    "hospital_name": "Apollo Care Hospital",
    "claim_amount": 30000.0
  }
  ```
- **Expected Status Code**: `200 OK`
- **Expected Response Body (JSON)**:
  ```json
  {
    "success": true,
    "status": "Rejected",
    "claim_id": 3,
    "patient_id": "P102",
    "patient_name": "Jane Smith",
    "hospital_name": "Apollo Care Hospital",
    "claim_amount": 30000.0,
    "previous_coverage": 300000.0,
    "remaining_coverage": 300000.0,
    "rule_evaluations": {
      "rule_1_policy_active": {
        "passed": false,
        "status": "Inactive",
        "message": "Policy is Inactive, expected Active."
      },
      "rule_2_within_limit": {
        "passed": true,
        "claim_amount": 30000.0,
        "available_limit": 300000.0,
        "message": "Skipped/Failed due to inactive policy."
      }
    },
    "remarks": "Policy status is 'Inactive'. Claim rejected under Rule 1 (Active Policy Required).",
    "timestamp": "2026-09-12 16:55:00"
  }
  ```

---

### Scenario C: Claim Rejection - Rule 2 Fail (Exceeds Coverage Limit)

- **Method**: `POST`
- **URL**: `http://127.0.0.1:5000/api/claims/process`
- **Headers**:
  ```http
  Content-Type: application/json
  ```
- **Request Body (JSON)**:
  ```json
  {
    "patient_id": "P103",
    "hospital_name": "Metro Memorial Hospital",
    "claim_amount": 80000.0
  }
  ```
- **Expected Status Code**: `200 OK`
- **Expected Response Body (JSON)**:
  ```json
  {
    "success": true,
    "status": "Rejected",
    "claim_id": 4,
    "patient_id": "P103",
    "patient_name": "Robert Taylor",
    "hospital_name": "Metro Memorial Hospital",
    "claim_amount": 80000.0,
    "previous_coverage": 50000.0,
    "remaining_coverage": 50000.0,
    "rule_evaluations": {
      "rule_1_policy_active": {
        "passed": true,
        "status": "Active",
        "message": "Policy is Active."
      },
      "rule_2_within_limit": {
        "passed": false,
        "claim_amount": 80000.0,
        "available_limit": 50000.0,
        "message": "Claim amount ($80,000.00) exceeds remaining limit ($50,000.00)."
      }
    },
    "remarks": "Claim amount ($80,000.00) exceeds remaining coverage limit ($50,000.00). Claim rejected under Rule 2 (Coverage Limit Check).",
    "timestamp": "2026-09-12 16:55:00"
  }
  ```

---

### Scenario D: Claim Rejection - Unregistered Patient ID

- **Method**: `POST`
- **URL**: `http://127.0.0.1:5000/api/claims/process`
- **Request Body (JSON)**:
  ```json
  {
    "patient_id": "P999",
    "hospital_name": "Mercy General Hospital",
    "claim_amount": 10000.0
  }
  ```
- **Expected Response Body (JSON)**:
  ```json
  {
    "success": true,
    "status": "Rejected",
    "remarks": "Patient ID 'P999' not found in registered policy database.",
    "rule_evaluations": {
      "rule_1_policy_active": {
        "passed": false,
        "status": "NotFound",
        "message": "Patient not found in system."
      }
    }
  }
  ```

---

## 4. Querying & Admin Endpoints

### 1. View All Patients & Balances
- **Method**: `GET`
- **URL**: `http://127.0.0.1:5000/api/patients`
- **Response**: Array of patient records with remaining `coverage_limit` and `policy_status`.

### 2. View Claims Audit Log
- **Method**: `GET`
- **URL**: `http://127.0.0.1:5000/api/claims`
- **Response**: Full transaction log of approved and rejected claims with timestamps.

### 3. Reset Database to Default Dummy Data
- **Method**: `POST`
- **URL**: `http://127.0.0.1:5000/api/reset`
- **Response**:
  ```json
  {
    "success": true,
    "message": "Database successfully reset to initial seed data."
  }
  ```

---

## 5. cURL Verification Commands

You can also run these directly from PowerShell or Command Prompt:

```bash
# 1. Successful Approval (P101)
curl -X POST http://127.0.0.1:5000/api/claims/process -H "Content-Type: application/json" -d "{\"patient_id\":\"P101\",\"hospital_name\":\"City General Hospital\",\"claim_amount\":50000}"

# 2. Inactive Policy Rejection (P102)
curl -X POST http://127.0.0.1:5000/api/claims/process -H "Content-Type: application/json" -d "{\"patient_id\":\"P102\",\"hospital_name\":\"Apollo Care Hospital\",\"claim_amount\":30000}"

# 3. Limit Exceeded Rejection (P103)
curl -X POST http://127.0.0.1:5000/api/claims/process -H "Content-Type: application/json" -d "{\"patient_id\":\"P103\",\"hospital_name\":\"Metro Memorial Hospital\",\"claim_amount\":80000}"
```
