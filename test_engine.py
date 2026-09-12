"""
Unit and Integration Test Suite for Automated Health Claims Processing Engine
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, get_db_connection


class ClaimsEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Reset DB before each test
        init_db(reset=True)

    def tearDown(self):
        pass

    def test_01_index_page(self):
        """Verify dashboard HTML renders with HTTP 200."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Automated Health & Insurance Claims Processing Engine", response.data)

    def test_02_get_patients(self):
        """Verify pre-seeded patient records are returned."""
        response = self.client.get("/api/patients")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 4)
        
        patient_ids = [p["patient_id"] for p in data["patients"]]
        self.assertIn("P101", patient_ids)
        self.assertIn("P102", patient_ids)
        self.assertIn("P103", patient_ids)
        self.assertIn("P104", patient_ids)

    def test_03_successful_claim_approval(self):
        """Rule 1 (Active) and Rule 2 (Within Limit) PASS -> Status Approved & limit deducted."""
        payload = {
            "patient_id": "P101",
            "hospital_name": "City General Hospital",
            "claim_amount": 50000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Approved")
        self.assertEqual(data["patient_id"], "P101")
        self.assertEqual(data["claim_amount"], 50000.0)
        self.assertEqual(data["previous_coverage"], 475000.0)
        self.assertEqual(data["remaining_coverage"], 425000.0)
        self.assertTrue(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertTrue(data["rule_evaluations"]["rule_2_within_limit"]["passed"])

        # Check DB update directly
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_limit FROM patients WHERE patient_id = 'P101';")
        db_limit = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(db_limit, 425000.0)

    def test_04_rejected_inactive_policy(self):
        """Rule 1 FAIL -> Inactive policy must be rejected immediately without deducting balance."""
        payload = {
            "patient_id": "P102",
            "hospital_name": "Apollo Care Hospital",
            "claim_amount": 30000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertFalse(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertIn("Inactive", data["remarks"])

        # Check DB limit remains 300,000.0
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_limit FROM patients WHERE patient_id = 'P102';")
        db_limit = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(db_limit, 300000.0)

    def test_05_rejected_exceeded_limit(self):
        """Rule 2 FAIL -> Claim amount exceeding limit must be rejected without deducting balance."""
        payload = {
            "patient_id": "P103",
            "hospital_name": "Metro Memorial Hospital",
            "claim_amount": 80000.0  # Limit is 50000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertTrue(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertFalse(data["rule_evaluations"]["rule_2_within_limit"]["passed"])
        self.assertIn("exceeds remaining coverage limit", data["remarks"])

        # Check DB limit remains 50,000.0
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_limit FROM patients WHERE patient_id = 'P103';")
        db_limit = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(db_limit, 50000.0)

    def test_06_rejected_unregistered_patient(self):
        """Unregistered patient ID -> Rejected."""
        payload = {
            "patient_id": "P999",
            "hospital_name": "Mercy General",
            "claim_amount": 10000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertIn("not found", data["remarks"])

    def test_07_invalid_input_validation(self):
        """Negative amounts or missing fields should return 400 Bad Request."""
        # Missing hospital
        res1 = self.client.post("/api/claims/process", json={"patient_id": "P101", "claim_amount": 5000})
        self.assertEqual(res1.status_code, 400)

        # Negative amount
        res2 = self.client.post("/api/claims/process", json={"patient_id": "P101", "hospital_name": "General", "claim_amount": -100})
        self.assertEqual(res2.status_code, 400)

        # Zero amount
        res3 = self.client.post("/api/claims/process", json={"patient_id": "P101", "hospital_name": "General", "claim_amount": 0})
        self.assertEqual(res3.status_code, 400)

    def test_08_claims_audit_log(self):
        """Check that claims are logged and retrievable via GET /api/claims."""
        self.client.post("/api/claims/process", json={
            "patient_id": "P101",
            "hospital_name": "St. Luke's",
            "claim_amount": 12000.0
        })

        response = self.client.get("/api/claims")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["claims"]), 2)

    def test_09_database_reset(self):
        """Verify POST /api/reset resets data correctly."""
        # Mutate limit
        self.client.post("/api/claims/process", json={
            "patient_id": "P101",
            "hospital_name": "Clinic",
            "claim_amount": 100000.0
        })
        
        reset_res = self.client.post("/api/reset")
        self.assertEqual(reset_res.status_code, 200)

        # Check P101 has restored coverage (475,000.0 after initial sample claim)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_limit FROM patients WHERE patient_id = 'P101';")
        db_limit = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(db_limit, 475000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
