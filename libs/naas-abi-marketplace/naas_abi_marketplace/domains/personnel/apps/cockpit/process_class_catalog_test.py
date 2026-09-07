"""Tests for ontology-derived process class catalogs."""

from naas_abi_marketplace.domains.personnel.apps.cockpit.process_class_catalog import (
    build_process_class_catalog,
)


def test_working_catalog_includes_seven_bucket_classes() -> None:
    catalog = build_process_class_catalog()
    labels = set(catalog["Act of Working"]["classLabels"])

    assert "Organization" in labels
    assert "Site" in labels
    assert "Temporal Region" in labels
    assert "Temporal Instant" in labels
    assert "Employee Role" in labels
    assert "Skill" in labels
    assert "Employment Contract" in labels
    assert "Mission" in labels
    assert "Profile Document" in labels
    assert "Remuneration" in labels
    assert "Person" not in labels
    assert "Act of Working" not in labels


def test_studying_catalog_includes_study_specific_classes() -> None:
    catalog = build_process_class_catalog()
    labels = set(catalog["Act of Studying"]["classLabels"])

    assert "Enrollment Record" in labels
    assert "Student Role" in labels
    assert "Academic Degree" in labels
    assert "Profile Document" in labels
    assert "Skill" in labels
    assert "Act of Studying" not in labels
