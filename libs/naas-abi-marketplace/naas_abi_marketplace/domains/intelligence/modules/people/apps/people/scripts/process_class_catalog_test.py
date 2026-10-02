"""Tests for ontology-derived process class catalogs."""

from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.process_class_catalog import (
    build_process_class_catalog,
)


def test_working_catalog_includes_seven_bucket_classes() -> None:
    catalog = build_process_class_catalog()
    labels = set(catalog["Act of Working"]["classLabels"])

    assert "Organization" in labels
    assert "Office Building" in labels  # WHERE: the facility, not a bare Site
    assert "Site" not in labels
    assert "Temporal Region" in labels
    assert "Temporal Instant" in labels
    assert "Occupation Role" in labels
    assert "Skill" in labels
    assert "Mission" in labels
    assert "Profile Document" in labels
    # Internal HR records are not part of the generic act of working.
    assert "Employee Role" not in labels
    assert "Employment Contract" not in labels
    assert "Remuneration" not in labels
    assert "Person" not in labels
    assert "Act of Working" not in labels


def test_studying_catalog_includes_study_specific_classes() -> None:
    catalog = build_process_class_catalog()
    labels = set(catalog["Act of Studying"]["classLabels"])

    assert "Educational Facility" in labels
    assert "Enrollment Record" in labels
    assert "Student Role" in labels
    assert "Academic Degree" in labels
    assert "Profile Document" in labels
    assert "Skill" in labels
    assert "Act of Studying" not in labels


def test_certification_catalog_covers_every_bucket() -> None:
    catalog = build_process_class_catalog()
    labels = set(catalog["Act of Certification"]["classLabels"])

    assert "Organization" in labels  # WHO: the certifying body
    assert "Temporal Region" in labels  # WHEN
    assert "Facility" in labels  # WHERE
    assert "Certification Candidate Role" in labels  # WHY
    assert "Skill" in labels  # HOW IT IS
    assert "Certification" in labels  # HOW WE KNOW
    assert "Profile Document" in labels  # HOW WE KNOW
    assert "Person" not in labels
    assert "Act of Certification" not in labels
