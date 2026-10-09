"""Catalog disclosure: fields, budgets, and real package files."""

from naas_abi.skills.catalog import (
    DEFAULT_CATALOG_BUDGET,
    DEFAULT_DESCRIPTION_CAP,
    CatalogEntry,
    list_package_files,
    read_package_file,
    render_catalog,
)


def test_catalog_lists_only_disclosure_fields_and_caps_descriptions() -> None:
    long_description = "D" * (DEFAULT_DESCRIPTION_CAP + 40)
    body = "BODY_THAT_MUST_STAY_OUT_OF_THE_CATALOG"
    rendered = render_catalog(
        [
            CatalogEntry(
                slug="weekly",
                name="Weekly",
                description=long_description,
                when_to_use="When the user asks for the week.",
            )
        ],
        budget=DEFAULT_CATALOG_BUDGET,
        description_cap=DEFAULT_DESCRIPTION_CAP,
    )

    assert "slug: weekly" in rendered
    assert "name: Weekly" in rendered
    assert "when_to_use: When the user asks for the week." in rendered
    assert "D" * DEFAULT_DESCRIPTION_CAP in rendered
    assert "D" * (DEFAULT_DESCRIPTION_CAP + 1) not in rendered
    assert body not in rendered
    assert len(rendered) <= DEFAULT_CATALOG_BUDGET


def test_catalog_drops_skills_that_do_not_fit_and_never_inserts_a_body() -> None:
    first = CatalogEntry(slug="one", name="One", description="short", when_to_use="now")
    second = CatalogEntry(
        slug="two",
        name="Two",
        description="y" * 400,
        when_to_use="later",
    )
    third = CatalogEntry(slug="three", name="Three", description="tiny", when_to_use="always")
    alone = render_catalog([first], budget=DEFAULT_CATALOG_BUDGET)
    rendered = render_catalog(
        [first, second, third],
        budget=len(alone),
        description_cap=DEFAULT_DESCRIPTION_CAP,
    )

    assert rendered == alone
    assert "slug: two" not in rendered
    assert "slug: three" not in rendered
    assert "y" * 251 not in rendered


def test_sheets_package_lists_real_files_and_postgres_slugs_do_not() -> None:
    files = list_package_files("sheets")
    assert files == (
        "SKILL.md",
        "references/research.md",
        "scripts/validate_workbook.py",
    )
    skill = read_package_file("sheets", "SKILL.md")
    assert skill is not None
    assert "workbook.html" in skill
    research = read_package_file("sheets", "references/research.md")
    assert research is not None
    assert "Nexus" in research
    assert read_package_file("sheets", "../SKILL.md") is None
    assert read_package_file("sheets", "nope.md") is None
    assert list_package_files("not-a-saved-prompt") == ()
    assert read_package_file("not-a-saved-prompt", "SKILL.md") is None
