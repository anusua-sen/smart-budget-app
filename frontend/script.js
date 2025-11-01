const API_BASE = "http://127.0.0.1:8000/budgets";

// === Upload CSV ===
async function uploadCSV() {
  const fileInput = document.getElementById("csvFile");
  if (!fileInput.files.length) return alert("Please choose a CSV file!");
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const res = await fetch(`${API_BASE}/upload-csv`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  document.getElementById("uploadStatus").textContent =
    data.message || JSON.stringify(data);
}

// === Clear Transactions ===
async function clearTransactions() {
  if (!confirm("Are you sure you want to delete all transactions?")) return;
  const res = await fetch(`${API_BASE}/transactions/clear`, {
    method: "DELETE",
  });
  const data = await res.json();
  alert(data.message || "Transactions cleared");
}

// === Budgets ===
async function setBudget() {
  const category = document.getElementById("budgetCategory").value;
  const limit = parseFloat(document.getElementById("budgetLimit").value);
  if (!category || isNaN(limit)) return alert("Enter valid category & limit");
  const res = await fetch(`${API_BASE}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, limit }),
  });
  const data = await res.json();
  alert(data.message || JSON.stringify(data));
}

// ===Fetch Budget ===
async function fetchBudgets() {
  const resultBox = document.getElementById("budgetList");
  resultBox.textContent = "Loading...";

  const res = await fetch(`${API_BASE}/view`);
  if (!res.ok) {
    resultBox.textContent = "Failed to fetch budgets.";
    return;
  }

  const data = await res.json();
  if (!data || data.length === 0) {
    resultBox.textContent = "No budgets available.";
  } else {
    resultBox.textContent = JSON.stringify(data, null, 2);
  }
}


// === Clear Budgets ===
// === Clear Budgets ===
async function clearBudgets() {
  if (!confirm("Clear all budget limits?")) return;

  const res = await fetch(`${API_BASE}/clear-limits`, { method: "DELETE" });
  const data = await res.json().catch(() => ({})); // safely parse JSON

  if (res.ok) {
    alert(data.message || "All budgets cleared!");
    // ✅ Clear UI to match backend
    document.getElementById("budgetList").textContent = "All budgets cleared. No data available.";
  } else {
    alert(data.error || "Failed to clear budgets");
  }
}



// === Insights ===
async function fetchInsights() {
  const res = await fetch(`${API_BASE}/insights`);
  const data = await res.json();
  renderInsightsCharts(data);
}

// === Advanced Analytics ===
async function fetchAnalytics() {
  const res = await fetch(`${API_BASE}/analytics`);
  const data = await res.json();
  renderAdvancedAnalytics(data);
}

// === Download Summary Report ===
async function downloadSummary() {
  const res = await fetch(`${API_BASE}/insights`);
  const data = await res.json();

  const csvRows = [];
  csvRows.push("Category,Amount");
  for (const [cat, val] of Object.entries(data.category_breakdown)) {
    csvRows.push(`${cat},${val}`);
  }
  csvRows.push("");
  csvRows.push(`Total Spent,${data.total_spent}`);

  const blob = new Blob([csvRows.join("\n")], { type: "text/csv" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "summary_report.csv";
  a.click();
  window.URL.revokeObjectURL(url);
}

// === Chart helpers ===
let charts = {};

function destroyCharts() {
  Object.values(charts).forEach((chart) => chart.destroy());
  charts = {};
}

function renderInsightsCharts(data) {
  destroyCharts();
  document.getElementById(
    "totalSpentText"
  ).textContent = `💰 Total Spent: ₹${data.total_spent}`;

  const ctxCategory = document
    .getElementById("categoryChart")
    .getContext("2d");
  charts.categoryChart = new Chart(ctxCategory, {
    type: "pie",
    data: {
      labels: Object.keys(data.category_breakdown),
      datasets: [
        {
          data: Object.values(data.category_breakdown),
          backgroundColor: [
            "#42a5f5",
            "#66bb6a",
            "#ffa726",
            "#ef5350",
            "#ab47bc",
          ],
        },
      ],
    },
    options: {
      plugins: { title: { display: true, text: "Spend by Category" } },
    },
  });

  const ctxMonthly = document
    .getElementById("monthlyChart")
    .getContext("2d");
  charts.monthlyChart = new Chart(ctxMonthly, {
    type: "line",
    data: {
      labels: Object.keys(data.monthly_summary),
      datasets: [
        {
          label: "Total Monthly Spend (₹)",
          data: Object.values(data.monthly_summary),
          borderColor: "#4CAF50",
          fill: false,
          tension: 0.3,
        },
      ],
    },
    options: {
      plugins: { title: { display: true, text: "Monthly Spending Trend" } },
    },
  });
}

function renderAdvancedAnalytics(data) {
  destroyCharts();

  // Category-wise monthly spend
  const ctxCatMonth = document
    .getElementById("categoryMonthlyChart")
    .getContext("2d");
  const months = [
    ...new Set(
      Object.values(data.category_monthly).flatMap((obj) =>
        Object.keys(obj)
      )
    ),
  ];
  const datasets = Object.entries(data.category_monthly).map(
    ([cat, vals]) => ({
      label: cat,
      data: months.map((m) => vals[m] || 0),
      fill: false,
      borderWidth: 2,
    })
  );

  charts.categoryMonthlyChart = new Chart(ctxCatMonth, {
    type: "line",
    data: { labels: months, datasets },
    options: {
      plugins: {
        title: { display: true, text: "Category Spend per Month" },
      },
    },
  });

  // Top merchants
  const ctxMerchants = document
    .getElementById("topMerchantsChart")
    .getContext("2d");
  charts.topMerchantsChart = new Chart(ctxMerchants, {
    type: "bar",
    data: {
      labels: data.top_merchants.map((x) => x.merchant),
      datasets: [
        {
          label: "Frequency",
          data: data.top_merchants.map((x) => x.count),
          backgroundColor: "#42a5f5",
        },
      ],
    },
    options: {
      plugins: {
        title: { display: true, text: "Top Frequent Merchant Keywords" },
      },
    },
  });
}
