"""
Unit and integration tests for synthetic logistics data generator.
"""

import pytest
from src.generator.generator import SyntheticDataGenerator


def test_generator_initialization_and_master_data():
    gen = SyntheticDataGenerator(seed=20261022)
    gen.generate_all(num_shipments=50, num_facilities=20, num_disruptions=40)

    assert len(gen.carriers) == 20
    assert len(gen.facilities) == 20
    assert len(gen.service_levels) == 4
    assert len(gen.delay_reasons) == 10
    assert len(gen.weather_events) == 20
    assert len(gen.facility_queues) == 20
    assert len(gen.shipments) == 50
    assert len(gen.shipment_legs) >= 50
    assert len(gen.tracking_events) >= 200
    assert len(gen.eta_estimates) == 50
    assert len(gen.ground_truth) == 50


def test_deterministic_seed_consistency():
    gen1 = SyntheticDataGenerator(seed=12345)
    gen1.generate_all(num_shipments=20, num_facilities=10, num_disruptions=10)

    gen2 = SyntheticDataGenerator(seed=12345)
    gen2.generate_all(num_shipments=20, num_facilities=10, num_disruptions=10)

    assert gen1.shipments[0].shipment_id == gen2.shipments[0].shipment_id
    assert gen1.shipments[0].planned_delivery_ts == gen2.shipments[0].planned_delivery_ts
    assert gen1.shipments[0].final_delay_minutes == gen2.shipments[0].final_delay_minutes
    assert gen1.tracking_events[5].event_timestamp == gen2.tracking_events[5].event_timestamp
