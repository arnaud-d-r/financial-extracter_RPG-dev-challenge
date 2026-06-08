const state = {
  records: [],
  warnings: [],
};

function render() {
  document.getElementById("record-count").textContent = String(state.records.length);
  document.getElementById("warning-count").textContent = String(state.warnings.length);
  document.getElementById("source-count").textContent = String(
    new Set(state.records.map((record) => record.source)).size,
  );

  const records = document.getElementById("records");
  records.innerHTML = state.records.length
    ? `
      <table>
        <thead>
          <tr><th>Vendor</th><th>Category</th><th>Amount</th><th>Source</th></tr>
        </thead>
        <tbody>
          ${state.records
            .map(
              (record) => `
                <tr>
                  <td>${record.vendor ?? "-"}</td>
                  <td>${record.category ?? "-"}</td>
                  <td>${record.amount ?? 0}</td>
                  <td>${record.source ?? "-"}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    `
    : "<p class=\"empty\">No records yet.</p>";

  const warnings = document.getElementById("warnings");
  warnings.innerHTML = state.warnings.length
    ? state.warnings.map((warning) => `<li>${warning}</li>`).join("")
    : "<li>No warnings.</li>";
}

async function loadDashboard() {
  const response = await fetch("/api/dashboard");
  if (!response.ok) {
    document.getElementById("status").textContent = "Not synced";
    return;
  }
  const payload = await response.json();
  state.records = payload.records ?? [];
  state.warnings = payload.warnings ?? [];
  document.getElementById("status").textContent = "Loaded";
  render();
}

async function syncDashboard() {
  document.getElementById("status").textContent = "Syncing...";
  const response = await fetch("/api/sync", { method: "POST" });
  if (response.ok) {
    document.getElementById("status").textContent = "Synced";
    await loadDashboard();
  } else {
    document.getElementById("status").textContent = "Sync failed";
  }
}

document.getElementById("sync-button").addEventListener("click", syncDashboard);
loadDashboard().catch(() => {
  document.getElementById("status").textContent = "Offline";
});
