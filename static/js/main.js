/**
 * Automated Health & Insurance Claims Processing Engine
 * Frontend Client Controller (Fetch API & Live DOM Updates)
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initial data loading
  loadPatients();
  loadClaims();

  // Setup form submission listener
  const claimForm = document.getElementById("claimForm");
  if (claimForm) {
    claimForm.addEventListener("submit", handleClaimSubmission);
  }

  // Setup DB reset button listener
  const resetDbBtn = document.getElementById("resetDbBtn");
  if (resetDbBtn) {
    resetDbBtn.addEventListener("click", handleDatabaseReset);
  }
});

// Helper for formatting currency values
function formatCurrency(amount) {
  const num = Number(amount) || 0;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(num);
}

// Preset Quick-Test Scenario Loader
function applyPreset(patientId, hospital, amount) {
  document.getElementById("patientId").value = patientId;
  document.getElementById("hospitalName").value = hospital;
  document.getElementById("claimAmount").value = amount;

  // Highlight the form briefly
  const formCard = document.querySelector(".form-card");
  formCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Select a patient directly from the Patients Table
function selectPatient(patientId) {
  document.getElementById("patientId").value = patientId;
  document.getElementById("hospitalName").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/**
 * Handle Claim Submission using Fetch API
 */
async function handleClaimSubmission(e) {
  e.preventDefault();

  const submitBtn = document.getElementById("submitBtn");
  const btnText = submitBtn.querySelector(".btn-text");
  const spinner = submitBtn.querySelector(".spinner");

  const patientId = document.getElementById("patientId").value.trim().toUpperCase();
  const hospitalName = document.getElementById("hospitalName").value.trim();
  const claimAmount = parseFloat(document.getElementById("claimAmount").value);

  if (!patientId || !hospitalName || isNaN(claimAmount) || claimAmount <= 0) {
    alert("Please enter valid patient ID, hospital name, and positive claim amount.");
    return;
  }

  // Set loading state
  submitBtn.disabled = true;
  btnText.textContent = "Validating Business Rules...";
  spinner.style.display = "inline-block";

  try {
    const response = await fetch("/api/claims/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        patient_id: patientId,
        hospital_name: hospitalName,
        claim_amount: claimAmount
      })
    });

    const result = await response.json();

    if (!response.ok && !result.rule_evaluations) {
      throw new Error(result.error || "An unexpected error occurred during processing.");
    }

    // Update Live Dynamic Result Area
    renderDynamicResult(result);

    // Refresh Live Tables to reflect updated database balances and claims history
    loadPatients();
    loadClaims();

  } catch (error) {
    console.error("Claims processing error:", error);
    alert("Error processing claim: " + error.message);
  } finally {
    // Restore button state
    submitBtn.disabled = false;
    btnText.textContent = "⚡ Process Claim Now";
    spinner.style.display = "none";
  }
}

/**
 * Render dynamic claim evaluation result card
 */
function renderDynamicResult(res) {
  const placeholder = document.getElementById("resultPlaceholder");
  const resultCard = document.getElementById("dynamicResult");

  if (placeholder) placeholder.style.display = "none";
  if (resultCard) resultCard.style.display = "block";

  const isApproved = (res.status === "Approved");

  // Status Banner
  const statusBanner = document.getElementById("statusBanner");
  const statusIcon = document.getElementById("statusIcon");
  const statusBadge = document.getElementById("statusBadge");
  const statusTitle = document.getElementById("statusTitle");
  const claimIdTag = document.getElementById("claimIdTag");

  statusBanner.className = `status-banner ${isApproved ? "approved" : "rejected"}`;
  statusIcon.textContent = isApproved ? "✓" : "✕";
  statusBadge.textContent = res.status.toUpperCase();
  statusTitle.textContent = isApproved 
    ? "Claim Approved & Settled" 
    : "Claim Rejected by Business Rules";
  claimIdTag.textContent = res.claim_id ? `Claim #${res.claim_id}` : "Audit Record";

  // Summary Grid
  document.getElementById("resPatientId").textContent = res.patient_id || "--";
  document.getElementById("resPatientName").textContent = res.patient_name || "Unknown";
  document.getElementById("resHospital").textContent = res.hospital_name || "--";
  document.getElementById("resAmount").textContent = formatCurrency(res.claim_amount);

  // Rule 1 Checklist: Policy Status
  const rule1 = res.rule_evaluations?.rule_1_policy_active;
  const rule1Box = document.getElementById("rule1Box");
  const rule1Icon = document.getElementById("rule1Icon");
  const rule1Pill = document.getElementById("rule1Pill");
  const rule1Desc = document.getElementById("rule1Desc");

  if (rule1?.passed) {
    rule1Box.className = "rule-box pass";
    rule1Icon.textContent = "✓";
    rule1Pill.textContent = "PASS";
    rule1Desc.textContent = `Status: ${rule1.status} (Verified Active in policy database)`;
  } else {
    rule1Box.className = "rule-box fail";
    rule1Icon.textContent = "✕";
    rule1Pill.textContent = "FAIL";
    rule1Desc.textContent = rule1?.message || "Policy is not Active.";
  }

  // Rule 2 Checklist: Remaining Limit
  const rule2 = res.rule_evaluations?.rule_2_within_limit;
  const rule2Box = document.getElementById("rule2Box");
  const rule2Icon = document.getElementById("rule2Icon");
  const rule2Pill = document.getElementById("rule2Pill");
  const rule2Desc = document.getElementById("rule2Desc");

  if (rule2?.passed) {
    rule2Box.className = "rule-box pass";
    rule2Icon.textContent = "✓";
    rule2Pill.textContent = "PASS";
    rule2Desc.textContent = `Within limit (${formatCurrency(rule2.claim_amount)} ≤ ${formatCurrency(rule2.available_limit)})`;
  } else {
    rule2Box.className = "rule-box fail";
    rule2Icon.textContent = "✕";
    rule2Pill.textContent = "FAIL";
    rule2Desc.textContent = rule2?.message || "Claim amount exceeds available limit.";
  }

  // Coverage Adjustment Section
  document.getElementById("resPrevLimit").textContent = formatCurrency(res.previous_coverage);
  document.getElementById("resNewLimit").textContent = formatCurrency(res.remaining_coverage);

  // Remarks Note & Timestamp
  document.getElementById("resRemarks").textContent = res.remarks || "--";
  document.getElementById("resTimestamp").textContent = res.timestamp || new Date().toLocaleString();
}

