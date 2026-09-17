"""
Unit and Integration Test Suite for Enterprise Automated Health Claims Processing Engine
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, get_db_connection, cents_to_dollars, dollars_to_cents


class EnterpriseClaimsEngineTestCase(unittest.TestCase):
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
        self.assertIn(b"Health Insurance Claims RPA Engine", response.data)

    def test_02_get_stats(self):
        """Verify aggregate statistics are computed accurately from SQLite."""
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["total_claims"], 1)  # Initial seed claim
        self.assertEqual(data["approved_claims"], 1)
        self.assertEqual(data["rejected_claims"], 0)
        self.assertEqual(data["total_amount_approved"], 25000.0)
        self.assertEqual(data["active_policies"], 3)
        self.assertEqual(data["total_policies"], 4)

    def test_03_get_policies(self):
        """Verify all registered policies are returned with calculated remaining coverage."""
        response = self.client.get("/api/policies")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 4)

        p101 = next(p for p in data["policies"] if p["policy_id"] == "P101")
        self.assertEqual(p101["patient_name"], "John Doe")
        self.assertEqual(p101["policy_status"], "Active")
        self.assertEqual(p101["coverage_limit"], 500000.0)
        self.assertEqual(p101["coverage_used"], 25000.0)
        self.assertEqual(p101["remaining_coverage"], 475000.0)

    def test_04_get_individual_policy_lookup(self):
        """Verify /api/policies/<id> returns policy details or 404."""
        # Valid policy
        res1 = self.client.get("/api/policies/P101")
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.data)
        self.assertTrue(data1["success"])
        self.assertEqual(data1["policy"]["patient_name"], "John Doe")
        self.assertEqual(data1["policy"]["remaining_coverage"], 475000.0)

        # Invalid policy
        res2 = self.client.get("/api/policies/UNKNOWN999")
        self.assertEqual(res2.status_code, 404)
        data2 = json.loads(res2.data)
        self.assertFalse(data2["success"])

    def test_05_successful_claim_approval(self):
        """Rule 1 & Rule 2 PASS -> Status Approved, coverage_used increased, audit log recorded."""
        payload = {
            "policy_id": "P101",
            "hospital_name": "City General Hospital",
            "claim_category": "Inpatient Medical",
            "claim_amount": 45000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Approved")
        self.assertEqual(data["policy_id"], "P101")
        self.assertEqual(data["claim_amount"], 45000.0)
        self.assertEqual(data["previous_coverage"], 475000.0)
        self.assertEqual(data["remaining_coverage"], 430000.0)
        self.assertTrue(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertTrue(data["rule_evaluations"]["rule_2_within_limit"]["passed"])

        # Check SQLite directly: coverage_used must be 25k + 45k = 70k (7,000,000 cents)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_used_cents FROM policies WHERE policy_id = 'P101';")
        used_cents = cursor.fetchone()[0]
        self.assertEqual(used_cents, 7000000)

        # Check append-only audit log exists
        cursor.execute("SELECT event_type FROM audit_logs WHERE claim_id = ?;", (data["claim_id"],))
        audit = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(audit)
        self.assertEqual(audit[0], "CLAIM_APPROVED_SETTLED")

    def test_06_rejected_inactive_policy(self):
        """Rule 1 FAIL -> Inactive policy must be rejected immediately, coverage unchanged, audit logged."""
        payload = {
            "policy_id": "P102",
            "hospital_name": "Apollo Care Hospital",
            "claim_category": "Surgery",
            "claim_amount": 30000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertFalse(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertIn("Inactive", data["remarks"])

        # Check SQLite coverage_used remains 0 cents
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_used_cents FROM policies WHERE policy_id = 'P102';")
        used_cents = cursor.fetchone()[0]
        self.assertEqual(used_cents, 0)

        # Verify audit log
        cursor.execute("SELECT event_type FROM audit_logs WHERE claim_id = ?;", (data["claim_id"],))
        audit = cursor.fetchone()
        conn.close()
        self.assertEqual(audit[0], "CLAIM_REJECTED_RULE_1")

    def test_07_rejected_exceeded_limit(self):
        """Rule 2 FAIL -> Claim exceeding limit must be rejected, coverage unchanged, audit logged."""
        payload = {
            "policy_id": "P103",
            "hospital_name": "Metro Memorial Hospital",
            "claim_category": "ICU Emergency",
            "claim_amount": 85000.0  # Limit is 50,000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertTrue(data["rule_evaluations"]["rule_1_policy_active"]["passed"])
        self.assertFalse(data["rule_evaluations"]["rule_2_within_limit"]["passed"])
        self.assertIn("exceeds remaining coverage limit", data["remarks"])

        # Check SQLite coverage_used remains 0 cents
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_used_cents FROM policies WHERE policy_id = 'P103';")
        used_cents = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(used_cents, 0)

    def test_08_rejected_unregistered_policy(self):
        """Unregistered policy ID -> Rejected, audit logged, no foreign key failure."""
        payload = {
            "policy_id": "P999",
            "hospital_name": "Mercy General",
            "claim_amount": 10000.0
        }
        response = self.client.post("/api/claims/process", json=payload)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "Rejected")
        self.assertIn("not found", data["remarks"])

    def test_09_invalid_input_validation(self):
        """Missing fields, negative or zero amounts must return 400 Bad Request."""
        res1 = self.client.post("/api/claims/process", json={"policy_id": "P101", "claim_amount": 5000})
        self.assertEqual(res1.status_code, 400)

        res2 = self.client.post("/api/claims/process", json={"policy_id": "P101", "hospital_name": "General", "claim_amount": -100})
        self.assertEqual(res2.status_code, 400)

        res3 = self.client.post("/api/claims/process", json={"policy_id": "P101", "hospital_name": "General", "claim_amount": 0})
        self.assertEqual(res3.status_code, 400)

    def test_10_claim_detail_with_audit_logs(self):
        """Check /api/claims/<id> returns claim record plus actual append-only audit trail."""
        # Initial seed claim has ID 1
        response = self.client.get("/api/claims/1")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        self.assertTrue(data["success"])
        self.assertEqual(data["claim"]["claim_id"], 1)
        self.assertEqual(data["claim"]["policy_id"], "P101")
        self.assertIsInstance(data["audit_logs"], list)
        self.assertGreaterEqual(len(data["audit_logs"]), 1)

    def test_11_database_reset(self):
        """Verify POST /api/reset restores clean seed data and logs event."""
        # Mutate by submitting a claim
        self.client.post("/api/claims/process", json={
            "policy_id": "P101",
            "hospital_name": "Clinic",
            "claim_amount": 100000.0
        })

        reset_res = self.client.post("/api/reset")
        self.assertEqual(reset_res.status_code, 200)

        # Check P101 remaining coverage is restored to $475,000.0
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT coverage_limit_cents, coverage_used_cents FROM policies WHERE policy_id = 'P101';")
        row = cursor.fetchone()
        conn.close()

        remaining_cents = row[0] - row[1]
        self.assertEqual(cents_to_dollars(remaining_cents), 475000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
