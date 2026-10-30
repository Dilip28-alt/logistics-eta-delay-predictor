# Data Provenance, Public Schema Attribution & Lawful Use

**Project**: Logistics ETA Estimation & Delay Risk Intelligence Platform  
**Compliance Mandate**: Transparent provenance, lawful data usage, and intellectual property compliance.

---

## 1. Data Origin & Generation Strategy

In strict adherence to lawful use principles and privacy protections:
- **100% Synthetic Data**: All shipment transactions, tracking events, carrier records, facility queues, and weather disruption windows in this project are **synthetically generated** using deterministic pseudorandom mathematics (`src/generator/generator.py`).
- **Zero Confidential / PII Exposure**: No proprietary carrier data, actual customer addresses, private telematics streams, or personal identifiable information (PII) were scraped, accessed, or incorporated.
- **Lawful & Redistributable**: All generated datasets, schemas, and code are completely free of access control restrictions and fully licensed for public redistribution under standard open-source terms.

---

## 2. Public Standards & Schema Inspiration Reference

To ensure industrial realism, our data dictionary and entity modeling draw structural inspiration from established international freight standards and public open-access ontologies:

1. **Open Logistics Foundation / UN/CEFACT (United Nations Centre for Trade Facilitation and Electronic Business)**
   - *Reference*: UN/CEFACT Buy-Ship-Pay (BSP) and Supply Chain Reference Data Model (SCRDM).
   - *Inspiration*: Milestone scan codes (`GATE_IN`, `DEPARTURE`, `TRANSFER_ARRIVAL`, `DELIVERED`), dual-timestamp telemetry patterns (`event_time` vs `ingestion_time`), and multi-leg sequence indexing.
   - *License/Terms*: Open UN public domain standards.

2. **National Weather Service (NOAA / NWS) Severe Weather Taxonomy**
   - *Reference*: NOAA National Weather Service Event Severity Categories.
   - *Inspiration*: Meteorological classification tiers (`MODERATE`, `SEVERE`, `EXTREME`) and disruption multipliers for road transit corridors.
   - *License/Terms*: Public domain (U.S. Federal Government work).

3. **Bureau of Transportation Statistics (BTS) Freight Analysis Framework (FAF5)**
   - *Reference*: U.S. Department of Transportation Freight Analysis Framework (FAF5 Network Data).
   - *Inspiration*: North American freight corridors (Midwest, Northeast, Southeast, Southwest, Pacific), intermodal transit speeds, and road circuity factors (1.12 - 1.25 over haversine distance).
   - *License/Terms*: Public domain.

---

## 3. Discarded Fields & Synthetic Transformation Record

| External Reference Entity | Discarded Proprietary Fields | Retained & Synthesized Fields | Rationale |
|---|---|---|---|
| Commercial Bill of Lading (BOL) | Driver Social Security Numbers, Customer Payment Card Details, Tax IDs. | Shipment ID, Origin, Destination, Weight, Cargo Value, Service Level. | Eliminates all privacy risks while preserving logistics scheduling constraints. |
| Heavy Vehicle Telematics (J1939) | Engine serial numbers, vehicle VIN, proprietary ECU sensor dumps. | In-transit GPS lat/lon, status codes, speed, event timestamp, ingestion timestamp. | Standardizes telemetry stream to core movement milestones. |
| Carrier Freight Billing | Margin percentages, private discount tariffs, billing entity corporate addresses. | SLA penalty per delayed hour, service level name, transit tolerance window. | Focuses purely on SLA compliance and delay cost attribution. |
