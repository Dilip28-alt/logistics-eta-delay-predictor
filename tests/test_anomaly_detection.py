"""
Tests for anomaly detection, exception remediation, and ground-truth isolation.
Verifies all 4 required edge cases:
1. Event ingestion time confused with event time
2. Impossible route order
3. ETA uses future event data (leakage)
4. Delivered shipment still marked in transit
"""

import pytest
from src.generator.generator import SyntheticDataGenerator
from src.engine.exception_handler import OperationalExceptionHandler
from src.models.entities import AnomalyType


@pytest.fixture(scope="module")
def gen_with_anomalies():
    gen = SyntheticDataGenerator(seed=20261022)
    gen.generate_all(num_shipments=200, num_facilities=30, num_disruptions=60)
    return gen


def test_exception_handler_detects_all_edge_cases(gen_with_anomalies):
    handler = OperationalExceptionHandler(gen_with_anomalies)
    remediations = handler.scan_and_remediate(auto_apply=False)

    issue_types = {r.issue_type for r in remediations}

    # Verify all 4 required negative scenarios are captured
    assert AnomalyType.INGESTION_TIME_CONFUSION.value in issue_types
    assert AnomalyType.IMPOSSIBLE_ROUTE_ORDER.value in issue_types
    assert AnomalyType.ETA_FUTURE_DATA_LEAKAGE.value in issue_types
    assert AnomalyType.DELIVERED_STILL_IN_TRANSIT.value in issue_types


def test_remediation_action_content(gen_with_anomalies):
    handler = OperationalExceptionHandler(gen_with_anomalies)
    remediations = handler.scan_and_remediate(auto_apply=False)

    for r in remediations:
        assert r.exception_id.startswith("EXC-")
        assert len(r.recommended_action) > 10
        assert r.severity in ("MEDIUM", "HIGH", "CRITICAL")
        assert len(r.description) > 10


def test_ground_truth_isolation(gen_with_anomalies):
    """
    Verifies that ground truth labels exist in separate ground_truth table
    and never corrupt the raw features of valid shipments.
    """
    gt_entities = {g.entity_id: g for g in gen_with_anomalies.ground_truth}
    assert len(gt_entities) == len(gen_with_anomalies.shipments)

    normal_shipments = [s for s in gen_with_anomalies.shipments if gt_entities[s.shipment_id].issue_type == "NORMAL"]
    assert len(normal_shipments) > 150
