"""
Relational integrity, foreign key verification, and arithmetic reconciliation tests.
"""

import pytest
from src.generator.generator import SyntheticDataGenerator
from src.validator.validator import DataValidator


@pytest.fixture(scope="module")
def sample_generator():
    gen = SyntheticDataGenerator(seed=20261022)
    gen.generate_all(num_shipments=100, num_facilities=25, num_disruptions=50)
    return gen


def test_validator_passes_all_checks(sample_generator):
    validator = DataValidator(sample_generator)
    report = validator.validate_all()
    assert report.passed is True
    assert report.checks_failed == 0
    assert report.checks_passed > 15


def test_primary_key_uniqueness(sample_generator):
    validator = DataValidator(sample_generator)
    report = validator.validate_all()
    pk_errors = [e for e in report.errors if e["check"] == "PK_UNIQUENESS"]
    assert len(pk_errors) == 0


def test_foreign_key_referential_integrity(sample_generator):
    validator = DataValidator(sample_generator)
    report = validator.validate_all()
    fk_errors = [e for e in report.errors if e["check"] == "FK_INTEGRITY"]
    assert len(fk_errors) == 0


def test_arithmetic_reconciliation(sample_generator):
    validator = DataValidator(sample_generator)
    report = validator.validate_all()
    arith_errors = [e for e in report.errors if e["check"] == "ARITHMETIC_RECONCILIATION"]
    assert len(arith_errors) == 0
