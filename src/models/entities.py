"""
Domain entities and data structures for Logistics ETA Estimation & Delay Risk Platform.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class TransportMode(str, Enum):
    ROAD = "ROAD"
    RAIL = "RAIL"
    AIR = "AIR"
    OCEAN = "OCEAN"


class FacilityType(str, Enum):
    PORT = "PORT"
    CROSS_DOCK = "CROSS_DOCK"
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    FULFILLMENT_CENTER = "FULFILLMENT_CENTER"


class Region(str, Enum):
    MIDWEST = "MIDWEST"
    NORTHEAST = "NORTHEAST"
    SOUTHEAST = "SOUTHEAST"
    SOUTHWEST = "SOUTHWEST"
    WEST_COAST = "WEST_COAST"


class ShipmentStatus(str, Enum):
    BOOKED = "BOOKED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class LegStatus(str, Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class EventType(str, Enum):
    SHIPMENT_CREATED = "SHIPMENT_CREATED"
    CARRIER_ASSIGNED = "CARRIER_ASSIGNED"
    GATE_IN = "GATE_IN"
    LOADING_STARTED = "LOADING_STARTED"
    DEPARTURE = "DEPARTURE"
    IN_TRANSIT_CHECKPOINT = "IN_TRANSIT_CHECKPOINT"
    GATE_OUT = "GATE_OUT"
    TRANSFER_ARRIVAL = "TRANSFER_ARRIVAL"
    TRANSFER_DEPARTURE = "TRANSFER_DEPARTURE"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERY_ATTEMPTED = "DELIVERY_ATTEMPTED"
    DELIVERED = "DELIVERED"
    EXCEPTION_HOLD = "EXCEPTION_HOLD"


class CongestionLevel(str, Enum):
    NORMAL = "NORMAL"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    GRIDLOCK = "GRIDLOCK"


class WeatherSeverity(str, Enum):
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


class WeatherType(str, Enum):
    BLIZZARD = "BLIZZARD"
    HEAVY_SNOW = "HEAVY_SNOW"
    SEVERE_THUNDERSTORM = "SEVERE_THUNDERSTORM"
    FLOODING = "FLOODING"
    HIGH_WINDS = "HIGH_WINDS"
    DENSE_FOG = "DENSE_FOG"


class DelayRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    NORMAL = "NORMAL"
    INGESTION_TIME_CONFUSION = "INGESTION_TIME_CONFUSION"
    IMPOSSIBLE_ROUTE_ORDER = "IMPOSSIBLE_ROUTE_ORDER"
    ETA_FUTURE_DATA_LEAKAGE = "ETA_FUTURE_DATA_LEAKAGE"
    DELIVERED_STILL_IN_TRANSIT = "DELIVERED_STILL_IN_TRANSIT"


@dataclass
class Carrier:
    carrier_id: str
    carrier_name: str
    transport_mode: str
    reliability_score: float
    operating_calendar: str
    contact_email: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Facility:
    facility_id: str
    facility_name: str
    facility_type: str
    region: str
    latitude: float
    longitude: float
    capacity_trucks_per_hr: int
    nominal_dwell_hours: float
    operating_calendar: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Route:
    route_id: str
    origin_facility_id: str
    destination_facility_id: str
    primary_carrier_id: str
    transport_mode: str
    distance_km: float
    standard_transit_hours: float
    is_toll_road: bool
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServiceLevel:
    service_level_id: str
    service_level_name: str
    max_delay_tolerance_mins: int
    target_on_time_pct: float
    penalty_per_hour_delayed: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DelayReason:
    delay_reason_id: str
    category: str
    sub_reason: str
    severity_tier: str
    is_carrier_fault: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Shipment:
    shipment_id: str
    origin_facility_id: str
    destination_facility_id: str
    service_level_id: str
    total_legs: int
    planned_departure_ts: str
    planned_delivery_ts: str
    actual_departure_ts: Optional[str]
    actual_delivery_ts: Optional[str]
    current_status: str
    total_weight_kg: float
    cargo_value_usd: float
    final_delay_minutes: int
    is_delayed: bool
    primary_delay_reason_id: Optional[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ShipmentLeg:
    leg_id: str
    shipment_id: str
    leg_sequence: int
    origin_facility_id: str
    destination_facility_id: str
    carrier_id: str
    route_id: str
    planned_leg_start_ts: str
    planned_leg_end_ts: str
    actual_leg_start_ts: Optional[str]
    actual_leg_end_ts: Optional[str]
    leg_distance_km: float
    leg_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrackingEvent:
    event_id: str
    shipment_id: str
    leg_id: Optional[str]
    event_sequence: int
    event_type: str
    event_timestamp: str
    ingestion_timestamp: str
    facility_id: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status_code: str
    notes: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FacilityQueue:
    queue_id: str
    facility_id: str
    snapshot_ts: str
    queue_depth_trucks: int
    avg_dwell_hours: float
    active_berths: int
    inflow_rate_per_hr: float
    outflow_rate_per_hr: float
    congestion_level: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeatherEvent:
    weather_id: str
    region: str
    event_type: str
    severity: str
    start_ts: str
    end_ts: str
    delay_multiplier: float
    radius_km: float
    center_lat: float
    center_lon: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ETAEstimate:
    eta_id: str
    shipment_id: str
    prediction_ts: str
    current_leg_sequence: int
    elapsed_transit_hours: float
    remaining_distance_km: float
    predicted_delivery_ts: str
    confidence_p10_ts: str
    confidence_p90_ts: str
    predicted_delay_minutes: int
    delay_risk_level: str
    predicted_delay_reason_id: Optional[str]
    model_version: str
    features_snapshot_json: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundTruth:
    entity_id: str
    entity_type: str
    issue_type: str
    is_anomaly: bool
    expected_decision: str
    ground_truth_delivery_ts: Optional[str]
    ground_truth_delay_mins: Optional[int]
    ground_truth_delay_category: Optional[str]
    anomaly_details: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
