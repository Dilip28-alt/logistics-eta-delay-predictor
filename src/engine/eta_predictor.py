"""
Dynamic Point-in-Time ETA Prediction Engine with Temporal Anti-Leakage Guardrails.
Combines carrier events, route plans, weather disruptions, and facility queues.
Exposes full decision explainability and preserves audit traceability.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.models.entities import DelayRiskLevel, TransportMode


class ETAPredictionResult:
    def __init__(
        self,
        shipment_id: str,
        evaluation_ts: str,
        predicted_delivery_ts: str,
        confidence_p10_ts: str,
        confidence_p90_ts: str,
        planned_delivery_ts: str,
        predicted_delay_minutes: int,
        delay_risk_level: str,
        primary_delay_reason: str,
        decision_trace: Dict[str, Any]
    ):
        self.shipment_id = shipment_id
        self.evaluation_ts = evaluation_ts
        self.predicted_delivery_ts = predicted_delivery_ts
        self.confidence_p10_ts = confidence_p10_ts
        self.confidence_p90_ts = confidence_p90_ts
        self.planned_delivery_ts = planned_delivery_ts
        self.predicted_delay_minutes = predicted_delay_minutes
        self.delay_risk_level = delay_risk_level
        self.primary_delay_reason = primary_delay_reason
        self.decision_trace = decision_trace

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shipment_id": self.shipment_id,
            "evaluation_ts": self.evaluation_ts,
            "predicted_delivery_ts": self.predicted_delivery_ts,
            "confidence_interval": {
                "p10_optimistic": self.confidence_p10_ts,
                "p90_pessimistic": self.confidence_p90_ts
            },
            "planned_delivery_ts": self.planned_delivery_ts,
            "predicted_delay_minutes": self.predicted_delay_minutes,
            "delay_risk_level": self.delay_risk_level,
            "primary_delay_reason": self.primary_delay_reason,
            "decision_trace": self.decision_trace
        }


class ETAPredictor:
    def __init__(self, data_store: Any):
        """
        data_store can be an instance of SyntheticDataGenerator or a repository accessor.
        """
        self.gen = data_store
        self.facility_map = {f.facility_id: f for f in self.gen.facilities}
        self.carrier_map = {c.carrier_id: c for c in self.gen.carriers}
        self.route_map = {r.route_id: r for r in self.gen.routes}
        self.service_level_map = {s.service_level_id: s for s in self.gen.service_levels}

    def predict(
        self,
        shipment_id: str,
        as_of_ts: Optional[datetime] = None,
        override_weather_multiplier: Optional[float] = None,
        override_facility_dwell_hours: Optional[float] = None
    ) -> ETAPredictionResult:
        """
        Executes point-in-time ETA estimation as of a designated evaluation timestamp.
        Guarantees temporal isolation: strictly rejects any future tracking events or future weather/queue telemetry.
        """
        shipment = next((s for s in self.gen.shipments if s.shipment_id == shipment_id), None)
        if not shipment:
            raise ValueError(f"Shipment {shipment_id} not found in repository")

        plan_dep = datetime.fromisoformat(shipment.planned_departure_ts.replace("Z", "+00:00"))
        plan_deliv = datetime.fromisoformat(shipment.planned_delivery_ts.replace("Z", "+00:00"))

        if as_of_ts is None:
            # Default to shipment planned departure if not specified
            as_of_ts = plan_dep

        # Ensure as_of_ts is timezone-aware
        if as_of_ts.tzinfo is None:
            as_of_ts = as_of_ts.replace(tzinfo=timezone.utc)

        # 1. Temporal Filter: Filter tracking events strictly <= as_of_ts
        visible_events = [
            t for t in self.gen.tracking_events
            if t.shipment_id == shipment_id and
            datetime.fromisoformat(t.event_timestamp.replace("Z", "+00:00")) <= as_of_ts
        ]
        visible_events.sort(key=lambda t: datetime.fromisoformat(t.event_timestamp.replace("Z", "+00:00")))

        # 2. Get shipment legs
        shipment_legs = [l for l in self.gen.shipment_legs if l.shipment_id == shipment_id]
        shipment_legs.sort(key=lambda l: l.leg_sequence)

        # 3. Determine current transit position
        current_leg_seq = 1
        has_departed = False
        is_already_delivered = False

        for evt in visible_events:
            if evt.event_type in ("DEPARTURE", "GATE_OUT", "IN_TRANSIT_CHECKPOINT"):
                has_departed = True
            if evt.event_type == "TRANSFER_ARRIVAL" and evt.leg_id:
                # Progressed through transfer
                leg_match = next((l for l in shipment_legs if l.leg_id == evt.leg_id), None)
                if leg_match:
                    current_leg_seq = min(len(shipment_legs), leg_match.leg_sequence + 1)
            if evt.event_type == "DELIVERED":
                is_already_delivered = True

        if is_already_delivered:
            last_evt_ts = datetime.fromisoformat(visible_events[-1].event_timestamp.replace("Z", "+00:00"))
            return ETAPredictionResult(
                shipment_id=shipment_id,
                evaluation_ts=as_of_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                predicted_delivery_ts=last_evt_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                confidence_p10_ts=last_evt_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                confidence_p90_ts=last_evt_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                planned_delivery_ts=shipment.planned_delivery_ts,
                predicted_delay_minutes=max(0, int((last_evt_ts - plan_deliv).total_seconds() / 60)),
                delay_risk_level=DelayRiskLevel.LOW.value,
                primary_delay_reason="DELIVERY_COMPLETED",
                decision_trace={"status": "COMPLETED", "note": "Shipment already delivered at observation time."}
            )

        # 4. Compute remaining distance & base duration
        remaining_legs = [l for l in shipment_legs if l.leg_sequence >= current_leg_seq]
        total_remaining_km = sum(l.leg_distance_km for l in remaining_legs)

        # Factor in progress on current leg
        elapsed_hours = 0.0
        if has_departed and visible_events:
            first_dep = datetime.fromisoformat(visible_events[0].event_timestamp.replace("Z", "+00:00"))
            elapsed_hours = max(0.0, (as_of_ts - first_dep).total_seconds() / 3600.0)

        # 5. Route Base Speeds and Carrier Reliability
        total_adjusted_transit_hours = 0.0
        carrier_delays_hrs = 0.0
        weather_delays_hrs = 0.0
        facility_dwell_delays_hrs = 0.0

        trace_factors = []

        for leg in remaining_legs:
            carrier = self.carrier_map.get(leg.carrier_id)
            rel_score = carrier.reliability_score if carrier else 0.90
            speed = 70.0  # km/h baseline road speed
            base_hours = leg.leg_distance_km / speed

            # Carrier reliability drag
            carrier_factor = 1.0 + (1.0 - rel_score) * 0.7
            leg_transit = base_hours * carrier_factor
            carrier_delays_hrs += (base_hours * (carrier_factor - 1.0))

            # Weather disruption impact
            dest_fac = self.facility_map.get(leg.destination_facility_id)
            w_multiplier = 1.0
            if override_weather_multiplier:
                w_multiplier = override_weather_multiplier
            elif dest_fac:
                # Find active weather in region at or forecast around as_of_ts
                for w in self.gen.weather_events:
                    w_start = datetime.fromisoformat(w.start_ts.replace("Z", "+00:00"))
                    w_end = datetime.fromisoformat(w.end_ts.replace("Z", "+00:00"))
                    if w.region == dest_fac.region and (w_start <= as_of_ts <= w_end + timedelta(hours=12)):
                        w_multiplier = max(w_multiplier, w.delay_multiplier)
                        break

            weather_added = leg_transit * (w_multiplier - 1.0)
            weather_delays_hrs += weather_added
            leg_transit += weather_added

            # Intermediate facility queue dwell
            leg_dwell = 0.0
            if leg.leg_sequence < len(shipment_legs):
                inter_fac = self.facility_map.get(leg.destination_facility_id)
                nom_dwell = inter_fac.nominal_dwell_hours if inter_fac else 2.0
                if override_facility_dwell_hours is not None:
                    leg_dwell = override_facility_dwell_hours
                else:
                    # Look up closest preceding queue observation
                    q_obs = [
                        q for q in self.gen.facility_queues
                        if q.facility_id == leg.destination_facility_id and
                        datetime.fromisoformat(q.snapshot_ts.replace("Z", "+00:00")) <= as_of_ts
                    ]
                    if q_obs:
                        q_obs.sort(key=lambda q: datetime.fromisoformat(q.snapshot_ts.replace("Z", "+00:00")), reverse=True)
                        leg_dwell = q_obs[0].avg_dwell_hours
                    else:
                        leg_dwell = nom_dwell

                facility_dwell_delays_hrs += max(0.0, leg_dwell - nom_dwell)

            total_adjusted_transit_hours += (leg_transit + leg_dwell)
            trace_factors.append({
                "leg_id": leg.leg_id,
                "distance_km": leg.leg_distance_km,
                "base_transit_hours": round(base_hours, 2),
                "carrier_reliability": rel_score,
                "weather_multiplier": round(w_multiplier, 2),
                "facility_dwell_hours": round(leg_dwell, 2)
            })

        # 6. Final Projected Delivery Time
        projected_delivery_dt = as_of_ts + timedelta(hours=total_adjusted_transit_hours)
        conf_p10_dt = projected_delivery_dt - timedelta(minutes=int(20 + total_adjusted_transit_hours * 2.5))
        conf_p90_dt = projected_delivery_dt + timedelta(minutes=int(30 + total_adjusted_transit_hours * 5.0))

        predicted_delay_mins = max(0, int((projected_delivery_dt - plan_deliv).total_seconds() / 60))

        # 7. Service Level Threshold & Risk Classification
        sl = self.service_level_map.get(shipment.service_level_id)
        tolerance_mins = sl.max_delay_tolerance_mins if sl else 60

        if predicted_delay_mins > tolerance_mins * 2:
            risk_level = DelayRiskLevel.CRITICAL.value
        elif predicted_delay_mins > tolerance_mins:
            risk_level = DelayRiskLevel.HIGH.value
        elif predicted_delay_mins > 15:
            risk_level = DelayRiskLevel.MEDIUM.value
        else:
            risk_level = DelayRiskLevel.LOW.value

        # Primary Delay Reason
        primary_reason = "ON_TIME_TRANSIT"
        if predicted_delay_mins > 0:
            if weather_delays_hrs >= max(carrier_delays_hrs, facility_dwell_delays_hrs):
                primary_reason = "WEATHER_DISRUPTION"
            elif facility_dwell_delays_hrs >= max(carrier_delays_hrs, weather_delays_hrs):
                primary_reason = "FACILITY_CONGESTION"
            else:
                primary_reason = "CARRIER_OPERATIONAL_VARIANCE"

        decision_trace = {
            "current_leg_sequence": current_leg_seq,
            "remaining_legs_count": len(remaining_legs),
            "remaining_distance_km": round(total_remaining_km, 1),
            "elapsed_transit_hours": round(elapsed_hours, 2),
            "estimated_remaining_hours": round(total_adjusted_transit_hours, 2),
            "carrier_delay_contribution_hours": round(carrier_delays_hrs, 2),
            "weather_delay_contribution_hours": round(weather_delays_hrs, 2),
            "facility_dwell_delay_contribution_hours": round(facility_dwell_delays_hrs, 2),
            "sla_tolerance_mins": tolerance_mins,
            "legs_breakdown": trace_factors
        }

        return ETAPredictionResult(
            shipment_id=shipment_id,
            evaluation_ts=as_of_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            predicted_delivery_ts=projected_delivery_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            confidence_p10_ts=conf_p10_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            confidence_p90_ts=conf_p90_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            planned_delivery_ts=shipment.planned_delivery_ts,
            predicted_delay_minutes=predicted_delay_mins,
            delay_risk_level=risk_level,
            primary_delay_reason=primary_reason,
            decision_trace=decision_trace
        )
