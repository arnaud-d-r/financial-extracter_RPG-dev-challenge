// ─── Warning metadata ────────────────────────────────────────────────────────
//
// fatal: record is excluded from all totals and shown in the Invalid tab.
//        No dismiss action is offered — the data cannot be trusted as-is.
//
// dismissable: record is included provisionally and highlighted. The user can:
//   • Accept  → confirm the value is correct despite the anomaly; warning is
//               cleared and the row returns to normal.
//   • Reject  → mark the record as manually excluded (treated like invalid for
//               totals), signalling it needs to be corrected at the source.

const WARNING_META = {
  invalid_amount: {
    fatal: true,
    label: "Amount could not be read",
    detail: "The extracted amount is missing or unparseable. This record is excluded from all totals until the source file is corrected.",
  },
  invalid_date: {
    fatal: true,
    label: "Date could not be read",
    detail: "The date is missing or in an unrecognised format. This record is excluded from all totals until the source file is corrected.",
  },
  invalid_category: {
    fatal: true,
    label: "Category could not be determined",
    detail: "The record could not be classified as income or expense. This record is excluded from all totals until the source file is corrected.",
  },
  invalid_vendor: {
    fatal: false,
    label: "Vendor name could not be read",
    detail: "The vendor name is missing or illegible. The amount and date were extracted successfully.",
    acceptLabel: "Confirm — include without vendor name",
    rejectLabel: "Exclude — I'll correct the source",
  },
  invalid_invoice_paid_date: {
    fatal: false,
    label: "Payment date could not be read",
    detail: "The invoice paid date is missing or unrecognised. The invoice amount is still counted as received income.",
    acceptLabel: "Confirm — paid date not needed",
    rejectLabel: "Exclude — payment date is required",
  },
  future_date: {
    fatal: true,
    label: "Date is in the future",
    detail: "This record's date falls in the future. It may have been misread or the source file may be incorrect. This record is excluded from all totals until the source file is corrected.",
  },
  paid_before_sent: {
    fatal: false,
    label: "Invoice paid before it was sent",
    detail: "The recorded payment date is earlier than the invoice date, which is unusual.",
    acceptLabel: "Confirm — dates are correct",
    rejectLabel: "Exclude — dates need review",
  },
  personal_expense: {
    fatal: false,
    label: "Flagged as personal expense",
    detail: "This transaction was identified in notes.txt as a personal expense and is excluded from business totals by default.",
    acceptLabel: "Override — treat as business expense",
    rejectLabel: "Confirm personal — keep excluded",
  },
  unpaid_invoice: {
    fatal: false,
    label: "Invoice is outstanding",
    detail: "No payment has been recorded for this invoice. It is counted under Outstanding, not Income.",
    acceptLabel: "Mark as paid — move to income",
    rejectLabel: "Confirm outstanding — keep as-is",
  },
  not_cash_receipt: {
    fatal: false,
    label: "File does not appear to be a cash receipt",
    detail: "The extraction model could not identify this file as a cash receipt. It may have been included by mistake.",
    acceptLabel: "Confirm — treat as valid receipt",
    rejectLabel: "Exclude — not a valid receipt",
  },
  negative_amount: {
    fatal: false,
    label: "Amount is negative",
    detail: "A negative amount on an expense record typically indicates a reimbursement or refund, and is subtracted from total expenses.",
    acceptLabel: "Confirm — this is a reimbursement",
    rejectLabel: "Exclude — amount looks wrong",
  },
};

const FATAL_WARNINGS = new Set(
  Object.entries(WARNING_META)
    .filter(([, m]) => m.fatal)
    .map(([k]) => k),
);

// ─── State ───────────────────────────────────────────────────────────────────

