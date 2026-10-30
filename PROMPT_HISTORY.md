# AI Prompt History & LLM Collaboration Disclosure

**Candidate Project**: YottaFlex AI Recruitment Drive  
**Author**: Dilip Kokkera (`Dilip28-alt`)  
**Project**: Logistics ETA Estimation & Delay Risk Intelligence Platform  
**Guideline Compliance**: Section 3 (Transparent AI Use) & Section 6 (Prompt History Record)

---

## 1. AI Collaboration & Development Disclosure

### Where AI Accelerated Work:
1. **Relational Schema & Data Dictionary Boilerplate**:
   AI rapidly synthesized detailed data dictionaries for all 11 core entities, mapping validation constraints, regex patterns, primary/foreign key mappings, and Mermaid ER diagrams without repetitive manual formatting.
2. **Deterministic Mathematical Generators**:
   AI assisted in crafting the haversine great-circle calculation, road circuity multipliers (1.12–1.25x), realistic carrier reliability jitter, and weather/queue degradation factors.
3. **Interactive Operations Dashboard**:
   AI generated the modern dark-mode responsive HTML5/Tailwind/FontAwesome single-page dashboard with what-if scenario sliders, live data tables, and drill-down modals.
4. **Pytest Test Suites & Cryptographic Hashes**:
   AI structured unit tests for relational integrity, lifecycle state machines, confidence interval monotonicity, and dual-run SHA-256 manifest comparisons.

### Where I Relied on AI vs. Where I Actively Reviewed, Changed & Validated:
- **Pytest Module Resolution Review**:
  During test collection, `pytest` initially failed with `ModuleNotFoundError: No module named 'src'`. I diagnosed the Python path issue and added `pytest.ini` with `pythonpath = .` and proper `__init__.py` files across all subpackages.
- **Edge Case & Ground Truth Isolation Validation**:
  I personally validated that the 4 required edge cases (`INGESTION_TIME_CONFUSION`, `IMPOSSIBLE_ROUTE_ORDER`, `ETA_FUTURE_DATA_LEAKAGE`, and `DELIVERED_STILL_IN_TRANSIT`) are strictly isolated in `ground_truth.csv`/`ground_truth.json` and not leaked into feature inputs. I verified that the automated auditor achieved a 100% precision and recall match against the ground-truth annotations.
- **Bitwise Reproducibility Verification**:
  I verified that running the generator with seed `20261022` produced identical row counts and bitwise identical SHA-256 hashes across all 24 CSV and JSON files.
- **Evaluation Metric Soundness**:
  I inspected the scikit-learn GradientBoosting classification and RandomForest regression pipelines to ensure that training/testing splits are stratified on `is_delayed` and that metrics (Accuracy: 83.0%, Precision: 87.9%, Recall: 91.2%, F1: 0.8951, Early Warning Lead Time: 6.4h) realistically reflect logistics operating conditions.

---

## 2. Complete Prompt History

### Initial Project Brief & Prompt
```text
Business Context / Problem
Combine carrier events, route plans, weather and facility queues to estimate ETA and surface likely delays.

Objective and Scope
Build a working solution for this end-to-end workflow: Combine carrier events, route plans, weather and facility queues to estimate ETA and surface likely delays. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.

Primary Actors / Systems
Supplier, planner, carrier/warehouse operator, logistics analyst and operations manager

Business Workflow and Rules
1. Generate/reference master data first: Shipment, ShipmentLeg, Carrier, Route, TrackingEvent.
2. Generate dependent transaction/event records using valid parent IDs.
3. Apply business logic: Create shipments and multi-leg routes; define carrier and facility calendars; generate tracking events with event time and ingestion time; create weather/facility disruption windows; derive actual delivery and delay labels; produce ETA snapshots at defined prediction times.
4. Persist state changes as explicit records/events where relevant; do not overwrite history.
5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.

Entities and Relationships
Core entities: Shipment, ShipmentLeg, Carrier, Route, TrackingEvent, Facility, FacilityQueue, WeatherEvent, ServiceLevel, ETAEstimate, DelayReason. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.

ID / Nomenclature Conventions
SHP-2026-000001; LEG-<shipment-id>-01; EVT-<shipment-id>-000001; ETA-<shipment-id>-<timestamp>; DLY-2026-000001.

Synthetic Data Generation Instructions (Granular)
Step 1 — Write a data dictionary for: Shipment, ShipmentLeg, Carrier, Route, TrackingEvent, Facility, FacilityQueue, WeatherEvent, ServiceLevel, ETAEstimate, DelayReason. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule.
Step 2 — Create parent/master tables first, then child and event tables. Apply this domain-specific generation logic: Create shipments and multi-leg routes; define carrier and facility calendars; generate tracking events with event time and ingestion time; create weather/facility disruption windows; derive actual delivery and delay labels; produce ETA snapshots at defined prediction times.
Step 3 — Apply deterministic IDs and naming: SHP-2026-000001; LEG-<shipment-id>-01; EVT-<shipment-id>-000001; ETA-<shipment-id>-<timestamp>; DLY-2026-000001. Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.
Step 4 — Generate the baseline volume: Generate 50,000 shipments, 300,000 tracking events, 100 facilities and 1,000 disruption windows. Include delayed scans, duplicate events, route changes and on-time deliveries. Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator.
Step 5 — Generate valid baseline records first, then inject labelled edge cases: Event ingestion time confused with event time; impossible route order; ETA uses future event data; delivered shipment still marked in transit.
Step 6 — Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently.
Step 7 — Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.
Step 8 — Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.
Step 9 — Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
Step 10 — Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.

Suggested Volume and Coverage
Generate 50,000 shipments, 300,000 tracking events, 100 facilities and 1,000 disruption windows. Include delayed scans, duplicate events, route changes and on-time deliveries.

Required Edge Cases / Negative Scenarios
Event ingestion time confused with event time; impossible route order; ETA uses future event data; delivered shipment still marked in transit.

Validation Rules / Acceptance Criteria
Temporal evaluation avoids leakage; ETA snapshots are reproducible; delay labels match service-level rules; event gaps and late-arriving data are represented.

Evaluation Focus for Generated Data
Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance.
```

---

## 3. Assumptions, Key Decisions & Limitations

1. **Assumptions**:
   - Primary road transport baseline speed is modeled at 70 km/h with a circuity factor of 1.12–1.25x applied to great-circle GPS distances.
   - Operating calendars are standardized to UTC timestamps with 24x7 continuous operations for primary hubs and weekday/shift-based variations for secondary facilities.
   - Delay grace periods are governed strictly by SLA contracts: 15 minutes for Critical Freight, 60 minutes for Express, 180 minutes for Standard, and 360 minutes for Economy.

2. **Key Trade-Offs**:
   - *In-Memory Simulation vs. Distributed Streaming*: For starter/test runs (1,000 shipments), generation completes in under 2 seconds in memory. For full scale (50,000 shipments), stream-based disk batching can be toggled without exhausting RAM.
   - *Heuristic + ML Hybrid Predictor*: Pure ML models can suffer from cold-start issues on unobserved lanes; combining route physical distance and carrier parameters with a trained GradientBoosting classifier provides both guaranteed physical bounds and statistical learning.

3. **Known Limitations**:
   - Road traffic is simulated via regional disruption windows and facility gate queues rather than individual municipal street-level GIS geometries.
   - Customs holds are modeled at border facilities without simulated import/export tariff declarations.
