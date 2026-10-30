"""
Unit and integration tests for dynamic ETA prediction engine and temporal isolation.
"""

from datetime import datetime, timedelta, timezone
import pytest

from src.generator.generator import SyntheticDataGenerator
from src.engine.eta_predictor import ETAPredictor


@pytest.fixture(scope="module")
def engine():
    gen = SyntheticDataGenerator(seed=20261022)
    gen.generate_all(num_shipments=100, num_facilities=25, num_disruptions=50)
    return ETAPredictor(gen)


def test_eta_prediction_temporal_isolation(engine):
    shp = engine.gen.shipments[0]
    plan_dep = datetime.fromisoformat(shp.planned_departure_ts.replace("Z", "+00:00"))

    # Predict at departure time
    result = engine.predict(shipment_id=shp.shipment_id, as_of_ts=plan_dep)
    assert result.shipment_id == shp.shipment_id
    assert result.predicted_delivery_ts is not None
    assert result.predicted_delay_minutes >= 0
    assert result.delay_risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "remaining_distance_km" in result.decision_trace


def test_what_if_scenario_weather_escalation(engine):
    shp = engine.gen.shipments[0]
    plan_dep = datetime.fromisoformat(shp.planned_departure_ts.replace("Z", "+00:00"))

    # Baseline prediction
    baseline = engine.predict(shipment_id=shp.shipment_id, as_of_ts=plan_dep)

    # Severe weather override (2.5x multiplier)
    escalated = engine.predict(
        shipment_id=shp.shipment_id,
        as_of_ts=plan_dep,
        override_weather_multiplier=2.5
    )

    t_base = datetime.fromisoformat(baseline.predicted_delivery_ts.replace("Z", "+00:00"))
    t_esc = datetime.fromisoformat(escalated.predicted_delivery_ts.replace("Z", "+00:00"))

    # Escalated weather should result in a later predicted delivery
    assert t_esc >= t_base
    assert escalated.decision_trace["weather_delay_contribution_hours"] >= baseline.decision_trace["weather_delay_contribution_hours"]


def test_confidence_interval_monotonicity(engine):
    shp = engine.gen.shipments[0]
    plan_dep = datetime.fromisoformat(shp.planned_departure_ts.replace("Z", "+00:00"))
    res = engine.predict(shipment_id=shp.shipment_id, as_of_ts=plan_dep)

    p10 = datetime.fromisoformat(res.confidence_p10_ts.replace("Z", "+00:00"))
    pred = datetime.fromisoformat(res.predicted_delivery_ts.replace("Z", "+00:00"))
    p90 = datetime.fromisoformat(res.confidence_p90_ts.replace("Z", "+00:00"))

    assert p10 <= pred
    assert pred <= p90