const state = {
  records: [],
  // dismissed: { "<record_id>_<warning_key>": "accepted" | "rejected" }
  dismissed: {},
  activeTab: "income",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Generate a stable ID from record fields in case the API doesn't include one.
function recordId(record) {
  return record.id ?? `${record.source_file}|${record.date}|${record.amount}`;
}

function isIncome(record) {
  return record.category === "invoice";
}

function isExpense(record) {
  return record.category === "bank_statement" || record.category === "receipt";
}

function isRecordInvalid(record) {
  const rid = recordId(record);
  return record.warnings.some((w) => {
    if (FATAL_WARNINGS.has(w)) return true;
    return state.dismissed[`${rid}_${w}`] === "rejected";
  });
}

function activeWarnings(record) {
  const rid = recordId(record);
  return record.warnings.filter((w) => !state.dismissed[`${rid}_${w}`]);
}

function fmtCAD(n) {
  const abs = Math.abs(n).toLocaleString("en-CA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (n < 0 ? "-" : "") + "$" + abs;
}

function computeSummary() {
  const { records } = state;

  const income = records
    .filter(
      (r) =>
        isIncome(r) &&
        !isRecordInvalid(r) &&
        !activeWarnings(r).includes("unpaid_invoice"),
    )
    .reduce((s, r) => s + (r.amount ?? 0), 0);

  const outstanding = records
    .filter(
      (r) =>
        isIncome(r) &&
        !isRecordInvalid(r) &&
        activeWarnings(r).includes("unpaid_invoice"),
    )
    .reduce((s, r) => s + (r.amount ?? 0), 0);

  const expenses = records
    .filter((r) => isExpense(r) && !isRecordInvalid(r))
    .reduce((s, r) => s + Math.abs(r.amount ?? 0), 0);

  return { income, outstanding, expenses, balance: income - expenses };
}

function tabStats(tab) {
  const { records } = state;
  if (tab === "invalid") {
    const inv = records.filter((r) => isRecordInvalid(r));
    return { count: inv.length, warnings: 0, invalid: inv.length };
  }
  const filter = tab === "income" ? isIncome : isExpense;
  const recs = records.filter((r) => filter(r) && !isRecordInvalid(r));
  const withWarnings = recs.filter((r) => activeWarnings(r).length > 0).length;
  return { count: recs.length, warnings: withWarnings, invalid: 0 };
}

// ─── Render ──────────────────────────────────────────────────────────────────

function renderSummary() {
  const s = computeSummary();
  const el = document.getElementById("summary-grid");
  el.innerHTML = `
    <div class="metric">
      <div class="metric__label">Income received</div>
      <div class="metric__value" style="color:var(--success-text)">${fmtCAD(s.income)}</div>
    </div>
    <div class="metric">
      <div class="metric__label">Expenses</div>
      <div class="metric__value" style="color:var(--invalid-text)">${fmtCAD(s.expenses)}</div>
    </div>
    <div class="metric">
      <div class="metric__label">Balance</div>
      <div class="metric__value" style="color:${s.balance >= 0 ? "var(--success-text)" : "var(--invalid-text)"}">${fmtCAD(s.balance)}</div>
    </div>
    <div class="metric">
      <div class="metric__label">Outstanding</div>
      <div class="metric__value" style="color:var(--warn-text)">${fmtCAD(s.outstanding)}</div>
    </div>
  `;
}

function renderTabs() {
  const tabs = [
    { key: "income", label: "Income" },
    { key: "expense", label: "Expenses" },
    { key: "invalid", label: "Invalid" },
  ];
  document.getElementById("tabs").innerHTML = tabs
    .map(({ key, label }) => {
      const s = tabStats(key);
      const isActive = state.activeTab === key;
      const warnBadge =
        s.warnings > 0
          ? `<span class="badge badge--warn"><i class="ti ti-alert-triangle" aria-hidden="true"></i> ${s.warnings}</span>`
          : "";
      const invBadge =
        s.invalid > 0
          ? `<span class="badge badge--invalid"><i class="ti ti-x" aria-hidden="true"></i> ${s.invalid}</span>`
          : "";
      return `
        <button class="tab${isActive ? " tab--active" : ""}" data-tab="${key}">
          <span class="tab__label">${label}</span>
          <span class="tab__meta">
            <span class="badge badge--count">${s.count}</span>
            ${warnBadge}${invBadge}
          </span>
        </button>
      `;
    })
    .join("");

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      renderTabs();
      renderTable();
    });
  });
}

function renderWarningBlock(record) {
  const rid = recordId(record);
  const warnings = activeWarnings(record);
  if (!warnings.length) {
    const anyDismissed = record.warnings.some(
      (w) => state.dismissed[`${rid}_${w}`],
    );
    if (anyDismissed) {
      return `<span class="warn-resolved"><i class="ti ti-circle-check" aria-hidden="true"></i> Reviewed</span>`;
    }
    return "";
  }

  return warnings
    .map((w) => {
      const meta = WARNING_META[w] ?? {
        fatal: false,
        label: w,
        detail: "Unknown warning.",
        acceptLabel: "Accept",
        rejectLabel: "Reject",
      };

      const actions = meta.fatal
        ? `<p class="warn-action-note">Fix the source file and re-sync to resolve this error.</p>`
        : `<div class="warn-actions">
            <button class="warn-btn warn-btn--accept" data-rid="${rid}" data-warning="${w}" data-action="accepted">
              <i class="ti ti-check" aria-hidden="true"></i> ${meta.acceptLabel}
            </button>
            <button class="warn-btn warn-btn--reject" data-rid="${rid}" data-warning="${w}" data-action="rejected">
              <i class="ti ti-x" aria-hidden="true"></i> ${meta.rejectLabel}
            </button>
          </div>`;

      return `
        <div class="warn-block${meta.fatal ? " warn-block--fatal" : ""}">
          <p class="warn-label"><i class="ti ti-alert-triangle" aria-hidden="true"></i> ${meta.label}</p>
          <p class="warn-detail">${meta.detail}</p>
          ${actions}
        </div>
      `;
    })
    .join("");
}

