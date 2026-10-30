"""
Automated reproducibility test comparing two independent generation runs.
"""

from src.generator.generator import SyntheticDataGenerator


def test_dual_generation_exact_reproducibility():
    seed = 20261022
    gen1 = SyntheticDataGenerator(seed=seed)
    gen1.generate_all(num_shipments=50, num_facilities=15, num_disruptions=20)

    gen2 = SyntheticDataGenerator(seed=seed)
    gen2.generate_all(num_shipments=50, num_facilities=15, num_disruptions=20)

    assert gen1.summary() == gen2.summary()

    for s1, s2 in zip(gen1.shipments, gen2.shipments):
        assert s1.to_dict() == s2.to_dict()

    for t1, t2 in zip(gen1.tracking_events, gen2.tracking_events):
        assert t1.to_dict() == t2.to_dict()

    for e1, e2 in zip(gen1.eta_estimates, gen2.eta_estimates):
        assert e1.to_dict() == e2.to_dict()