/**
 * Fetch and populate registered patients table
 */
async function loadPatients() {
  const tbody = document.getElementById("patientsTableBody");
  if (!tbody) return;

  try {
    const response = await fetch("/api/patients");
    const data = await response.json();

    if (!data.success || !data.patients) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No patients found.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.patients.map(p => {
      const remaining = Number(p.coverage_limit);
      const initial = Number(p.initial_coverage);
      const pct = initial > 0 ? Math.max(0, Math.min(100, Math.round((remaining / initial) * 100))) : 0;
      
      let progressClass = "";
      if (pct <= 15) progressClass = "depleted";
      else if (pct <= 40) progressClass = "low";

      const statusBadge = p.policy_status === "Active" 
        ? `<span class="badge badge-active">● Active</span>`
        : `<span class="badge badge-inactive">● Inactive</span>`;

      return `
        <tr>
          <td><strong>${p.patient_id}</strong></td>
          <td>${p.name}</td>
          <td>${statusBadge}</td>
          <td><strong>${formatCurrency(p.coverage_limit)}</strong></td>
          <td>${formatCurrency(p.initial_coverage)}</td>
          <td>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 2px;">
              ${pct}% remaining
            </div>
            <div class="progress-container">
              <div class="progress-bar ${progressClass}" style="width: ${pct}%"></div>
            </div>
          </td>
          <td>
            <button class="btn btn-sm btn-outline" onclick="selectPatient('${p.patient_id}')">
              Select
            </button>
          </td>
        </tr>
      `;
    }).join("");

  } catch (error) {
    console.error("Failed to load patients:", error);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--danger);">Failed to load patients data.</td></tr>`;
  }
}

/**
 * Fetch and populate claims history audit table
 */
async function loadClaims() {
  const tbody = document.getElementById("claimsTableBody");
  if (!tbody) return;

  try {
    const response = await fetch("/api/claims");
    const data = await response.json();

    if (!data.success || !data.claims || data.claims.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No claims processed yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.claims.map(c => {
      const statusBadge = c.status === "Approved"
        ? `<span class="badge badge-approved">✓ Approved</span>`
        : `<span class="badge badge-rejected">✕ Rejected</span>`;

      return `
        <tr>
          <td>#${c.claim_id}</td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${c.created_at}</td>
          <td><strong>${c.patient_id}</strong></td>
          <td>${c.patient_name || "Unknown"}</td>
          <td>${c.hospital_name}</td>
          <td><strong>${formatCurrency(c.claim_amount)}</strong></td>
          <td>${statusBadge}</td>
          <td style="font-size: 0.82rem; max-width: 320px; line-height: 1.35;">${c.remarks}</td>
        </tr>
      `;
    }).join("");

  } catch (error) {
    console.error("Failed to load claims:", error);
    tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: var(--danger);">Failed to load claims history.</td></tr>`;
  }
}

/**
 * Handle database reset to default dummy data
 */
async function handleDatabaseReset() {
  if (!confirm("Are you sure you want to reset the database to initial seed data? This will restore original coverage limits and reset claims.")) {
    return;
  }

  try {
    const response = await fetch("/api/reset", { method: "POST" });
    const data = await response.json();

    if (data.success) {
      alert("Database reset successfully!");
      // Reset result area to placeholder
      const placeholder = document.getElementById("resultPlaceholder");
      const resultCard = document.getElementById("dynamicResult");
      if (placeholder) placeholder.style.display = "flex";
      if (resultCard) resultCard.style.display = "none";
      
      // Reload tables
      loadPatients();
      loadClaims();
    } else {
      alert("Failed to reset database.");
    }
  } catch (error) {
    console.error("Reset error:", error);
    alert("Error resetting database: " + error.message);
  }
}
