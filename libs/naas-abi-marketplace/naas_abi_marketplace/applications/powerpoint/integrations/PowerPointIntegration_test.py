import pytest
from naas_abi_core import logger
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)


@pytest.fixture(
    params=["src/marketplace/applications/powerpoint/templates/TemplateSlides.pptx"]
)
def powerpoint_integration(request) -> PowerPointIntegration:
    template_path = request.param
    configuration = PowerPointIntegrationConfiguration(template_path=template_path)
    integration = PowerPointIntegration(configuration)
    return integration


def test_add_slide(powerpoint_integration: PowerPointIntegration):
    output_path = "src/marketplace/applications/powerpoint/sandbox/test_add_slide.pptx"
    # Count number of slides before adding a new one
    presentation = powerpoint_integration.create_presentation()
    slides_count = len(presentation.slides)
    logger.debug(f"Slides count before adding a new one: {slides_count}")

    presentation, slide_index = powerpoint_integration.add_slide(presentation)

    assert len(presentation.slides) == slides_count + 1, "New slide not added"
    assert len(presentation.slides) == slide_index + 1, (
        f"Slide index is not correct. Expected {slides_count}, got {slide_index}"
    )
    logger.debug(f"Slides count after adding a new one: {len(presentation.slides)}")

    powerpoint_integration.save_presentation(presentation, output_path)


def test_remove_all_slides(powerpoint_integration: PowerPointIntegration):
    """Test removing all slides from presentation."""
    output_path = (
        "src/marketplace/applications/powerpoint/sandbox/test_remove_all_slides.pptx"
    )
    # Create presentation
    presentation = powerpoint_integration.create_presentation()
    initial_slides_count = len(presentation.slides)
    logger.debug(f"Initial slides count: {initial_slides_count}")

    # Remove all slides
    presentation = powerpoint_integration.remove_all_slides(presentation)

    # Verify all slides were removed
    assert len(presentation.slides) == 0, "All slides should be removed"
    logger.debug(f"Slides count after removing all: {len(presentation.slides)}")

    powerpoint_integration.save_presentation(presentation, output_path)


def test_duplicate_slide(powerpoint_integration: PowerPointIntegration):
    """Test duplicating slides between presentations."""
    output_path = (
        "src/marketplace/applications/powerpoint/sandbox/test_duplicate_slide.pptx"
    )

    # Create source and destination presentations
    src = powerpoint_integration.create_presentation()
    dst = powerpoint_integration.create_presentation()
    dst = powerpoint_integration.remove_all_slides(dst)

    # Verify initial state
    initial_dst_count = len(dst.slides)
    assert initial_dst_count == 0, "Destination should start empty"

    # Duplicate slides in same pattern as sandbox example
    dst, idx = powerpoint_integration.duplicate_slide(src, 0, dst)
    assert len(dst.slides) == 1, "First slide not duplicated"

    dst, idx = powerpoint_integration.duplicate_slide(src, 1, dst)
    assert len(dst.slides) == 2, "Second slide not duplicated"

    dst, idx = powerpoint_integration.duplicate_slide(src, 2, dst)
    assert len(dst.slides) == 3, "Third slide not duplicated"

    dst, idx = powerpoint_integration.duplicate_slide(src, 1, dst)
    assert len(dst.slides) == 4, "Fourth slide not duplicated"

    dst, idx = powerpoint_integration.duplicate_slide(src, 1, dst)
    assert len(dst.slides) == 5, "Fifth slide not duplicated"

    # Verify all duplicated slides are at the end
    assert idx == len(dst.slides) - 1, "Duplicated slides should be added at the end"

    # Save result
    powerpoint_integration.save_presentation(dst, output_path)
