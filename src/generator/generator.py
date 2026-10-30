"""
High-performance deterministic synthetic data generator for Logistics ETA and Delay Risk Platform.
Supports parameterized scale (starter: 1,000 shipments, full: 50,000 shipments, 300,000 tracking events).
Fixed seed guarantees 100% bitwise reproducibility.
"""

import math
import random
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional

from src.models.entities import (
    Carrier, Facility, Route, ServiceLevel, DelayReason,
    Shipment, ShipmentLeg, TrackingEvent, FacilityQueue,
    WeatherEvent, ETAEstimate, GroundTruth,
    TransportMode, FacilityType, Region, ShipmentStatus, LegStatus,
    EventType, CongestionLevel, WeatherSeverity, WeatherType,
    DelayRiskLevel, AnomalyType
)

# Reference Base Timestamps
SIMULATION_START = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
SIMULATION_END = datetime(2026, 10, 28, 23, 59, 59, tzinfo=timezone.utc)

REGIONS_GEOGRAPHY = {
    Region.MIDWEST.value: {"lat_range": (39.0, 45.0), "lon_range": (-94.0, -82.0), "name": "Midwest Freight Corridor"},
    Region.NORTHEAST.value: {"lat_range": (40.0, 44.5), "lon_range": (-79.0, -71.0), "name": "Northeast Megalopolis"},
    Region.SOUTHEAST.value: {"lat_range": (28.0, 36.5), "lon_range": (-88.0, -78.0), "name": "Southeast Distribution Zone"},
    Region.SOUTHWEST.value: {"lat_range": (29.0, 35.5), "lon_range": (-106.0, -94.0), "name": "Southwest Cross-Border Hub"},
    Region.WEST_COAST.value: {"lat_range": (33.0, 48.0), "lon_range": (-124.0, -117.0), "name": "Pacific Freight Gateway"}
}

SERVICE_LEVEL_DEFS = [
    {
        "id": "SL-CRIT",
        "name": "CRITICAL_FREIGHT",
        "tolerance_mins": 15,
        "target_pct": 99.5,
        "penalty": 500.0,
        "desc": "High-priority critical cargo with 15-minute strict SLA grace window."
    },
    {
        "id": "SL-EXP",
        "name": "EXPRESS",
        "tolerance_mins": 60,
        "target_pct": 98.0,
        "penalty": 250.0,
        "desc": "Expedited commercial freight with 60-minute SLA buffer."
    },
    {
        "id": "SL-STD",
        "name": "STANDARD",
        "tolerance_mins": 180,
        "target_pct": 95.0,
        "penalty": 100.0,
        "desc": "Standard ground and intermodal freight with 3-hour SLA window."
    },
    {
        "id": "SL-ECO",
        "name": "ECONOMY",
        "tolerance_mins": 360,
        "target_pct": 90.0,
        "penalty": 50.0,
        "desc": "Consolidated economy freight with flexible 6-hour delivery tolerance."
    }
]

