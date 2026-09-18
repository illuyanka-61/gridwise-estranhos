/**
 * GridWise Enterprise Energy Management System (EMS)
 * Frontend Application Controller • Production Grade
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  let currentScenario = null;
  let chartGenBalance = null;
  let chartBatterySoC = null;
  let chartTariffGrid = null;
  let isOptimizing = false;

  // DOM Elements - Sidebar Controls
  const presetSelect = document.getElementById("scenarioPresetSelect");
  const notesContainer = document.getElementById("notesListContainer");
  const btnAddNote = document.getElementById("btnAddNote");
  const btnRunOptimizer = document.getElementById("btnRunOptimizer");

  // BESS Inputs
  const paramCapacity = document.getElementById("paramCapacity");
  const paramInitial = document.getElementById("paramInitial");
  const paramReserve = document.getElementById("paramReserve");
  const paramMaxCharge = document.getElementById("paramMaxCharge");
  const paramMaxDischarge = document.getElementById("paramMaxDischarge");

  // Header & Status
  const systemStatusPill = document.getElementById("systemStatusPill");
  const systemStatusText = document.getElementById("systemStatusText");

  // KPIs
  const kpiCost = document.getElementById("kpiCost");
  const kpiGridTotal = document.getElementById("kpiGridTotal");
  const kpiPeakGrid = document.getElementById("kpiPeakGrid");
  const kpiNeutrality = document.getElementById("kpiNeutrality");

  // Summaries & Directives
  const auditStrategySummaryText = document.getElementById("auditStrategySummaryText");
  const directivesGridContainer = document.getElementById("directivesGridContainer");

  // Ledger Table & Totals
  const ledgerBody = document.getElementById("dispatchLedgerBody");
  const footDemand = document.getElementById("footDemand");
  const footSolarAvail = document.getElementById("footSolarAvail");
  const footSolarUsed = document.getElementById("footSolarUsed");
  const footGrid = document.getElementById("footGrid");
  const footBatteryFlow = document.getElementById("footBatteryFlow");
  const footEndSoC = document.getElementById("footEndSoC");
  const footCost = document.getElementById("footCost");

  // JSON Viewer & Toast
  const codeViewerBlock = document.getElementById("codeViewerBlock");
  const btnCopyJson = document.getElementById("btnCopyJson");
  const toastBanner = document.getElementById("emsToast");
  const toastMsg = document.getElementById("toastMsg");

  // Toast Notification System
  function showToast(message, isError = false) {
    toastMsg.textContent = message;
    toastBanner.style.borderColor = isError ? "var(--danger-rose)" : "var(--border-default)";
    toastBanner.classList.add("show");
    setTimeout(() => {
      toastBanner.classList.remove("show");
    }, 3500);
  }

  // 1. Initialize Scenario Presets
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
    customOpt.textContent = "Custom Operating Scenario";
    presetSelect.appendChild(customOpt);

    presetSelect.addEventListener("change", (e) => loadPreset(e.target.value));

    if (presets.length > 0) {
      loadPreset(0);
    }
  }

  // 2. Load Preset Data
  function loadPreset(idx) {
    const presets = window.SAMPLE_PRESETS || [];
    if (idx === "custom" || !presets[idx]) {
      currentScenario = {
        scenario_id: "CUSTOM-01",
        operator_notes: [
          "Expect an 80% reduction in rooftop solar between 11 AM and 2 PM due to maintenance.",
          "The battery charger will be isolated from 2 PM until 4 PM."
        ],
        hours: Array.from({ length: 24 }, (_, h) => ({
          hour: h,
          demand_kwh: Math.round(110 + Math.sin(h / 3.5) * 35),
          solar_kwh: (h >= 7 && h <= 17) ? Math.max(0, Math.round(150 - Math.abs(h - 12) * 28)) : 0,
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

    renderInputs();
  }

  // 3. Render Inputs to Controls
  function renderInputs() {
    if (!currentScenario) return;

    paramCapacity.value = currentScenario.battery.capacity_kwh;
    paramInitial.value = currentScenario.battery.initial_energy_kwh;
    paramReserve.value = currentScenario.battery.minimum_energy_kwh;
    paramMaxCharge.value = currentScenario.battery.max_charge_kwh_per_hour;
    paramMaxDischarge.value = currentScenario.battery.max_discharge_kwh_per_hour;

    renderNotes();
  }

  // 4. Render Notes List
  function renderNotes() {
    notesContainer.innerHTML = "";
    const notes = currentScenario.operator_notes || [];

    notes.forEach((note, i) => {
      const row = document.createElement("div");
      row.className = "note-row";
      row.innerHTML = `
        <div class="note-row-top">
          <span class="note-num">NOTE [${i}]</span>
          ${notes.length > 1 ? `<button type="button" class="note-remove-link" data-index="${i}">Remove</button>` : ""}
        </div>
        <textarea class="note-text-editor" data-index="${i}" rows="2">${note}</textarea>
      `;
      notesContainer.appendChild(row);
    });

    // Update note listeners
    document.querySelectorAll(".note-text-editor").forEach(ta => {
      ta.addEventListener("input", (e) => {
        const i = parseInt(e.target.dataset.index);
        currentScenario.operator_notes[i] = e.target.value;
      });
    });

    document.querySelectorAll(".note-remove-link").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const i = parseInt(e.target.dataset.index);
        currentScenario.operator_notes.splice(i, 1);
        renderNotes();
      });
    });

    btnAddNote.style.display = notes.length >= 3 ? "none" : "inline-flex";
  }

  btnAddNote.addEventListener("click", () => {
    if ((currentScenario.operator_notes || []).length < 3) {
      currentScenario.operator_notes.push("");
      renderNotes();
    }
  });

  // Quick Directive Injector Chips
  document.querySelectorAll(".preset-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const noteText = chip.dataset.note;
      const notes = currentScenario.operator_notes || [];
      if (notes.length < 3) {
        notes.push(noteText);
      } else {
        notes[notes.length - 1] = noteText;
      }
      renderNotes();
      showToast("Injected directive note");
    });
  });

  // 5. System Health Check
  async function checkBackendHealth() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        const data = await res.json();
        if (data.status === "ok") {
          systemStatusPill.classList.remove("offline");
          systemStatusText.textContent = "Online (200 OK)";
          return;
        }
      }
    } catch (err) {
      console.warn("Backend poll error:", err);
    }
    systemStatusPill.classList.add("offline");
    systemStatusText.textContent = "Offline (Connection Error)";
  }

  // 6. Run Mathematical Optimization
  async function executeOptimization() {
    if (isOptimizing) return;
    isOptimizing = true;
    btnRunOptimizer.disabled = true;
    btnRunOptimizer.innerHTML = `
      <svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
        <path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path>
      </svg>
      Computing Optimal Schedule...
    `;

    // Sync state from inputs
    currentScenario.battery.capacity_kwh = parseFloat(paramCapacity.value) || 200;
    currentScenario.battery.initial_energy_kwh = parseFloat(paramInitial.value) || 100;
    currentScenario.battery.minimum_energy_kwh = parseFloat(paramReserve.value) || 40;
    currentScenario.battery.max_charge_kwh_per_hour = parseFloat(paramMaxCharge.value) || 50;
    currentScenario.battery.max_discharge_kwh_per_hour = parseFloat(paramMaxDischarge.value) || 50;

    // Filter empty notes
    currentScenario.operator_notes = (currentScenario.operator_notes || []).filter(n => n && n.trim().length > 0);
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

      const latencyMs = Math.round(performance.now() - t0);

      if (!response.ok) {
        const errPayload = await response.json().catch(() => ({}));
        showToast(`Optimization Failed (${response.status}): ${errPayload.detail || "Check scenario bounds"}`, true);
        return;
      }

      const planResult = await response.json();
      renderPlanResults(planResult, latencyMs);
      showToast(`Optimization Complete (${latencyMs}ms)`);

      // On mobile viewports, automatically switch to Dispatch Analytics
      if (window.innerWidth < 1024) {
        setMobileView("main");
        window.scrollTo({ top: 0, behavior: "smooth" });
      }

    } catch (err) {
      showToast(`Network request failed: ${err.message}`, true);
    } finally {
      isOptimizing = false;
      btnRunOptimizer.disabled = false;
      btnRunOptimizer.innerHTML = `
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        Compute Optimal Dispatch Plan
      `;
    }
  }

  btnRunOptimizer.addEventListener("click", executeOptimization);

  // 7. Render Optimization Results
  function renderPlanResults(data, latencyMs) {
    // 1. KPIs
    kpiCost.textContent = data.total_cost_bdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    kpiGridTotal.textContent = data.total_grid_kwh.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    kpiPeakGrid.textContent = data.peak_grid_kwh.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

    const plan = data.hourly_plan;
    const initE = currentScenario.battery.initial_energy_kwh;
    const finalE = plan[plan.length - 1].battery_energy_after_kwh;
    const deltaE = Math.abs(finalE - initE);

    if (deltaE <= 0.05) {
      kpiNeutrality.textContent = "Verified (E₂₃ = E₀)";
      kpiNeutrality.style.color = "var(--success-emerald)";
    } else {
      kpiNeutrality.textContent = `ΔE = ${deltaE.toFixed(2)} kWh`;
      kpiNeutrality.style.color = "var(--danger-rose)";
    }

    // 2. Strategy & Audit Summary
    auditStrategySummaryText.textContent = `${data.plan_summary} (Solved in ${latencyMs}ms via OR-Tools GLOP)`;

    // 3. Directives List
    renderDirectives(data.directive_interpretation);

    // 4. Visual Charts
    renderCharts(data, currentScenario);

    // 5. 24h Ledger Table & Footers
    renderLedger(data.hourly_plan, currentScenario.hours);

    // 6. JSON Inspector
    codeViewerBlock.textContent = JSON.stringify(data, null, 2);
  }

  // 8. Render Directives
  function renderDirectives(directives) {
    directivesGridContainer.innerHTML = "";
    if (!directives || directives.length === 0) {
      directivesGridContainer.innerHTML = "<span style='font-size: 11px; color: var(--text-muted);'>No active directives extracted.</span>";
      return;
    }

    directives.forEach(d => {
      const item = document.createElement("div");
      item.className = "directive-badge-item";

      let pillClass = "noop";
      let paramStr = "No Schedule Impact";

      if (d.directive_type === "solar_reduction") {
        pillClass = "solar";
        if (d.structured_adjustment) {
          paramStr = `Hours: [${d.structured_adjustment.hours.join(", ")}] • Factor: ${(d.structured_adjustment.factor * 100).toFixed(0)}%`;
        }
      } else if (d.directive_type === "minimum_battery_reserve") {
        pillClass = "battery";
        if (d.structured_adjustment) {
          paramStr = `Hours: [${d.structured_adjustment.hours.join(", ")}] • Reserve: ${d.structured_adjustment.minimum_energy_kwh} kWh`;
        }
      } else if (d.directive_type === "no_charge_window" || d.directive_type === "no_discharge_window") {
        pillClass = "battery";
        if (d.structured_adjustment) {
          paramStr = `Hours: [${d.structured_adjustment.hours.join(", ")}]`;
        }
      } else if (d.directive_type === "max_grid_window") {
        pillClass = "grid";
        if (d.structured_adjustment) {
          paramStr = `Hours: [${d.structured_adjustment.hours.join(", ")}] • Cap: ${d.structured_adjustment.max_grid_kwh} kWh`;
        }
      }

      item.innerHTML = `
        <div class="directive-badge-top">
          <span class="badge-pill ${pillClass}">${d.directive_type}</span>
          <span style="font-size: 10px; font-family: var(--font-data); font-weight: 700; color: ${d.applies ? 'var(--success-emerald)' : 'var(--text-muted)'}">
            ${d.applies ? 'APPLIED' : 'NO-OP'}
          </span>
        </div>
        <div class="directive-note-quote">${d.explanation || ""}</div>
        <div class="directive-exact-params">${paramStr}</div>
      `;

      directivesGridContainer.appendChild(item);
    });
  }

  // 9. Render Dispatch Visualizations
  function renderCharts(resData, reqData) {
    const plan = resData.hourly_plan;
    const hours = reqData.hours;
    const labels = plan.map(p => `${p.hour.toString().padStart(2, "0")}:00`);

    // Chart 1: Generation & Load Balance Stack
    const ctxGen = document.getElementById("canvasGenBalance").getContext("2d");
    if (chartGenBalance) chartGenBalance.destroy();

    chartGenBalance = new Chart(ctxGen, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Solar Utilized",
            data: plan.map(p => p.solar_used_kwh),
            backgroundColor: "#eab308",
            stack: "gen",
            borderRadius: 2,
          },
          {
            label: "Grid Purchased",
            data: plan.map(p => p.grid_kwh),
            backgroundColor: "#38bdf8",
            stack: "gen",
            borderRadius: 2,
          },
          {
            label: "Battery Discharge",
            data: plan.map(p => p.battery_action === "discharge" ? p.battery_kwh : 0),
            backgroundColor: "#a855f7",
            stack: "gen",
            borderRadius: 2,
          },
          {
            label: "Campus Demand",
            data: hours.map(h => h.demand_kwh),
            type: "line",
            borderColor: "#f43f5e",
            borderWidth: 2,
            pointRadius: 2,
            fill: false,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0d131f",
            borderColor: "#1e293b",
            borderWidth: 1,
            titleFont: { family: "Inter", size: 12 },
            bodyFont: { family: "JetBrains Mono", size: 11 },
            padding: 8
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } } },
          y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } } }
        }
      }
    });

    // Chart 2: Battery SoC Curve
    const ctxBattery = document.getElementById("canvasBatterySoC").getContext("2d");
    if (chartBatterySoC) chartBatterySoC.destroy();

    const cap = reqData.battery.capacity_kwh;
    const minReserve = reqData.battery.minimum_energy_kwh;

    chartBatterySoC = new Chart(ctxBattery, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Storage SoC (kWh)",
            data: plan.map(p => p.battery_energy_after_kwh),
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.08)",
            borderWidth: 2,
            fill: true,
            tension: 0.2,
            pointRadius: 2,
          },
          {
            label: "Base Reserve",
            data: Array(24).fill(minReserve),
            borderColor: "#f43f5e",
            borderDash: [4, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
          {
            label: "Nameplate Capacity",
            data: Array(24).fill(cap),
            borderColor: "#64748b",
            borderDash: [2, 2],
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0d131f",
            borderColor: "#1e293b",
            borderWidth: 1,
            bodyFont: { family: "JetBrains Mono", size: 11 }
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 } } },
          y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 } }, min: 0, max: cap * 1.05 }
        }
      }
    });

    // Chart 3: Tariff Arbitrage (Grid vs Price)
    const ctxTariff = document.getElementById("canvasTariffGrid").getContext("2d");
    if (chartTariffGrid) chartTariffGrid.destroy();

    chartTariffGrid = new Chart(ctxTariff, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Grid Intake (kWh)",
            data: plan.map(p => p.grid_kwh),
            backgroundColor: "#38bdf8",
            yAxisID: "yGrid",
            borderRadius: 2,
          },
          {
            label: "Tariff (BDT)",
            data: hours.map(h => h.tariff_bdt_per_kwh),
            type: "line",
            borderColor: "#eab308",
            borderWidth: 2,
            pointRadius: 2,
            yAxisID: "yTariff",
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0d131f",
            borderColor: "#1e293b",
            borderWidth: 1,
            bodyFont: { family: "JetBrains Mono", size: 11 }
          }
        },
        scales: {
          x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 } } },
          yGrid: {
            type: "linear",
            position: "left",
            grid: { color: "rgba(255,255,255,0.03)" },
            ticks: { color: "#38bdf8", font: { family: "JetBrains Mono", size: 9 } }
          },
          yTariff: {
            type: "linear",
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { color: "#eab308", font: { family: "JetBrains Mono", size: 9 } }
          }
        }
      }
    });
  }

  // 10. Render Ledger Table & Calculate Sums
  function renderLedger(plan, hours) {
    ledgerBody.innerHTML = "";

    let sumDemand = 0.0;
    let sumSolarAvail = 0.0;
    let sumSolarUsed = 0.0;
    let sumGrid = 0.0;
    let sumBatteryFlow = 0.0;
    let sumCost = 0.0;

    plan.forEach((p, h) => {
      const hData = hours[h];
      const cost = p.grid_kwh * hData.tariff_bdt_per_kwh;

      sumDemand += hData.demand_kwh;
      sumSolarAvail += hData.solar_kwh;
      sumSolarUsed += p.solar_used_kwh;
      sumGrid += p.grid_kwh;
      sumBatteryFlow += p.battery_kwh;
      sumCost += cost;

      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="font-family: var(--font-data); font-weight: 600;">${p.hour.toString().padStart(2, "0")}:00</td>
        <td class="num-col">${hData.demand_kwh.toFixed(1)}</td>
        <td class="num-col" style="color: var(--text-muted);">${hData.solar_kwh.toFixed(1)}</td>
        <td class="num-col" style="color: var(--solar-amber); font-weight: 600;">${p.solar_used_kwh.toFixed(1)}</td>
        <td class="num-col" style="color: var(--grid-sky); font-weight: 600;">${p.grid_kwh.toFixed(1)}</td>
        <td><span class="action-chip ${p.battery_action}">${p.battery_action}</span></td>
        <td class="num-col" style="color: var(--battery-purple);">${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) : "—"}</td>
        <td class="num-col" style="font-weight: 600;">${p.battery_energy_after_kwh.toFixed(1)}</td>
        <td class="num-col" style="color: var(--text-muted);">${hData.tariff_bdt_per_kwh.toFixed(1)}</td>
        <td class="num-col" style="font-weight: 700; color: #fff;">${cost.toFixed(2)}</td>
      `;
      ledgerBody.appendChild(row);
    });

    // Populate Ledger Totals Footer
    footDemand.textContent = sumDemand.toFixed(1);
    footSolarAvail.textContent = sumSolarAvail.toFixed(1);
    footSolarUsed.textContent = sumSolarUsed.toFixed(1);
    footGrid.textContent = sumGrid.toFixed(1);
    footBatteryFlow.textContent = sumBatteryFlow.toFixed(1);
    footEndSoC.textContent = plan[plan.length - 1].battery_energy_after_kwh.toFixed(1);
    footCost.textContent = sumCost.toFixed(2);

    if (window.innerWidth < 1024) {
      setMobileView("main");
    }
  }

  // 11. Tab Switching
  document.querySelectorAll(".ems-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".ems-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".ems-tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");

      // Force recalculation of chart canvas sizes if charts tab activated
      if (btn.dataset.tab === "tabChartsView") {
        setTimeout(() => {
          chartGenBalance?.resize();
          chartBatterySoC?.resize();
          chartTariffGrid?.resize();
        }, 60);
      }
    });
  });

  // 12. Mobile Segmented View Navigation (< 1024px)
  const emsWorkspace = document.getElementById("emsWorkspace");
  const btnMobileSidebar = document.getElementById("btnMobileViewSidebar");
  const btnMobileMain = document.getElementById("btnMobileViewMain");

  function setMobileView(view) {
    if (!emsWorkspace) return;
    if (view === "sidebar") {
      emsWorkspace.classList.remove("view-main");
      emsWorkspace.classList.add("view-sidebar");
      btnMobileSidebar?.classList.add("active");
      btnMobileMain?.classList.remove("active");
    } else {
      emsWorkspace.classList.remove("view-sidebar");
      emsWorkspace.classList.add("view-main");
      btnMobileMain?.classList.add("active");
      btnMobileSidebar?.classList.remove("active");
      // Resize charts when switching into main panel view
      setTimeout(() => {
        chartGenBalance?.resize();
        chartBatterySoC?.resize();
        chartTariffGrid?.resize();
      }, 60);
    }
  }

  btnMobileSidebar?.addEventListener("click", () => setMobileView("sidebar"));
  btnMobileMain?.addEventListener("click", () => setMobileView("main"));

  // 13. Window Resize Event Listener
  window.addEventListener("resize", () => {
    if (window.innerWidth >= 1024 && emsWorkspace) {
      emsWorkspace.classList.remove("view-sidebar", "view-main");
    } else if (window.innerWidth < 1024 && emsWorkspace && !emsWorkspace.classList.contains("view-main") && !emsWorkspace.classList.contains("view-sidebar")) {
      emsWorkspace.classList.add("view-sidebar");
    }
    chartGenBalance?.resize();
    chartBatterySoC?.resize();
    chartTariffGrid?.resize();
  });

  // 14. Copy JSON Action
  btnCopyJson.addEventListener("click", () => {
    navigator.clipboard.writeText(codeViewerBlock.textContent).then(() => {
      showToast("Copied JSON payload to clipboard");
    }).catch(() => {
      showToast("Clipboard copy failed", true);
    });
  });

  // Startup
  initPresets();
  checkBackendHealth();
  setInterval(checkBackendHealth, 12000);

  // Auto-run initial computation
  setTimeout(executeOptimization, 300);
});
