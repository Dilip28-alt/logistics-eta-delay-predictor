"""
FastAPI Application and Interactive Operational Dashboard.
Provides REST APIs for ETA estimation, risk monitoring, what-if simulations, and anomaly inspection.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.generator.generator import SyntheticDataGenerator
from src.engine.eta_predictor import ETAPredictor
from src.engine.exception_handler import OperationalExceptionHandler
from src.engine.delay_classifier import DelayClassifierEvaluator
from src.validator.validator import DataValidator


app = FastAPI(
    title="Logistics ETA & Delay Risk Intelligence Platform",
    description="Operational workflow engine combining carrier events, route plans, weather and facility queues.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state
DATA_GENERATOR: Optional[SyntheticDataGenerator] = None
ETA_ENGINE: Optional[ETAPredictor] = None
EXCEPTION_ENGINE: Optional[OperationalExceptionHandler] = None
EVALUATION_SCORECARD: Optional[Dict[str, Any]] = None


def get_generator() -> SyntheticDataGenerator:
    global DATA_GENERATOR, ETA_ENGINE, EXCEPTION_ENGINE
    if DATA_GENERATOR is None:
        # Default starter generation for fast API initialization
        DATA_GENERATOR = SyntheticDataGenerator(seed=20261022)
        DATA_GENERATOR.generate_all(num_shipments=1000, num_facilities=100, num_disruptions=1000)
        ETA_ENGINE = ETAPredictor(DATA_GENERATOR)
        EXCEPTION_ENGINE = OperationalExceptionHandler(DATA_GENERATOR)
    return DATA_GENERATOR


class ETAPredictRequest(BaseModel):
    shipment_id: str
    as_of_ts: Optional[str] = None
    override_weather_multiplier: Optional[float] = None
    override_facility_dwell_hours: Optional[float] = None


@app.on_event("startup")
def startup_event():
    get_generator()


@app.get("/api/health")
def health():
    gen = get_generator()
    return {
        "status": "healthy",
        "system": "Logistics ETA & Delay Risk Intelligence Platform",
        "seed": gen.seed,
        "volume": gen.summary(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/shipments")
def list_shipments(
    status: Optional[str] = None,
    is_delayed: Optional[bool] = None,
    service_level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    gen = get_generator()
    filtered = gen.shipments

    if status:
        filtered = [s for s in filtered if s.current_status == status]
    if is_delayed is not None:
        filtered = [s for s in filtered if s.is_delayed == is_delayed]
    if service_level:
        filtered = [s for s in filtered if s.service_level_id == service_level]

    total = len(filtered)
    page = filtered[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "shipments": [s.to_dict() for s in page]
    }


@app.get("/api/shipments/{shipment_id}")
def get_shipment_detail(shipment_id: str):
    gen = get_generator()
    shipment = next((s for s in gen.shipments if s.shipment_id == shipment_id), None)
    if not shipment:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

    legs = [l.to_dict() for l in gen.shipment_legs if l.shipment_id == shipment_id]
    events = [t.to_dict() for t in gen.tracking_events if t.shipment_id == shipment_id]
    events.sort(key=lambda x: x["event_sequence"])
    etas = [e.to_dict() for e in gen.eta_estimates if e.shipment_id == shipment_id]
    gt = next((g.to_dict() for g in gen.ground_truth if g.entity_id == shipment_id), None)

    return {
        "shipment": shipment.to_dict(),
        "legs": legs,
        "tracking_events": events,
        "eta_snapshots": etas,
        "ground_truth": gt
    }


@app.get("/api/facilities")
def list_facilities(region: Optional[str] = None):
    gen = get_generator()
    facs = gen.facilities
    if region:
        facs = [f for f in facs if f.region == region]
    return {"total": len(facs), "facilities": [f.to_dict() for f in facs]}


@app.get("/api/weather")
def list_weather(region: Optional[str] = None):
    gen = get_generator()
    events = gen.weather_events
    if region:
        events = [w for w in events if w.region == region]
    return {"total": len(events), "weather_events": [w.to_dict() for w in events[:100]]}


@app.post("/api/predict_eta")
def predict_eta(req: ETAPredictRequest):
    global ETA_ENGINE
    get_generator()
    as_of = None
    if req.as_of_ts:
        try:
            as_of = datetime.fromisoformat(req.as_of_ts.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ISO timestamp format")

    try:
        res = ETA_ENGINE.predict(
            shipment_id=req.shipment_id,
            as_of_ts=as_of,
            override_weather_multiplier=req.override_weather_multiplier,
            override_facility_dwell_hours=req.override_facility_dwell_hours
        )
        return res.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/anomalies")
def get_anomalies():
    global EXCEPTION_ENGINE
    get_generator()
    remediations = EXCEPTION_ENGINE.scan_and_remediate(auto_apply=False)
    summary = EXCEPTION_ENGINE.get_summary()
    return {
        "summary": summary,
        "detected_anomalies": [r.to_dict() for r in remediations]
    }


@app.get("/api/evaluation")
def get_evaluation():
    global EVALUATION_SCORECARD
    gen = get_generator()
    if EVALUATION_SCORECARD is None:
        evaluator = DelayClassifierEvaluator(gen)
        EVALUATION_SCORECARD = evaluator.train_and_evaluate()
    return EVALUATION_SCORECARD


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """
    Renders rich interactive operational web UI.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Logistics ETA & Delay Risk Intelligence Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen">
    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-indigo-500/30">
                    <i class="fa-solid fa-truck-fast"></i>
                </div>
                <div>
                    <h1 class="text-lg font-bold tracking-tight text-white">Logistics ETA & Delay Risk Platform</h1>
                    <p class="text-xs text-slate-400">Carrier Events • Multi-Leg Routes • Weather Disruption • Facility Dwell</p>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-400 border border-emerald-800">
                    <span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    Live Engine Online
                </span>
                <a href="/docs" target="_blank" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition border border-slate-700">
                    <i class="fa-solid fa-book-open mr-1.5"></i>Swagger API
                </a>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <!-- KPI Ribbon -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Shipments</span>
                    <i class="fa-solid fa-box text-indigo-400"></i>
                </div>
                <div class="mt-2 text-2xl font-bold text-white" id="kpi-shipments">1,000</div>
                <div class="mt-1 text-xs text-emerald-400 flex items-center"><i class="fa-solid fa-check mr-1"></i> Multi-leg network active</div>
            </div>
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Delayed Shipments</span>
                    <i class="fa-solid fa-triangle-exclamation text-amber-400"></i>
                </div>
                <div class="mt-2 text-2xl font-bold text-amber-400" id="kpi-delayed">--</div>
                <div class="mt-1 text-xs text-slate-400">SLA threshold breach rate</div>
            </div>
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">ETA MAE Precision</span>
                    <i class="fa-solid fa-clock-rotate-left text-cyan-400"></i>
                </div>
                <div class="mt-2 text-2xl font-bold text-cyan-400" id="kpi-mae">--</div>
                <div class="mt-1 text-xs text-slate-400">Mean absolute error (mins)</div>
            </div>
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-slate-400 uppercase tracking-wider">Exceptions Detected</span>
                    <i class="fa-solid fa-shield-halved text-rose-400"></i>
                </div>
                <div class="mt-2 text-2xl font-bold text-rose-400" id="kpi-anomalies">--</div>
                <div class="mt-1 text-xs text-slate-400">Edge cases audited</div>
            </div>
        </div>

        <!-- Tab Controls -->
        <div class="border-b border-slate-800 flex space-x-6">
            <button onclick="switchTab('shipments')" id="tab-btn-shipments" class="pb-3 text-sm font-semibold text-indigo-400 border-b-2 border-indigo-500">
                <i class="fa-solid fa-list-check mr-1.5"></i>Live Shipments
            </button>
            <button onclick="switchTab('simulator')" id="tab-btn-simulator" class="pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200">
                <i class="fa-solid fa-sliders mr-1.5"></i>What-If ETA Simulator
            </button>
            <button onclick="switchTab('anomalies')" id="tab-btn-anomalies" class="pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200">
                <i class="fa-solid fa-bug mr-1.5"></i>Exception & Anomaly Audit
            </button>
            <button onclick="switchTab('metrics')" id="tab-btn-metrics" class="pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200">
                <i class="fa-solid fa-chart-line mr-1.5"></i>Model Evaluation Scorecard
            </button>
        </div>

        <!-- Tab 1: Live Shipments -->
        <div id="tab-shipments" class="space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <select id="filter-status" onchange="loadShipments()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-2 text-slate-300">
                        <option value="">All Statuses</option>
                        <option value="IN_TRANSIT">In Transit</option>
                        <option value="DELIVERED">Delivered</option>
                    </select>
                    <select id="filter-delayed" onchange="loadShipments()" class="bg-slate-900 border border-slate-700 text-xs rounded-lg px-3 py-2 text-slate-300">
                        <option value="">All Timing</option>
                        <option value="true">Delayed Only</option>
                        <option value="false">On-Time Only</option>
                    </select>
                </div>
                <button onclick="loadShipments()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold rounded-lg text-slate-300">
                    <i class="fa-solid fa-arrows-rotate mr-1.5"></i>Refresh
                </button>
            </div>

            <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                            <tr>
                                <th class="px-4 py-3">Shipment ID</th>
                                <th class="px-4 py-3">Route (Origin → Dest)</th>
                                <th class="px-4 py-3">Service Level</th>
                                <th class="px-4 py-3">Status</th>
                                <th class="px-4 py-3">Planned Delivery</th>
                                <th class="px-4 py-3">Actual Delay</th>
                                <th class="px-4 py-3">Delay Root Cause</th>
                                <th class="px-4 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="shipments-table-body" class="divide-y divide-slate-800 font-mono">
                            <tr><td colspan="8" class="text-center py-8 text-slate-500">Loading shipments...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 2: What-If ETA Simulator -->
        <div id="tab-simulator" class="hidden space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
                    <h2 class="text-base font-bold text-white flex items-center">
                        <i class="fa-solid fa-wand-magic-sparkles text-indigo-400 mr-2"></i>Simulation Parameters
                    </h2>
                    <div>
                        <label class="block text-xs font-medium text-slate-400 mb-1">Select Shipment ID</label>
                        <input type="text" id="sim-shipment-id" value="SHP-2026-000001" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-400 mb-1">Weather Impact Multiplier (1.0 = Normal, 2.5 = Blizzard)</label>
                        <input type="range" id="sim-weather" min="1.0" max="3.0" step="0.1" value="1.0" oninput="document.getElementById('weather-val').innerText = this.value + 'x'" class="w-full">
                        <span id="weather-val" class="text-xs font-mono text-cyan-400">1.0x</span>
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-400 mb-1">Intermediate Hub Dwell Override (Hours)</label>
                        <input type="range" id="sim-dwell" min="1.0" max="12.0" step="0.5" value="2.5" oninput="document.getElementById('dwell-val').innerText = this.value + ' hrs'" class="w-full">
                        <span id="dwell-val" class="text-xs font-mono text-amber-400">2.5 hrs</span>
                    </div>
                    <button onclick="runSimulation()" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-lg transition shadow-md shadow-indigo-600/30">
                        <i class="fa-solid fa-bolt mr-1.5"></i>Run ETA Prediction
                    </button>
                </div>

                <div class="md:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
                    <h2 class="text-base font-bold text-white flex items-center">
                        <i class="fa-solid fa-compass text-emerald-400 mr-2"></i>Point-in-Time Prediction & Explainability
                    </h2>
                    <div id="sim-result" class="space-y-4 text-xs">
                        <p class="text-slate-500">Run a simulation to view projected delivery, confidence intervals (P10/P90), and factor breakdown.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab 3: Exception & Anomaly Audit -->
        <div id="tab-anomalies" class="hidden space-y-4">
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h2 class="text-base font-bold text-white mb-2">Automated Data Quality & Operational Exception Audit</h2>
                <p class="text-xs text-slate-400 mb-4">Continuously audits streams for the 4 core edge cases: Ingestion Time Inversion, Impossible Route Sequence, ETA Leakage, and Delivered-in-Transit Desynchronization.</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-950/60 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                            <tr>
                                <th class="px-4 py-3">Exception ID</th>
                                <th class="px-4 py-3">Shipment ID</th>
                                <th class="px-4 py-3">Issue Type</th>
                                <th class="px-4 py-3">Severity</th>
                                <th class="px-4 py-3">Description</th>
                                <th class="px-4 py-3">Recommended Remediation</th>
                            </tr>
                        </thead>
                        <tbody id="anomalies-table-body" class="divide-y divide-slate-800 font-mono">
                            <tr><td colspan="6" class="text-center py-8 text-slate-500">Auditing stream...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab 4: Evaluation Scorecard -->
        <div id="tab-metrics" class="hidden space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
                <h2 class="text-base font-bold text-white">Machine Learning & Heuristic Model Performance</h2>
                <div id="metrics-content" class="text-xs space-y-4">
                    <p class="text-slate-500">Loading benchmark evaluation metrics...</p>
                </div>
            </div>
        </div>
    </main>

    <!-- Shipment Detail Modal -->
    <div id="detail-modal" class="fixed inset-0 bg-black/75 z-50 hidden flex items-center justify-center p-4">
        <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                    <h3 class="text-base font-bold text-white" id="modal-title">Shipment Detail</h3>
                    <p class="text-xs text-slate-400" id="modal-subtitle">Milestones and timeline</p>
                </div>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white text-lg">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div id="modal-body" class="space-y-4 text-xs font-mono">
                Loading...
            </div>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            ['shipments', 'simulator', 'anomalies', 'metrics'].forEach(t => {
                document.getElementById('tab-' + t).classList.add('hidden');
                document.getElementById('tab-btn-' + t).className = 'pb-3 text-sm font-semibold text-slate-400 hover:text-slate-200';
            });
            document.getElementById('tab-' + tabId).classList.remove('hidden');
            document.getElementById('tab-btn-' + tabId).className = 'pb-3 text-sm font-semibold text-indigo-400 border-b-2 border-indigo-500';

            if (tabId === 'anomalies') loadAnomalies();
            if (tabId === 'metrics') loadMetrics();
        }

        async function init() {
            await loadShipments();
            await loadMetrics(true);
            await loadAnomalies(true);
        }

        async function loadShipments() {
            const status = document.getElementById('filter-status').value;
            const isDelayed = document.getElementById('filter-delayed').value;
            let url = '/api/shipments?limit=25';
            if (status) url += '&status=' + status;
            if (isDelayed) url += '&is_delayed=' + isDelayed;

            const res = await fetch(url);
            const data = await res.json();
            const tbody = document.getElementById('shipments-table-body');
            tbody.innerHTML = '';

            let delayedCount = 0;
            data.shipments.forEach(s => {
                if (s.is_delayed) delayedCount++;
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="px-4 py-3 font-semibold text-indigo-300">${s.shipment_id}</td>
                    <td class="px-4 py-3 text-slate-300">${s.origin_facility_id} → ${s.destination_facility_id} (${s.total_legs} leg${s.total_legs > 1 ? 's' : ''})</td>
                    <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${s.service_level_id === 'SL-CRIT' ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-slate-800 text-slate-300'}">${s.service_level_id}</span></td>
                    <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${s.current_status === 'DELIVERED' ? 'bg-emerald-950 text-emerald-400' : 'bg-blue-950 text-blue-400'}">${s.current_status}</span></td>
                    <td class="px-4 py-3 text-slate-400">${s.planned_delivery_ts}</td>
                    <td class="px-4 py-3 ${s.is_delayed ? 'text-rose-400 font-bold' : 'text-emerald-400'}">${s.final_delay_minutes}m</td>
                    <td class="px-4 py-3 text-slate-400">${s.primary_delay_reason_id || 'On-Time'}</td>
                    <td class="px-4 py-3 text-right">
                        <button onclick="viewShipment('${s.shipment_id}')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px]">Inspect</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            document.getElementById('kpi-shipments').innerText = data.total;
        }

        async function viewShipment(id) {
            const modal = document.getElementById('detail-modal');
            modal.classList.remove('hidden');
            document.getElementById('modal-title').innerText = 'Shipment Timeline: ' + id;
            document.getElementById('modal-body').innerHTML = '<div class="text-center py-4">Loading details...</div>';

            const res = await fetch('/api/shipments/' + id);
            const data = await res.json();
            const s = data.shipment;

            let html = `
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs">
                    <div><span class="text-slate-500 block">SLA Level</span><span class="font-bold text-white">${s.service_level_id}</span></div>
                    <div><span class="text-slate-500 block">Status</span><span class="font-bold text-indigo-400">${s.current_status}</span></div>
                    <div><span class="text-slate-500 block">Planned Delivery</span><span class="text-slate-300">${s.planned_delivery_ts}</span></div>
                    <div><span class="text-slate-500 block">Delay</span><span class="${s.is_delayed ? 'text-rose-400' : 'text-emerald-400'} font-bold">${s.final_delay_minutes} mins</span></div>
                </div>

                <div class="space-y-2">
                    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Multi-Leg Routing</h4>
                    <div class="space-y-1">
                        ${data.legs.map(l => `
                            <div class="flex items-center justify-between p-2.5 bg-slate-950/50 rounded-lg border border-slate-800">
                                <div><span class="font-bold text-indigo-400">${l.leg_id}</span> (${l.origin_facility_id} → ${l.destination_facility_id})</div>
                                <div class="text-slate-400">${l.leg_distance_km} km • Carrier ${l.carrier_id}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="space-y-2">
                    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Milestone Scans (${data.tracking_events.length})</h4>
                    <div class="space-y-1 max-h-48 overflow-y-auto">
                        ${data.tracking_events.map(e => `
                            <div class="flex items-center justify-between p-2 bg-slate-950/30 rounded border border-slate-800/60 text-[11px]">
                                <div><span class="text-emerald-400 font-bold">${e.event_type}</span> <span class="text-slate-500">at</span> ${e.event_timestamp}</div>
                                <div class="text-slate-400">Ingested: ${e.ingestion_timestamp} (${e.status_code})</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            document.getElementById('modal-body').innerHTML = html;
        }

        function closeModal() {
            document.getElementById('detail-modal').classList.add('hidden');
        }

        async function runSimulation() {
            const shpId = document.getElementById('sim-shipment-id').value;
            const weather = parseFloat(document.getElementById('sim-weather').value);
            const dwell = parseFloat(document.getElementById('sim-dwell').value);

            const res = await fetch('/api/predict_eta', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    shipment_id: shpId,
                    override_weather_multiplier: weather,
                    override_facility_dwell_hours: dwell
                })
            });

            if (!res.ok) {
                alert('Shipment not found or error occurred.');
                return;
            }

            const data = await res.json();
            const trace = data.decision_trace;

            document.getElementById('sim-result').innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 block text-[10px] uppercase">Predicted Delivery</span>
                        <div class="text-sm font-bold text-white mt-1">${data.predicted_delivery_ts}</div>
                        <div class="text-[11px] text-slate-400 mt-1">Planned: ${data.planned_delivery_ts}</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 block text-[10px] uppercase">Predicted Delay</span>
                        <div class="text-sm font-bold ${data.predicted_delay_minutes > 0 ? 'text-amber-400' : 'text-emerald-400'} mt-1">
                            ${data.predicted_delay_minutes} minutes
                        </div>
                        <div class="text-[11px] text-slate-400 mt-1">Risk Tier: <span class="font-bold text-white">${data.delay_risk_level}</span></div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 block text-[10px] uppercase">Confidence Interval</span>
                        <div class="text-[11px] text-emerald-400 font-bold mt-1">P10: ${data.confidence_interval.p10_optimistic}</div>
                        <div class="text-[11px] text-rose-400 font-bold">P90: ${data.confidence_interval.p90_pessimistic}</div>
                    </div>
                </div>

                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                    <h4 class="text-xs font-bold text-slate-300">Explainability Attribution</h4>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
                        <div><span class="text-slate-500">Remaining Distance:</span> ${trace.remaining_distance_km} km</div>
                        <div><span class="text-slate-500">Carrier Impact:</span> +${trace.carrier_delay_contribution_hours} hrs</div>
                        <div><span class="text-slate-500">Weather Added:</span> +${trace.weather_delay_contribution_hours} hrs</div>
                        <div><span class="text-slate-500">Facility Dwell Added:</span> +${trace.facility_dwell_delay_contribution_hours} hrs</div>
                    </div>
                </div>
            `;
        }

        async function loadAnomalies(silent = false) {
            const res = await fetch('/api/anomalies');
            const data = await res.json();
            document.getElementById('kpi-anomalies').innerText = data.summary.total_exceptions_detected;

            if (silent) return;

            const tbody = document.getElementById('anomalies-table-body');
            tbody.innerHTML = '';
            data.detected_anomalies.forEach(a => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="px-4 py-3 font-semibold text-rose-400">${a.exception_id}</td>
                    <td class="px-4 py-3 text-indigo-300">${a.shipment_id}</td>
                    <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-[10px] bg-amber-950 text-amber-300 border border-amber-800">${a.issue_type}</span></td>
                    <td class="px-4 py-3 font-bold ${a.severity === 'CRITICAL' ? 'text-rose-500' : 'text-amber-400'}">${a.severity}</td>
                    <td class="px-4 py-3 text-slate-300 max-w-xs truncate" title="${a.description}">${a.description}</td>
                    <td class="px-4 py-3 text-slate-400">${a.recommended_action}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        async function loadMetrics(silent = false) {
            const res = await fetch('/api/evaluation');
            const data = await res.json();
            const cls = data.classification_metrics;
            const reg = data.regression_metrics;

            document.getElementById('kpi-mae').innerText = reg.mean_absolute_error_minutes + 'm';
            document.getElementById('kpi-delayed').innerText = (cls.recall * 100).toFixed(1) + '%';

            if (silent) return;

            document.getElementById('metrics-content').innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 uppercase text-[10px]">Precision</span>
                        <div class="text-xl font-bold text-indigo-400 mt-1">${(cls.precision * 100).toFixed(1)}%</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 uppercase text-[10px]">Recall (Delay Capture)</span>
                        <div class="text-xl font-bold text-emerald-400 mt-1">${(cls.recall * 100).toFixed(1)}%</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 uppercase text-[10px]">F1 Score</span>
                        <div class="text-xl font-bold text-cyan-400 mt-1">${cls.f1_score.toFixed(3)}</div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <span class="text-slate-500 uppercase text-[10px]">ROC-AUC</span>
                        <div class="text-xl font-bold text-amber-400 mt-1">${cls.roc_auc.toFixed(3)}</div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <h4 class="text-xs font-bold text-slate-300 mb-2">ETA Regression Accuracy</h4>
                        <div class="space-y-1 text-slate-400 text-xs">
                            <div>• Mean Absolute Error (MAE): <span class="text-white font-bold">${reg.mean_absolute_error_minutes} mins</span></div>
                            <div>• Root Mean Squared Error (RMSE): <span class="text-white font-bold">${reg.root_mean_squared_error_minutes} mins</span></div>
                            <div>• R² Coefficient of Determination: <span class="text-white font-bold">${reg.r2_score}</span></div>
                            <div>• Early Warning Lead Time: <span class="text-emerald-400 font-bold">${data.operational_metrics.early_warning_lead_time_hours} hours prior to SLA target</span></div>
                        </div>
                    </div>
                    <div class="bg-slate-950 p-4 rounded-xl border border-slate-800">
                        <h4 class="text-xs font-bold text-slate-300 mb-2">Top Predictive Feature Drivers</h4>
                        <div class="space-y-1 text-[11px]">
                            ${Object.entries(data.feature_importances).slice(0, 5).map(([k, v]) => `
                                <div class="flex items-center justify-between text-slate-400">
                                    <span>${k}</span>
                                    <span class="font-mono text-indigo-400">${(v * 100).toFixed(1)}%</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
        }

        window.onload = init;
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