DELAY_REASON_TAXONOMY = [
    {"id": "DLY-WTH-01", "category": "WEATHER", "sub": "BLIZZARD_ROAD_CLOSURE", "severity": "SEVERE", "carrier_fault": False},
    {"id": "DLY-WTH-02", "category": "WEATHER", "sub": "FLOOD_INTERSTATE_DETOUR", "severity": "SEVERE", "carrier_fault": False},
    {"id": "DLY-WTH-03", "category": "WEATHER", "sub": "DENSE_FOG_SPEED_REDUCTION", "severity": "MODERATE", "carrier_fault": False},
    {"id": "DLY-FAC-01", "category": "FACILITY_CONGESTION", "sub": "GATE_QUEUE_BACKLOG", "severity": "MODERATE", "carrier_fault": False},
    {"id": "DLY-FAC-02", "category": "FACILITY_CONGESTION", "sub": "DOCK_BERTH_UNAVAILABLE", "severity": "SEVERE", "carrier_fault": False},
    {"id": "DLY-CRR-01", "category": "CARRIER_MECHANICAL", "sub": "TRACTOR_ENGINE_BREAKDOWN", "severity": "SEVERE", "carrier_fault": True},
    {"id": "DLY-CRR-02", "category": "CARRIER_MECHANICAL", "sub": "DRIVER_HOS_MAX_HOURS_REST", "severity": "MODERATE", "carrier_fault": True},
    {"id": "DLY-RTE-01", "category": "ROUTE_BLOCKAGE", "sub": "HIGHWAY_CONSTRUCTION_LANE_DROP", "severity": "MODERATE", "carrier_fault": False},
    {"id": "DLY-CST-01", "category": "CUSTOMS_INSPECTION", "sub": "BORDER_SECURITY_SECONDARY_HOLD", "severity": "SEVERE", "carrier_fault": False},
    {"id": "DLY-OPS-01", "category": "OPERATIONAL_MISMATCH", "sub": "DISPATCH_TIMING_DESYNC", "severity": "MODERATE", "carrier_fault": True}
]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class SyntheticDataGenerator:
    def __init__(self, seed: int = 20261022):
        self.seed = seed
        self.rng = random.Random(seed)

        # Storage containers
        self.carriers: List[Carrier] = []
        self.facilities: List[Facility] = []
        self.routes: List[Route] = []
        self.service_levels: List[ServiceLevel] = []
        self.delay_reasons: List[DelayReason] = []
        self.weather_events: List[WeatherEvent] = []
        self.facility_queues: List[FacilityQueue] = []
        self.shipments: List[Shipment] = []
        self.shipment_legs: List[ShipmentLeg] = []
        self.tracking_events: List[TrackingEvent] = []
        self.eta_estimates: List[ETAEstimate] = []
        self.ground_truth: List[GroundTruth] = []

        # Internal lookup indexes
        self.facility_map: Dict[str, Facility] = {}
        self.carrier_map: Dict[str, Carrier] = {}
        self.route_map: Dict[str, Route] = {}
        self.route_by_pair: Dict[Tuple[str, str], Route] = {}

    def generate_all(self, num_shipments: int = 1000, num_facilities: int = 100, num_disruptions: int = 1000):
        """
        Executes end-to-end deterministic generation pipeline.
        Step 2: Parent/master first, then child/transactional, then injected anomalies.
        """
        self.rng.seed(self.seed)

        # 1. Master Reference Data
        self._generate_service_levels()
        self._generate_delay_reasons()
        self._generate_carriers(count=20)
        self._generate_facilities(count=num_facilities)
        self._generate_routes(count=500)

        # 2. Master Disruption Windows (Weather + Facility Queues = num_disruptions)
        weather_count = num_disruptions // 2
        queue_count = num_disruptions - weather_count
        self._generate_weather_events(count=weather_count)
        self._generate_facility_queues(count=queue_count)

        # 3. Shipments, Legs, Tracking Events, ETAs, and Derived Labels
        self._generate_shipments(count=num_shipments)

        return self

    def _generate_service_levels(self):
        for s in SERVICE_LEVEL_DEFS:
            sl = ServiceLevel(
                service_level_id=s["id"],
                service_level_name=s["name"],
                max_delay_tolerance_mins=s["tolerance_mins"],
                target_on_time_pct=s["target_pct"],
                penalty_per_hour_delayed=s["penalty"],
                description=s["desc"]
            )
            self.service_levels.append(sl)

    def _generate_delay_reasons(self):
        for d in DELAY_REASON_TAXONOMY:
            dr = DelayReason(
                delay_reason_id=d["id"],
                category=d["category"],
                sub_reason=d["sub"],
                severity_tier=d["severity"],
                is_carrier_fault=d["carrier_fault"]
            )
            self.delay_reasons.append(dr)

    def _generate_carriers(self, count: int = 20):
        modes = [TransportMode.ROAD.value] * 12 + [TransportMode.RAIL.value] * 4 + [TransportMode.AIR.value] * 2 + [TransportMode.OCEAN.value] * 2
        calendars = ["24x7", "WEEKDAYS_ONLY", "EXTENDED_HOURS"]

        for i in range(1, count + 1):
            cid = f"CRR-{i:03d}"
            mode = modes[i - 1]
            rel = round(self.rng.uniform(0.78, 0.98), 3)
            cal = self.rng.choice(calendars)
            c = Carrier(
                carrier_id=cid,
                carrier_name=f"Carrier-Logistics-{i:02d} ({mode})",
                transport_mode=mode,
                reliability_score=rel,
                operating_calendar=cal,
                contact_email=f"dispatch.operations{i}@carrier-network.com",
                created_at="2026-01-01T00:00:00Z"
            )
            self.carriers.append(c)
            self.carrier_map[cid] = c

    def _generate_facilities(self, count: int = 100):
        fac_types = [
            FacilityType.DISTRIBUTION_CENTER.value,
            FacilityType.CROSS_DOCK.value,
            FacilityType.FULFILLMENT_CENTER.value,
            FacilityType.PORT.value
        ]
        regions = list(REGIONS_GEOGRAPHY.keys())

        for i in range(1, count + 1):
            fid = f"FAC-{i:03d}"
            region = regions[(i - 1) % len(regions)]
            geo = REGIONS_GEOGRAPHY[region]
            lat = round(self.rng.uniform(geo["lat_range"][0], geo["lat_range"][1]), 4)
            lon = round(self.rng.uniform(geo["lon_range"][0], geo["lon_range"][1]), 4)
            ftype = self.rng.choice(fac_types)
            cap = self.rng.randint(25, 150)
            dwell = round(self.rng.uniform(1.0, 4.5), 1)

            f = Facility(
                facility_id=fid,
                facility_name=f"Hub-{region[:3]}-{i:03d} {ftype}",
                facility_type=ftype,
                region=region,
                latitude=lat,
                longitude=lon,
                capacity_trucks_per_hr=cap,
                nominal_dwell_hours=dwell,
                operating_calendar="24x7",
                created_at="2026-01-01T00:00:00Z"
            )
            self.facilities.append(f)
            self.facility_map[fid] = f

    def _generate_routes(self, count: int = 500):
        fac_ids = [f.facility_id for f in self.facilities]
        created_pairs = set()

        for i in range(1, count + 1):
            rid = f"RTE-{i:04d}"
            for _ in range(50):
                orig_id = self.rng.choice(fac_ids)
                dest_id = self.rng.choice(fac_ids)
                if orig_id != dest_id and (orig_id, dest_id) not in created_pairs:
                    created_pairs.add((orig_id, dest_id))
                    break
            else:
                orig_id = fac_ids[(i - 1) % len(fac_ids)]
                dest_id = fac_ids[i % len(fac_ids)]

            orig = self.facility_map[orig_id]
            dest = self.facility_map[dest_id]
            dist = haversine_distance(orig.latitude, orig.longitude, dest.latitude, dest.longitude)
            # Route circuity factor (road freight is ~1.18x haversine)
            dist_km = round(dist * self.rng.uniform(1.12, 1.25), 1)
            dist_km = max(dist_km, 30.0)

            # Assign carrier & speed
            carrier = self.rng.choice(self.carriers)
            avg_speed = 70.0 if carrier.transport_mode == TransportMode.ROAD.value else (
                45.0 if carrier.transport_mode == TransportMode.RAIL.value else 500.0
            )
            transit_hours = round(dist_km / avg_speed, 2)
            is_toll = self.rng.choice([True, False])

            r = Route(
                route_id=rid,
                origin_facility_id=orig_id,
                destination_facility_id=dest_id,
                primary_carrier_id=carrier.carrier_id,
                transport_mode=carrier.transport_mode,
                distance_km=dist_km,
                standard_transit_hours=transit_hours,
                is_toll_road=is_toll,
                created_at="2026-01-01T00:00:00Z"
            )
            self.routes.append(r)
            self.route_map[rid] = r
            self.route_by_pair[(orig_id, dest_id)] = r

    def _generate_weather_events(self, count: int = 500):
        regions = list(REGIONS_GEOGRAPHY.keys())
        w_types = [w.value for w in WeatherType]
        sevs = [WeatherSeverity.MODERATE.value, WeatherSeverity.SEVERE.value, WeatherSeverity.EXTREME.value]

        sim_secs = int((SIMULATION_END - SIMULATION_START).total_seconds())

        for i in range(1, count + 1):
            wid = f"WTH-2026-{i:06d}"
            region = self.rng.choice(regions)
            w_type = self.rng.choice(w_types)
            sev = self.rng.choice(sevs)

            start_offset = self.rng.randint(0, sim_secs - 86400)
            duration_hours = self.rng.randint(4, 48)
            start_dt = SIMULATION_START + timedelta(seconds=start_offset)
            end_dt = start_dt + timedelta(hours=duration_hours)

            multiplier = 1.2 if sev == WeatherSeverity.MODERATE.value else (
                1.5 if sev == WeatherSeverity.SEVERE.value else 2.2
            )
            geo = REGIONS_GEOGRAPHY[region]
            clat = round(self.rng.uniform(geo["lat_range"][0], geo["lat_range"][1]), 4)
            clon = round(self.rng.uniform(geo["lon_range"][0], geo["lon_range"][1]), 4)
            radius = round(self.rng.uniform(100.0, 450.0), 1)

            w = WeatherEvent(
                weather_id=wid,
                region=region,
                event_type=w_type,
                severity=sev,
                start_ts=start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_ts=end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                delay_multiplier=multiplier,
                radius_km=radius,
                center_lat=clat,
                center_lon=clon
            )
            self.weather_events.append(w)

    def _generate_facility_queues(self, count: int = 500):
        fac_ids = [f.facility_id for f in self.facilities]
        sim_secs = int((SIMULATION_END - SIMULATION_START).total_seconds())
        congestions = [
            (CongestionLevel.MODERATE.value, 1.4, 40),
            (CongestionLevel.SEVERE.value, 2.2, 85),
            (CongestionLevel.GRIDLOCK.value, 3.5, 160)
        ]

        for i in range(1, count + 1):
            fid = self.rng.choice(fac_ids)
            fac = self.facility_map[fid]
            snap_offset = self.rng.randint(0, sim_secs)
            snap_dt = SIMULATION_START + timedelta(seconds=snap_offset)
            ts_str = snap_dt.strftime("%Y%m%dT%H%M%SZ")
            qid = f"QUE-{fid}-{ts_str}"

            c_level, dwell_mult, base_trucks = self.rng.choice(congestions)
            queue_depth = int(base_trucks * self.rng.uniform(0.8, 1.3))
            dwell_hrs = round(fac.nominal_dwell_hours * dwell_mult, 1)

            active_berths = max(2, fac.capacity_trucks_per_hr // 10)
            inflow = round(self.rng.uniform(15.0, 45.0), 1)
            outflow = round(inflow * self.rng.uniform(0.6, 0.9), 1)

            q = FacilityQueue(
                queue_id=qid,
                facility_id=fid,
                snapshot_ts=snap_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                queue_depth_trucks=queue_depth,
                avg_dwell_hours=dwell_hrs,
                active_berths=active_berths,
                inflow_rate_per_hr=inflow,
                outflow_rate_per_hr=outflow,
                congestion_level=c_level
            )
            self.facility_queues.append(q)

    def _find_or_create_route(self, orig_id: str, dest_id: str, route_counter: int) -> Route:
        if (orig_id, dest_id) in self.route_by_pair:
            return self.route_by_pair[(orig_id, dest_id)]

        orig = self.facility_map[orig_id]
        dest = self.facility_map[dest_id]
        dist_km = max(35.0, round(haversine_distance(orig.latitude, orig.longitude, dest.latitude, dest.longitude) * 1.18, 1))
        carrier = self.rng.choice(self.carriers)
        transit_hours = round(dist_km / 70.0, 2)
        rid = f"RTE-{route_counter:04d}"

        r = Route(
            route_id=rid,
            origin_facility_id=orig_id,
            destination_facility_id=dest_id,
            primary_carrier_id=carrier.carrier_id,
            transport_mode=carrier.transport_mode,
            distance_km=dist_km,
            standard_transit_hours=transit_hours,
            is_toll_road=False,
            created_at="2026-01-01T00:00:00Z"
        )
        self.routes.append(r)
        self.route_map[rid] = r
        self.route_by_pair[(orig_id, dest_id)] = r
        return r

    def _generate_shipments(self, count: int):
        fac_ids = [f.facility_id for f in self.facilities]
        route_counter = len(self.routes) + 1
        sim_secs = int((SIMULATION_END - SIMULATION_START - timedelta(days=5)).total_seconds())

        # Anomaly targets (~5% total across 4 distinct edge cases)
        num_anomaly_ingestion = max(2, int(count * 0.015))
        num_anomaly_route = max(2, int(count * 0.010))
        num_anomaly_leakage = max(2, int(count * 0.010))
        num_anomaly_desync = max(2, int(count * 0.015))

        anomaly_assignment: Dict[int, AnomalyType] = {}
        all_indices = list(range(1, count + 1))
        self.rng.shuffle(all_indices)

        idx = 0
        for _ in range(num_anomaly_ingestion):
            anomaly_assignment[all_indices[idx]] = AnomalyType.INGESTION_TIME_CONFUSION
            idx += 1
        for _ in range(num_anomaly_route):
            anomaly_assignment[all_indices[idx]] = AnomalyType.IMPOSSIBLE_ROUTE_ORDER
            idx += 1
        for _ in range(num_anomaly_leakage):
            anomaly_assignment[all_indices[idx]] = AnomalyType.ETA_FUTURE_DATA_LEAKAGE
            idx += 1
        for _ in range(num_anomaly_desync):
            anomaly_assignment[all_indices[idx]] = AnomalyType.DELIVERED_STILL_IN_TRANSIT
            idx += 1

        for i in range(1, count + 1):
            shp_id = f"SHP-2026-{i:06d}"
            assigned_anomaly = anomaly_assignment.get(i, AnomalyType.NORMAL)

            # Pick origin, dest, and legs (40% 1-leg, 45% 2-leg, 15% 3-leg)
            orig_id = self.rng.choice(fac_ids)
            dest_id = self.rng.choice(fac_ids)
            while dest_id == orig_id:
                dest_id = self.rng.choice(fac_ids)

            leg_roll = self.rng.random()
            if leg_roll < 0.40:
                leg_nodes = [orig_id, dest_id]
            elif leg_roll < 0.85:
                intermediate = self.rng.choice(fac_ids)
                while intermediate in (orig_id, dest_id):
                    intermediate = self.rng.choice(fac_ids)
                leg_nodes = [orig_id, intermediate, dest_id]
            else:
                inter1 = self.rng.choice(fac_ids)
                inter2 = self.rng.choice(fac_ids)
                while inter1 in (orig_id, dest_id):
                    inter1 = self.rng.choice(fac_ids)
                while inter2 in (orig_id, dest_id, inter1):
                    inter2 = self.rng.choice(fac_ids)
                leg_nodes = [orig_id, inter1, inter2, dest_id]

            num_legs = len(leg_nodes) - 1
            service_level = self.rng.choice(self.service_levels)

            # Planned departure window
            dep_offset = self.rng.randint(0, sim_secs)
            planned_dep_dt = SIMULATION_START + timedelta(seconds=dep_offset)

            # Construct legs and calculate planned durations
            legs_meta = []
            curr_planned_time = planned_dep_dt

            for leg_seq in range(1, num_legs + 1):
                leg_orig = leg_nodes[leg_seq - 1]
                leg_dest = leg_nodes[leg_seq]
                route = self._find_or_create_route(leg_orig, leg_dest, route_counter)
                route_counter += 1

                carrier = self.carrier_map[route.primary_carrier_id]
                planned_transit = timedelta(hours=route.standard_transit_hours)
                planned_leg_start = curr_planned_time
                planned_leg_end = planned_leg_start + planned_transit

                # Add dwell between legs
                if leg_seq < num_legs:
                    intermediate_fac = self.facility_map[leg_dest]
                    curr_planned_time = planned_leg_end + timedelta(hours=intermediate_fac.nominal_dwell_hours)
                else:
                    curr_planned_time = planned_leg_end

                legs_meta.append({
                    "seq": leg_seq,
                    "orig": leg_orig,
                    "dest": leg_dest,
                    "route": route,
                    "carrier": carrier,
                    "planned_start": planned_leg_start,
                    "planned_end": planned_leg_end
                })

            planned_delivery_dt = curr_planned_time

            # ----------------------------------------------------
            # Physical Execution Simulation (Actuals & Delays)
            # ----------------------------------------------------
            actual_curr_time = planned_dep_dt + timedelta(minutes=self.rng.randint(-15, 45))
            actual_departure_dt = actual_curr_time

            shipment_legs_records: List[ShipmentLeg] = []
            tracking_events_records: List[TrackingEvent] = []
            dominant_cause_minutes = {"WEATHER": 0, "FACILITY_CONGESTION": 0, "CARRIER": 0}

            evt_counter = 1

            for leg_info in legs_meta:
                leg_id = f"LEG-{shp_id}-{leg_info['seq']:02d}"
                carrier = leg_info["carrier"]
                route = leg_info["route"]

                actual_leg_start = actual_curr_time

                # Baseline transit hours with carrier reliability variance
                carrier_variance = 1.0 + (1.0 - carrier.reliability_score) * self.rng.uniform(0.0, 1.2)
                carrier_delay_hrs = route.standard_transit_hours * max(0.0, carrier_variance - 1.0)
                dominant_cause_minutes["CARRIER"] += int(carrier_delay_hrs * 60)

                # Weather impact check
                weather_delay_hrs = 0.0
                dest_fac = self.facility_map[leg_info["dest"]]
                for w in self.weather_events[:50]:  # sample check
                    w_start = datetime.fromisoformat(w.start_ts.replace("Z", "+00:00"))
                    w_end = datetime.fromisoformat(w.end_ts.replace("Z", "+00:00"))
                    if w.region == dest_fac.region and (w_start <= actual_leg_start <= w_end):
                        weather_delay_hrs = route.standard_transit_hours * (w.delay_multiplier - 1.0)
                        dominant_cause_minutes["WEATHER"] += int(weather_delay_hrs * 60)
                        break

                # Facility queue dwell check
                facility_queue_delay_hrs = 0.0
                if leg_info["seq"] < num_legs:
                    transfer_fac = self.facility_map[leg_info["dest"]]
                    dwell_hrs = transfer_fac.nominal_dwell_hours
                    # Check if high congestion
                    if self.rng.random() < 0.20:
                        extra_dwell = self.rng.uniform(1.5, 5.0)
                        dwell_hrs += extra_dwell
                        facility_queue_delay_hrs += extra_dwell
                        dominant_cause_minutes["FACILITY_CONGESTION"] += int(extra_dwell * 60)
                else:
                    dwell_hrs = 0.0

                total_leg_duration_hrs = (
                    route.standard_transit_hours * carrier_variance +
                    weather_delay_hrs +
                    dwell_hrs
                )
                actual_leg_end = actual_leg_start + timedelta(hours=total_leg_duration_hrs)
                actual_curr_time = actual_leg_end

                s_leg = ShipmentLeg(
                    leg_id=leg_id,
                    shipment_id=shp_id,
                    leg_sequence=leg_info["seq"],
                    origin_facility_id=leg_info["orig"],
                    destination_facility_id=leg_info["dest"],
                    carrier_id=carrier.carrier_id,
                    route_id=route.route_id,
                    planned_leg_start_ts=leg_info["planned_start"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    planned_leg_end_ts=leg_info["planned_end"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    actual_leg_start_ts=actual_leg_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    actual_leg_end_ts=actual_leg_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    leg_distance_km=route.distance_km,
                    leg_status=LegStatus.COMPLETED.value
                )
                shipment_legs_records.append(s_leg)

                # ----------------------------------------------------
                # Generate Milestone Tracking Events for Leg
                # ----------------------------------------------------
                leg_events = []
                orig_fac = self.facility_map[leg_info["orig"]]

                if leg_info["seq"] == 1:
                    leg_events.append((EventType.SHIPMENT_CREATED.value, actual_leg_start - timedelta(minutes=45), orig_fac))
                    leg_events.append((EventType.CARRIER_ASSIGNED.value, actual_leg_start - timedelta(minutes=30), orig_fac))
                    leg_events.append((EventType.GATE_IN.value, actual_leg_start - timedelta(minutes=15), orig_fac))
                    leg_events.append((EventType.DEPARTURE.value, actual_leg_start, orig_fac))
                else:
                    leg_events.append((EventType.TRANSFER_ARRIVAL.value, actual_leg_start - timedelta(hours=dwell_hrs), orig_fac))
                    leg_events.append((EventType.TRANSFER_DEPARTURE.value, actual_leg_start, orig_fac))

                # In-transit checkpoints
                mid_time = actual_leg_start + (actual_leg_end - actual_leg_start) / 2
                mid_lat = (orig_fac.latitude + dest_fac.latitude) / 2.0
                mid_lon = (orig_fac.longitude + dest_fac.longitude) / 2.0
                leg_events.append((EventType.IN_TRANSIT_CHECKPOINT.value, mid_time, None, mid_lat, mid_lon))

                if leg_info["seq"] == num_legs:
                    leg_events.append((EventType.OUT_FOR_DELIVERY.value, actual_leg_end - timedelta(minutes=25), dest_fac))
                    leg_events.append((EventType.DELIVERED.value, actual_leg_end, dest_fac))

                for item in leg_events:
                    e_type = item[0]
                    e_time = item[1]
                    f_ref = item[2] if len(item) > 2 else None
                    e_lat = item[3] if len(item) > 3 else (f_ref.latitude if f_ref else None)
                    e_lon = item[4] if len(item) > 4 else (f_ref.longitude if f_ref else None)

                    # Realistic ingestion delay (90% fast 1-10 mins, 8% delayed 1-8 hrs)
                    ingestion_delay_secs = self.rng.randint(60, 600) if self.rng.random() < 0.90 else self.rng.randint(3600, 28800)
                    ingest_time = e_time + timedelta(seconds=ingestion_delay_secs)

                    eid = f"EVT-{shp_id}-{evt_counter:06d}"
                    evt_counter += 1

                    status_code = "LATE_SCAN" if ingestion_delay_secs > 3600 else "SCAN_OK"

                    te = TrackingEvent(
                        event_id=eid,
                        shipment_id=shp_id,
                        leg_id=leg_id,
                        event_sequence=evt_counter,
                        event_type=e_type,
                        event_timestamp=e_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        ingestion_timestamp=ingest_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        facility_id=f_ref.facility_id if f_ref else None,
                        latitude=e_lat,
                        longitude=e_lon,
                        status_code=status_code,
                        notes="Normal scan"
                    )
                    tracking_events_records.append(te)

            actual_delivery_dt = actual_curr_time
            final_delay_minutes = max(0, int((actual_delivery_dt - planned_delivery_dt).total_seconds() / 60))
            is_delayed = final_delay_minutes > service_level.max_delay_tolerance_mins

            # Primary delay reason attribution
            primary_reason_id = None
            if is_delayed:
                top_cause = max(dominant_cause_minutes, key=dominant_cause_minutes.get)
                if top_cause == "WEATHER" and dominant_cause_minutes["WEATHER"] > 0:
                    primary_reason_id = "DLY-WTH-01"
                elif top_cause == "FACILITY_CONGESTION" and dominant_cause_minutes["FACILITY_CONGESTION"] > 0:
                    primary_reason_id = "DLY-FAC-01"
                else:
                    primary_reason_id = "DLY-CRR-01"

            # ----------------------------------------------------
            # Anomaly Injections (Edge Cases / Negative Scenarios)
            # ----------------------------------------------------
            ground_truth_issue = AnomalyType.NORMAL.value
            is_anomaly = False
            expected_decision = "APPROVE_TRANSIT"
            anomaly_details = "Nominal shipment operation without detected defects."

            # Edge Case 1: Ingestion time confused with event time
            if assigned_anomaly == AnomalyType.INGESTION_TIME_CONFUSION and len(tracking_events_records) > 2:
                target_evt = tracking_events_records[1]
                # Invert: set ingestion timestamp before event timestamp (backward time skew)
                ev_dt = datetime.fromisoformat(target_evt.event_timestamp.replace("Z", "+00:00"))
                inverted_ingest = ev_dt - timedelta(hours=3, minutes=15)
                target_evt.ingestion_timestamp = inverted_ingest.strftime("%Y-%m-%dT%H:%M:%SZ")
                target_evt.status_code = "EXCEPTION"
                target_evt.notes = "INJECTED_DEFECT: Ingestion time earlier than physical event time"
                ground_truth_issue = AnomalyType.INGESTION_TIME_CONFUSION.value
                is_anomaly = True
                expected_decision = "FLAG_INGESTION_DRIFT"
                anomaly_details = f"Tracking event {target_evt.event_id} has ingestion timestamp 3h15m prior to physical event occurrence."

            # Edge Case 2: Impossible route order
            elif assigned_anomaly == AnomalyType.IMPOSSIBLE_ROUTE_ORDER and len(shipment_legs_records) >= 2:
                # Invert sequence dates: leg 2 start before leg 1 end
                l1 = shipment_legs_records[0]
                l2 = shipment_legs_records[1]
                l2.actual_leg_start_ts = l1.planned_leg_start_ts
                l2.actual_leg_end_ts = l1.planned_leg_start_ts
                ground_truth_issue = AnomalyType.IMPOSSIBLE_ROUTE_ORDER.value
                is_anomaly = True
                expected_decision = "REJECT_ROUTE_SEQUENCE"
                anomaly_details = f"Shipment leg {l2.leg_id} actual start timestamp precedes leg {l1.leg_id} completion."

            # Edge Case 4: Delivered shipment still marked in transit
            shipment_status = ShipmentStatus.DELIVERED.value
            if assigned_anomaly == AnomalyType.DELIVERED_STILL_IN_TRANSIT:
                shipment_status = ShipmentStatus.IN_TRANSIT.value  # stale status!
                ground_truth_issue = AnomalyType.DELIVERED_STILL_IN_TRANSIT.value
                is_anomaly = True
                expected_decision = "FORCE_DELIVERY_SYNC"
                anomaly_details = "DELIVERED milestone scan recorded but master shipment current_status remained IN_TRANSIT."

            # ----------------------------------------------------
            # ETA Snapshots generation (Point-in-time predictions)
            # ----------------------------------------------------
            # Produce snapshot at departure
            pred_time = actual_departure_dt
            rem_dist = sum(l.leg_distance_km for l in shipment_legs_records)
            predicted_dur_hrs = rem_dist / 70.0
            if is_delayed:
                predicted_dur_hrs += (final_delay_minutes / 60.0) * self.rng.uniform(0.7, 1.1)

            pred_deliv = pred_time + timedelta(hours=predicted_dur_hrs)
            conf_p10 = pred_deliv - timedelta(minutes=int(30 + predicted_dur_hrs * 3))
            conf_p90 = pred_deliv + timedelta(minutes=int(45 + predicted_dur_hrs * 8))
            pred_delay_mins = max(0, int((pred_deliv - planned_delivery_dt).total_seconds() / 60))

            risk_level = DelayRiskLevel.LOW.value
            if pred_delay_mins > service_level.max_delay_tolerance_mins:
                risk_level = DelayRiskLevel.CRITICAL.value if pred_delay_mins > 180 else DelayRiskLevel.HIGH.value
            elif pred_delay_mins > 15:
                risk_level = DelayRiskLevel.MEDIUM.value

            eta_snap_id = f"ETA-{shp_id}-{pred_time.strftime('%Y%m%dT%H%M%SZ')}"

            # Edge Case 3: ETA uses future event data (Data Leakage)
            if assigned_anomaly == AnomalyType.ETA_FUTURE_DATA_LEAKAGE:
                # Artificially set predicted_delivery_ts to exact future actual_delivery_ts down to the second
                pred_deliv = actual_delivery_dt
                pred_delay_mins = final_delay_minutes
                ground_truth_issue = AnomalyType.ETA_FUTURE_DATA_LEAKAGE.value
                is_anomaly = True
                expected_decision = "FLAG_DATA_LEAKAGE"
                anomaly_details = "ETA snapshot at departure perfectly encoded future delivery timestamp down to 0-second variance via unmasked telemetry leakage."

            features_meta = {
                "remaining_distance_km": rem_dist,
                "carrier_id": shipment_legs_records[0].carrier_id,
                "service_level": service_level.service_level_id,
                "initial_prediction": True
            }

            eta_obj = ETAEstimate(
                eta_id=eta_snap_id,
                shipment_id=shp_id,
                prediction_ts=pred_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                current_leg_sequence=1,
                elapsed_transit_hours=0.0,
                remaining_distance_km=rem_dist,
                predicted_delivery_ts=pred_deliv.strftime("%Y-%m-%dT%H:%M:%SZ"),
                confidence_p10_ts=conf_p10.strftime("%Y-%m-%dT%H:%M:%SZ"),
                confidence_p90_ts=conf_p90.strftime("%Y-%m-%dT%H:%M:%SZ"),
                predicted_delay_minutes=pred_delay_mins,
                delay_risk_level=risk_level,
                predicted_delay_reason_id=primary_reason_id,
                model_version="v1.2.0-hybrid",
                features_snapshot_json=json.dumps(features_meta)
            )
            self.eta_estimates.append(eta_obj)

            # Master Shipment Record
            shp = Shipment(
                shipment_id=shp_id,
                origin_facility_id=orig_id,
                destination_facility_id=dest_id,
                service_level_id=service_level.service_level_id,
                total_legs=num_legs,
                planned_departure_ts=planned_dep_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                planned_delivery_ts=planned_delivery_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                actual_departure_ts=actual_departure_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                actual_delivery_ts=actual_delivery_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                current_status=shipment_status,
                total_weight_kg=round(self.rng.uniform(500.0, 18000.0), 1),
                cargo_value_usd=round(self.rng.uniform(2000.0, 150000.0), 2),
                final_delay_minutes=final_delay_minutes,
                is_delayed=is_delayed,
                primary_delay_reason_id=primary_reason_id,
                created_at=planned_dep_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            self.shipments.append(shp)
            self.shipment_legs.extend(shipment_legs_records)
            self.tracking_events.extend(tracking_events_records)

            # Isolated Ground Truth Record
            gt = GroundTruth(
                entity_id=shp_id,
                entity_type="SHIPMENT",
                issue_type=ground_truth_issue,
                is_anomaly=is_anomaly,
                expected_decision=expected_decision,
                ground_truth_delivery_ts=actual_delivery_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ground_truth_delay_mins=final_delay_minutes,
                ground_truth_delay_category=primary_reason_id,
                anomaly_details=anomaly_details
            )
            self.ground_truth.append(gt)

    def summary(self) -> Dict[str, int]:
        return {
            "carriers": len(self.carriers),
            "facilities": len(self.facilities),
            "routes": len(self.routes),
            "service_levels": len(self.service_levels),
            "delay_reasons": len(self.delay_reasons),
            "weather_events": len(self.weather_events),
            "facility_queues": len(self.facility_queues),
            "shipments": len(self.shipments),
            "shipment_legs": len(self.shipment_legs),
            "tracking_events": len(self.tracking_events),
            "eta_estimates": len(self.eta_estimates),
            "ground_truth": len(self.ground_truth)
        }
