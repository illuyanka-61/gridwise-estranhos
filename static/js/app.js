/**
 * GridWise Frontend Application Logic
 * BUP CSE Fest 2026: Smart Campus Energy Optimization Dashboard
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentScenario = null;
  let chartGeneration = null;
  let chartBattery = null;
  let chartTariff = null;

  // DOM Elements
  const presetSelect = document.getElementById("presetSelect");
  const notesContainer = document.getElementById("notesContainer");
  const addNoteBtn = document.getElementById("addNoteBtn");
  const optimizeBtn = document.getElementById("optimizeBtn");
  const statusBadge = document.getElementById("statusBadge");
  const statusText = document.getElementById("statusText");

  // Battery inputs
  const inputCapacity = document.getElementById("batteryCapacity");
  const inputInitial = document.getElementById("batteryInitial");
  const inputMin = document.getElementById("batteryMin");
  const inputMaxCharge = document.getElementById("batteryMaxCharge");
  const inputMaxDischarge = document.getElementById("batteryMaxDischarge");

  // Output containers
  const kpiTotalCost = document.getElementById("kpiTotalCost");
  const kpiTotalGrid = document.getElementById("kpiTotalGrid");
  const kpiPeakGrid = document.getElementById("kpiPeakGrid");
  const kpiNeutrality = document.getElementById("kpiNeutrality");
  const strategyBanner = document.getElementById("strategyBanner");
  const strategyText = document.getElementById("strategyText");
  const directivesList = document.getElementById("directivesList");
  const tableBody = document.getElementById("dispatchTableBody");
  const jsonOutput = document.getElementById("jsonOutput");

  // 1. Initialize Presets Dropdown
  function initPresets() {
    const presets = window.SAMPLE_PRESETS || [];
    presetSelect.innerHTML = "";

    presets.forEach((p, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `${p.id} — ${p.label}`;
      presetSelect.appendChild(opt);
    });

    const customOpt = document.createElement("option");
    customOpt.value = "custom";
    customOpt.textContent = "⚙️ Custom Scenario";
    presetSelect.appendChild(customOpt);

    presetSelect.addEventListener("change", onPresetChange);
    if (presets.length > 0) {
      loadPreset(0);
    }
  }

  // 2. Load Preset
  function loadPreset(idx) {
    const presets = window.SAMPLE_PRESETS || [];
    if (idx === "custom" || !presets[idx]) {
      // Setup a custom blank scenario
      currentScenario = {
        scenario_id: "CUSTOM-01",
        operator_notes: [
          "Reduce solar availability by 50% from 11 AM until 2 PM.",
          "Do not charge the battery between 2 PM and 5 PM."
        ],
        hours: Array.from({ length: 24 }, (_, h) => ({
          hour: h,
          demand_kwh: 120 + Math.sin(h / 3) * 30,
          solar_kwh: (h >= 7 && h <= 17) ? Math.max(0, 160 - Math.abs(h - 12) * 30) : 0,
          tariff_bdt_per_kwh: (h >= 18 && h <= 21) ? 22 : (h < 6 ? 7 : 14)
        })),
        battery: {
          capacity_kwh: 250,
          initial_energy_kwh: 120,
          minimum_energy_kwh: 40,
          max_charge_kwh_per_hour: 60,
          max_discharge_kwh_per_hour: 60
        }
      };
    } else {
      currentScenario = JSON.parse(JSON.stringify(presets[idx].input));
    }

    renderScenarioInputs();
  }

  function onPresetChange(e) {
    loadPreset(e.target.value);
  }

  // 3. Render Inputs to Form
  function renderScenarioInputs() {
    if (!currentScenario) return;

    // Battery
    inputCapacity.value = currentScenario.battery.capacity_kwh;
    inputInitial.value = currentScenario.battery.initial_energy_kwh;
    inputMin.value = currentScenario.battery.minimum_energy_kwh;
    inputMaxCharge.value = currentScenario.battery.max_charge_kwh_per_hour;
    inputMaxDischarge.value = currentScenario.battery.max_discharge_kwh_per_hour;

    // Notes
    renderNotes();
  }

  function renderNotes() {
    notesContainer.innerHTML = "";
    const notes = currentScenario.operator_notes || [];

    notes.forEach((note, i) => {
      const item = document.createElement("div");
      item.className = "note-item animate-fade-in";
      item.innerHTML = `
        <div class="note-item-header">
          <span class="note-tag">Note [${i}]</span>
          ${notes.length > 1 ? `<button type="button" class="remove-note-btn" data-index="${i}">✕ Remove</button>` : ""}
        </div>
        <textarea class="form-textarea note-textarea" rows="2" data-index="${i}">${note}</textarea>
      `;
      notesContainer.appendChild(item);
    });

    // Update listeners
    document.querySelectorAll(".note-textarea").forEach(ta => {
      ta.addEventListener("input", (e) => {
        const idx = parseInt(e.target.dataset.index);
        currentScenario.operator_notes[idx] = e.target.value;
      });
    });

    document.querySelectorAll(".remove-note-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.target.dataset.index);
        currentScenario.operator_notes.splice(idx, 1);
        renderNotes();
        updateAddButtonState();
      });
    });

    updateAddButtonState();
  }

  function updateAddButtonState() {
    const count = (currentScenario.operator_notes || []).length;
    addNoteBtn.style.display = count >= 3 ? "none" : "flex";
  }

  addNoteBtn.addEventListener("click", () => {
    if ((currentScenario.operator_notes || []).length < 3) {
      currentScenario.operator_notes.push("");
      renderNotes();
    }
  });

  // 4. Probe Backend Health
  async function checkHealth() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        const data = await res.json();
        if (data.status === "ok") {
          statusBadge.classList.remove("offline");
          statusText.textContent = "Live Backend Ready";
          return true;
        }
      }
    } catch (err) {
      console.warn("Backend health check failed:", err);
    }
    statusBadge.classList.add("offline");
    statusText.textContent = "Backend Offline";
    return false;
  }

  // 5. Trigger Optimization API Call
  async function runOptimization() {
    optimizeBtn.disabled = true;
    optimizeBtn.innerHTML = `
      <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
      </svg>
      Optimizing Energy Schedule...
    `;

    // Sync battery inputs
    currentScenario.battery.capacity_kwh = parseFloat(inputCapacity.value) || 200;
    currentScenario.battery.initial_energy_kwh = parseFloat(inputInitial.value) || 100;
    currentScenario.battery.minimum_energy_kwh = parseFloat(inputMin.value) || 40;
    currentScenario.battery.max_charge_kwh_per_hour = parseFloat(inputMaxCharge.value) || 50;
    currentScenario.battery.max_discharge_kwh_per_hour = parseFloat(inputMaxDischarge.value) || 50;

    // Filter out empty notes
    currentScenario.operator_notes = currentScenario.operator_notes.filter(n => n && n.trim().length > 0);
    if (currentScenario.operator_notes.length === 0) {
      currentScenario.operator_notes = ["Normal campus operation."];
    }

    try {
      const t0 = performance.now();
      const response = await fetch("/optimize-energy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentScenario)
      });

      const elapsed = ((performance.now() - t0) / 1000).toFixed(3);

      if (!response.ok) {
        const errData = await response.json();
        alert(`Optimization Error (${response.status}):\n${JSON.stringify(errData, null, 2)}`);
        return;
      }

      const result = await response.json();
      renderOptimizationResults(result, elapsed);

    } catch (err) {
      alert(`Network / Service Error: ${err.message}`);
    } finally {
      optimizeBtn.disabled = false;
      optimizeBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        Run Mathematical Optimization
      `;
    }
  }

  optimizeBtn.addEventListener("click", runOptimization);

  // 6. Render Optimization Results
  function renderOptimizationResults(data, elapsed) {
    // Top KPIs
    kpiTotalCost.textContent = `${data.total_cost_bdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    kpiTotalGrid.textContent = `${data.total_grid_kwh.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
    kpiPeakGrid.textContent = `${data.peak_grid_kwh.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
    
    // Battery neutrality check
    const plan = data.hourly_plan;
    const initialE = currentScenario.battery.initial_energy_kwh;
    const finalE = plan[plan.length - 1].battery_energy_after_kwh;
    const isNeutral = Math.abs(finalE - initialE) <= 0.05;
    
    kpiNeutrality.textContent = isNeutral ? "✓ Verified (E₂₃ = E₀)" : "⚠️ Neutrality Error";
    kpiNeutrality.style.color = isNeutral ? "var(--emerald-400)" : "var(--rose-400)";

    // Strategy Banner
    strategyText.textContent = `${data.plan_summary} (Solved in ${elapsed}s via OR-Tools GLOP)`;
    strategyBanner.style.display = "block";

    // Directives
    renderDirectives(data.directive_interpretation);

    // Render Charts
    renderCharts(data, currentScenario);

    // Render Table
    renderTable(data.hourly_plan, currentScenario.hours);

    // Render Raw JSON
    jsonOutput.textContent = JSON.stringify(data, null, 2);
  }

  // 7. Render Directives Cards
  function renderDirectives(directives) {
    directivesList.innerHTML = "";
    if (!directives || directives.length === 0) {
      directivesList.innerHTML = "<p class='text-muted'>No directives processed.</p>";
      return;
    }

    directives.forEach(d => {
      const card = document.createElement("div");
      card.className = "directive-card animate-fade-in";

      let adjDetails = "";
      if (d.structured_adjustment) {
        const adj = d.structured_adjustment;
        const hoursStr = `Hours: [${adj.hours.join(", ")}]`;
        let paramStr = "";
        if (adj.factor !== undefined) paramStr = `Factor: ${(adj.factor * 100).toFixed(0)}%`;
        if (adj.minimum_energy_kwh !== undefined) paramStr = `Min: ${adj.minimum_energy_kwh} kWh`;
        if (adj.max_grid_kwh !== undefined) paramStr = `Max Grid: ${adj.max_grid_kwh} kWh`;

        adjDetails = `${hoursStr} ${paramStr ? "• " + paramStr : ""}`;
      } else {
        adjDetails = "applies: false (no_op)";
      }

      card.innerHTML = `
        <div class="directive-meta">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="directive-badge badge-${d.directive_type}">${d.directive_type}</span>
            <span style="font-size: 11px; font-weight: 700; color: ${d.applies ? 'var(--emerald-400)' : 'var(--text-dim)'}">
              ${d.applies ? '● APPLIES' : '○ NO-OP'}
            </span>
          </div>
          <div class="directive-note-text">${d.explanation || ""}</div>
        </div>
        <div class="directive-params">${adjDetails}</div>
      `;

      directivesList.appendChild(card);
    });
  }

  // 8. Render Visualizations with Chart.js
  function renderCharts(resData, reqData) {
    const plan = resData.hourly_plan;
    const hours = reqData.hours;
    const labels = plan.map(p => `${p.hour}:00`);

    // Chart 1: Energy Generation & Balance
    const ctxGen = document.getElementById("chartGeneration").getContext("2d");
    if (chartGeneration) chartGeneration.destroy();

    chartGeneration = new Chart(ctxGen, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Solar Used (kWh)",
            data: plan.map(p => p.solar_used_kwh),
            backgroundColor: "rgba(245, 158, 11, 0.8)",
            borderRadius: 4,
            stack: "gen",
          },
          {
            label: "Grid Purchased (kWh)",
            data: plan.map(p => p.grid_kwh),
            backgroundColor: "rgba(56, 189, 248, 0.8)",
            borderRadius: 4,
            stack: "gen",
          },
          {
            label: "Battery Discharge (kWh)",
            data: plan.map(p => p.battery_action === "discharge" ? p.battery_kwh : 0),
            backgroundColor: "rgba(168, 85, 247, 0.8)",
            borderRadius: 4,
            stack: "gen",
          },
          {
            label: "Campus Demand (kWh)",
            data: hours.map(h => h.demand_kwh),
            type: "line",
            borderColor: "#f43f5e",
            borderWidth: 2.5,
            pointBackgroundColor: "#f43f5e",
            pointRadius: 3,
            fill: false,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans" } } },
          tooltip: {
            backgroundColor: "#0e1422",
            borderColor: "rgba(255,255,255,0.1)",
            borderWidth: 1,
            titleFont: { family: "Plus Jakarta Sans" },
            bodyFont: { family: "JetBrains Mono" }
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748b" } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748b" }, title: { display: true, text: "Energy (kWh)", color: "#94a3b8" } }
        }
      }
    });

    // Chart 2: Battery State of Charge (SoC)
    const ctxBattery = document.getElementById("chartBattery").getContext("2d");
    if (chartBattery) chartBattery.destroy();

    const capacity = reqData.battery.capacity_kwh;
    const baseMin = reqData.battery.minimum_energy_kwh;

    chartBattery = new Chart(ctxBattery, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Battery Energy After Hour (kWh)",
            data: plan.map(p => p.battery_energy_after_kwh),
            borderColor: "#38bdf8",
            borderWidth: 3,
            backgroundColor: "rgba(56, 189, 248, 0.12)",
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointHoverRadius: 6,
          },
          {
            label: "Base Min Reserve (kWh)",
            data: Array(24).fill(baseMin),
            borderColor: "#f43f5e",
            borderWidth: 1.5,
            borderDash: [5, 5],
            fill: false,
            pointRadius: 0,
          },
          {
            label: "Capacity Limit (kWh)",
            data: Array(24).fill(capacity),
            borderColor: "#94a3b8",
            borderWidth: 1,
            borderDash: [3, 3],
            fill: false,
            pointRadius: 0,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans" } } },
          tooltip: {
            backgroundColor: "#0e1422",
            borderColor: "rgba(255,255,255,0.1)",
            borderWidth: 1,
            bodyFont: { family: "JetBrains Mono" }
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748b" } },
          y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748b" }, min: 0, max: capacity * 1.1 }
        }
      }
    });

    // Chart 3: Grid Import vs Tariff (Economic Dispatch)
    const ctxTariff = document.getElementById("chartTariff").getContext("2d");
    if (chartTariff) chartTariff.destroy();

    chartTariff = new Chart(ctxTariff, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Grid Purchased (kWh)",
            data: plan.map(p => p.grid_kwh),
            backgroundColor: "rgba(56, 189, 248, 0.75)",
            yAxisID: "yGrid",
            borderRadius: 4,
          },
          {
            label: "Tariff (BDT/kWh)",
            data: hours.map(h => h.tariff_bdt_per_kwh),
            type: "line",
            borderColor: "#fbbf24",
            borderWidth: 2.5,
            pointBackgroundColor: "#fbbf24",
            yAxisID: "yTariff",
            tension: 0.2,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans" } } }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#64748b" } },
          yGrid: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255,255,255,0.05)" },
            ticks: { color: "#38bdf8" },
            title: { display: true, text: "Grid (kWh)", color: "#38bdf8" }
          },
          yTariff: {
            type: "linear",
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { color: "#fbbf24" },
            title: { display: true, text: "Tariff (BDT/kWh)", color: "#fbbf24" }
          }
        }
      }
    });
  }

  // 9. Render Dispatch Table
  function renderTable(plan, hours) {
    tableBody.innerHTML = "";
    plan.forEach((p, h) => {
      const row = document.createElement("tr");
      const hourData = hours[h];
      const cost = (p.grid_kwh * hourData.tariff_bdt_per_kwh).toFixed(2);

      row.innerHTML = `
        <td style="font-weight: 700; font-family: var(--font-mono)">${p.hour}:00</td>
        <td>${hourData.demand_kwh.toFixed(1)}</td>
        <td style="color: var(--amber-400)">${hourData.solar_kwh.toFixed(1)}</td>
        <td style="color: var(--amber-400); font-weight: 600">${p.solar_used_kwh.toFixed(1)}</td>
        <td style="color: var(--cyan-400); font-weight: 600">${p.grid_kwh.toFixed(1)}</td>
        <td><span class="badge-action ${p.battery_action}">${p.battery_action}</span></td>
        <td style="font-family: var(--font-mono)">${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) : "—"}</td>
        <td style="font-weight: 600">${p.battery_energy_after_kwh.toFixed(1)}</td>
        <td>${hourData.tariff_bdt_per_kwh.toFixed(1)}</td>
        <td style="font-weight: 700; color: var(--emerald-400)">${cost}</td>
      `;
      tableBody.appendChild(row);
    });
  }

  // 10. Tab Switching
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // Init
  initPresets();
  checkHealth();
  setInterval(checkHealth, 15000);

  // Auto-run first scenario for instant preview!
  setTimeout(runOptimization, 400);
});
