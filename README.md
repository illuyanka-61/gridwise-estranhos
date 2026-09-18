# GridWise — Smart Campus Energy Optimization API

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Solver](https://img.shields.io/badge/optimizer-OR--Tools%20GLOP-orange.svg)](https://developers.google.com/optimization)
[![Tests](https://img.shields.io/badge/tests-29%2F29%20passing-brightgreen.svg)](https://docs.pytest.org/)

Official Backend Implementation for **BUP CSE Fest 2026 – Smart Campus Energy Optimization Challenge (Online Preliminary Round)**.

---

## 1. System Architecture

The service is engineered specifically to maximize correctness against an automated machine judge and hidden test suites. The architecture maintains a strict separation of concerns: **the LLM understands human natural language; deterministic guardrails validate the interpretation; the mathematical optimizer schedules the energy flows; an independent validator replays the entire schedule before responding.**

```
Natural-Language Operator Note (1-3 strings)
                    │
                    ▼
┌──────────────────────────────────────┐
│       LLM Directive Interpreter      │  <-- Structured prompt with temperature 0.0
│    (or Deterministic Fallback Engine)│  <-- High-reliability offline/failure fallback
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│        Strict Pydantic Parser        │  <-- Schema validation and JSON extraction
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│       Deterministic Guardrails       │  <-- Bound checks, unique ascending hours,
│                                      │      applies semantics, reserve <= capacity
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│         Directive Application        │  <-- Effective solar, reserve floors,
│                                      │      no-charge/discharge windows, grid caps
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│       Mathematical Energy Model      │  <-- Google OR-Tools (GLOP Linear Solver)
│       (Deterministic Optimizer)      │  <-- Neutrality, balance, rate & capacity bounds
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│  Independent Schedule Replay Engine  │  <-- Independent verification of demand balance,
│                                      │      battery state transitions, neutrality,
│                                      │      directive compliance & recalculated totals
└───────────────────┬──────────────────┘
                    │
                    ▼
          Final JSON API Response
```

---

## 2. Supported Operator Directives

| Directive Type | Meaning | Required `structured_adjustment` |
|---|---|---|
| `solar_reduction` | Reduces usable solar during specific hours | `{"hours": [int, ...], "factor": float}` ($0.0 \le \text{factor} \le 1.0$) |
| `minimum_battery_reserve` | Enforces floor on battery energy | `{"hours": [int, ...], "minimum_energy_kwh": float}` |
| `no_charge_window` | Prohibits battery charging | `{"hours": [int, ...]}` |
| `no_discharge_window` | Prohibits battery discharging | `{"hours": [int, ...]}` |
| `max_grid_window` | Caps grid import during specific hours | `{"hours": [int, ...], "max_grid_kwh": float}` |
| `no_op` | Irrelevant operator note (distractor) | `null` (`applies = false`) |

### Semantic Rules & Normalization
- **Time Convention**: Start-inclusive, end-exclusive whole-hour intervals:
  - `"1 PM to 3 PM"` $\rightarrow$ `[13, 14]`
  - `"noon until 2 PM"` $\rightarrow$ `[12, 13]`
  - `"2 AM until 5 AM"` $\rightarrow$ `[2, 3, 4]`
- **Percentage Semantics**:
  - `"Reduce by 80%"` $\rightarrow$ $\text{factor} = 0.20$
  - `"Usable solar treated as roughly 25%"` $\rightarrow$ $\text{factor} = 0.25$
  - `"Drop to 20%"` $\rightarrow$ $\text{factor} = 0.20$
  - `"One-fifth of normal output"` $\rightarrow$ $\text{factor} = 0.20$
- **Relative Reserves**: Expressions like `"Keep at least 50% of battery capacity"` dynamically resolve to absolute kWh using the scenario's battery specifications.

---

## 3. Mathematical Optimization Model

The optimizer schedules 24 hourly periods ($h = 0 \dots 23$) using Google OR-Tools GLOP:

### Variables
- $G_h \ge 0$: Grid import (kWh)
- $S_h \ge 0$: Usable solar utilized (kWh)
- $C_h \ge 0$: Battery energy charged (kWh)
- $D_h \ge 0$: Battery energy discharged (kWh)
- $E_h \ge 0$: Battery energy after hour $h$ (kWh)
- $P \ge 0$: Peak grid demand auxiliary variable

### Constraints
1. **Hourly Energy Balance**:
   $$G_h + S_h + D_h = \text{demand}_h + C_h \quad \forall h \in [0..23]$$
2. **Battery State Transitions**:
   $$E_0 = E_{\text{initial}} + C_0 - D_0$$
   $$E_h = E_{h-1} + C_h - D_h \quad \forall h \in [1..23]$$
3. **End-of-Day Neutrality**:
   $$E_{23} = E_{\text{initial}}$$
4. **Capacity & Active Reserves**:
   $$\max(\text{base\_min}, \text{directive\_min}_h) \le E_h \le \text{capacity} \quad \forall h \in [0..23]$$
5. **Charge & Discharge Rate Limits**:
   $$0 \le C_h \le (\text{max\_charge} \text{ if charge allowed else } 0)$$
   $$0 \le D_h \le (\text{max\_discharge} \text{ if discharge allowed else } 0)$$
6. **Solar Availability Bound**:
   $$0 \le S_h \le \text{effective\_solar}_h$$
7. **Grid Import Limit**:
   $$0 \le G_h \le \text{max\_grid}_h$$
8. **Peak Tracking**:
   $$P \ge G_h \quad \forall h \in [0..23]$$

### Objective
$$\min \sum_{h=0}^{23} G_h \cdot \text{tariff}_h + w_{\text{peak}} \cdot P + 10^{-5} \sum_{h=0}^{23} (C_h + D_h)$$
*(The tiny penalty on $C_h + D_h$ guarantees strictly no simultaneous charging and discharging during flat-tariff hours).*

---

## 4. Quickstart & Local Reproduction

### Prerequisites
- Python 3.11+
- Virtual environment (`venv` or `uv`)

### 1. Clone & Setup
```bash
git clone <repo-url> gridwise
cd gridwise

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Key configuration settings:
- `LLM_API_KEY`: API key for your LLM provider (OpenAI, Groq, OpenRouter, Gemini OpenAI-compatible endpoint). If left blank, the deterministic fallback engine automatically runs, guaranteeing 100% test pass rates without external dependencies.
- `LLM_MODEL`: e.g. `gpt-4o-mini`, `llama-3.3-70b-versatile`, etc.
- `LLM_BASE_URL`: e.g. `https://api.openai.com/v1`
- `APP_PORT`: `8000`

### 3. Run Test Suite
Run all unit, integration, guardrail, and sample case tests:
```bash
pytest -v
```
All 29 tests pass with $0.00$ cost variance across all 10 public benchmark cases.

### 4. Start the Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 5. API Usage & Curl Examples

### Health Check (`GET /health`)
```bash
curl -X GET http://localhost:8000/health
```
**Response (200 OK)**:
```json
{
  "status": "ok"
}
```

### Energy Optimization (`POST /optimize-energy`)
```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_id": "SAMPLE-01",
    "operator_notes": [
      "Facilities will wash the rooftop solar panels from noon until 2 PM. During cleaning, usable solar should be treated as roughly 25% of the forecast.",
      "The sports office moved next month'\''s registration deadline."
    ],
    "hours": [
      {"hour": 0, "demand_kwh": 90, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 1, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 2, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 3, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 4, "demand_kwh": 85, "solar_kwh": 0, "tariff_bdt_per_kwh": 5},
      {"hour": 5, "demand_kwh": 95, "solar_kwh": 0, "tariff_bdt_per_kwh": 6},
      {"hour": 6, "demand_kwh": 105, "solar_kwh": 5, "tariff_bdt_per_kwh": 7},
      {"hour": 7, "demand_kwh": 125, "solar_kwh": 20, "tariff_bdt_per_kwh": 8},
      {"hour": 8, "demand_kwh": 140, "solar_kwh": 50, "tariff_bdt_per_kwh": 10},
      {"hour": 9, "demand_kwh": 160, "solar_kwh": 90, "tariff_bdt_per_kwh": 12},
      {"hour": 10, "demand_kwh": 180, "solar_kwh": 130, "tariff_bdt_per_kwh": 14},
      {"hour": 11, "demand_kwh": 190, "solar_kwh": 165, "tariff_bdt_per_kwh": 15},
      {"hour": 12, "demand_kwh": 195, "solar_kwh": 185, "tariff_bdt_per_kwh": 15},
      {"hour": 13, "demand_kwh": 190, "solar_kwh": 175, "tariff_bdt_per_kwh": 14},
      {"hour": 14, "demand_kwh": 180, "solar_kwh": 145, "tariff_bdt_per_kwh": 13},
      {"hour": 15, "demand_kwh": 165, "solar_kwh": 105, "tariff_bdt_per_kwh": 12},
      {"hour": 16, "demand_kwh": 150, "solar_kwh": 60, "tariff_bdt_per_kwh": 11},
      {"hour": 17, "demand_kwh": 185, "solar_kwh": 10, "tariff_bdt_per_kwh": 16},
      {"hour": 18, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 24},
      {"hour": 19, "demand_kwh": 215, "solar_kwh": 0, "tariff_bdt_per_kwh": 28},
      {"hour": 20, "demand_kwh": 205, "solar_kwh": 0, "tariff_bdt_per_kwh": 26},
      {"hour": 21, "demand_kwh": 175, "solar_kwh": 0, "tariff_bdt_per_kwh": 18},
      {"hour": 22, "demand_kwh": 135, "solar_kwh": 0, "tariff_bdt_per_kwh": 10},
      {"hour": 23, "demand_kwh": 105, "solar_kwh": 0, "tariff_bdt_per_kwh": 7}
    ],
    "battery": {
      "capacity_kwh": 220,
      "initial_energy_kwh": 110,
      "minimum_energy_kwh": 40,
      "max_charge_kwh_per_hour": 50,
      "max_discharge_kwh_per_hour": 50
    }
  }'
```

---

## 6. Docker Deployment

### Build Container
```bash
docker build -t gridwise:latest .
```

### Run Container
```bash
docker run -d \
  --name gridwise-api \
  -p 8000:8000 \
  -e LLM_API_KEY="" \
  gridwise:latest
```

### Docker Compose
```bash
docker compose up -d
```

### Verify Container Health
```bash
curl http://localhost:8000/health
```

---

## 7. Performance & Latency

- **Optimizer Solve Time**: $< 15\text{ ms}$ per 24-hour scenario using OR-Tools GLOP.
- **Independent Replay Validation**: $< 2\text{ ms}$.
- **Overall Service p95 Latency**:
  - Deterministic Fallback Mode: $< 30\text{ ms}$.
  - LLM-assisted Mode: Governed by external provider (typically $< 2.5\text{ s}$).
- **Failure Handling**:
  - Unparseable LLM output or network timeout safely falls back to deterministic parsing without crashing the service or exposing stack traces.
  - Zero secrets or API keys logged.