function renderTable() {
  const { records, activeTab } = state;
  const filter = activeTab === "income" ? isIncome : isExpense;
  const shown =
    activeTab === "invalid"
      ? records.filter((r) => isRecordInvalid(r))
      : records.filter((r) => filter(r) && !isRecordInvalid(r));

  if (!shown.length) {
    document.getElementById("records-body").innerHTML = `
      <tr><td colspan="6" class="table-empty">No records in this category.</td></tr>
    `;
    return;
  }
}

function fmtPaymentMethod(raw) {
  if (!raw) return "—";
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function sortedByDate(records) {
  return [...records].sort((a, b) => {
    if (!a.date && !b.date) return 0;
    if (!a.date) return 1;
    if (!b.date) return -1;
    return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
  });
}

async function patchWarning(record, warning) {
  try {
    await fetch("/api/transaction/warning", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        match: {
          source_file: record.source_file,
          date: record.date,
          amount: record.amount,
        },
        remove_warning: warning,
      }),
    });
  } catch (err) {
    console.warn("PATCH /api/transaction/warning failed:", err);
  }
}

function renderTable() {
  const { records, activeTab } = state;
  const filter = activeTab === "income" ? isIncome : isExpense;
  const shown =
    activeTab === "invalid"
      ? records.filter((r) => isRecordInvalid(r))
      : records.filter((r) => filter(r) && !isRecordInvalid(r));

  if (!shown.length) {
    document.getElementById("records-body").innerHTML = `
      <tr><td colspan="6" class="table-empty">No records in this category.</td></tr>
    `;
    return;
  }

  document.getElementById("records-body").innerHTML = sortedByDate(shown)
    .map((record) => {
      const warns = activeWarnings(record);
      const invalid = isRecordInvalid(record);
      const rowClass = invalid
        ? "row--invalid"
        : warns.length
          ? "row--warn"
          : "";
      const amtColor =
        record.amount == null
          ? ""
          : record.amount >= 0
            ? "color:var(--success-text)"
            : "color:var(--invalid-text)";

      return `
        <tr class="${rowClass}">
          <td>${record.date ?? "—"}</td>
          <td>${record.vendor ?? "—"}</td>
          <td class="cell--muted">${record.source_file ?? "—"}</td>
          <td class="cell--muted">${fmtPaymentMethod(record.payment_method)}</td>
          <td class="cell--amount" style="${amtColor}">${record.amount != null ? fmtCAD(record.amount) : "—"}</td>
          <td>${renderWarningBlock(record)}</td>
        </tr>
      `;
    })
    .join("");

  document.querySelectorAll(".warn-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const { rid, warning, action } = btn.dataset;
      state.dismissed[`${rid}_${warning}`] = action;

      if (action === "accepted") {
        const record = state.records.find((r) => recordId(r) === rid);
        if (record) await patchWarning(record, warning);
      }

      renderAll();
    });
  });
}

function renderAll() {
  renderSummary();
  renderTabs();
  renderTable();
}

// ─── API ─────────────────────────────────────────────────────────────────────

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function setSyncing(isSyncing) {
  const btn = document.getElementById("sync-button");
  btn.disabled = isSyncing;
  btn.textContent = isSyncing ? "Syncing…" : "Sync shoebox";
}

async function loadDashboard() {
  const response = await fetch("/api/dashboard");
  if (!response.ok) {
    setStatus("Not synced");
    return;
  }
  const payload = await response.json();
  state.records = payload.records ?? [];
  setStatus("Loaded");
  renderAll();
}

async function syncDashboard() {
  setSyncing(true);
  setStatus("Syncing…");
  try {
    const response = await fetch("/api/sync", { method: "POST" });
    if (response.ok) {
      state.dismissed = {};
      await loadDashboard();
    } else {
      setStatus("Sync failed");
    }
  } finally {
    setSyncing(false);
  }
}

document.getElementById("sync-button").addEventListener("click", syncDashboard);
loadDashboard().catch(() => {
  setStatus("Offline");
});

