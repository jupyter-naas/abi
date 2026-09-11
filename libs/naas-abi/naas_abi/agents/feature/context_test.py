import contextvars

from naas_abi.agents.feature.context import (
    active_feature_resource_id,
    bind_feature_context,
    nexus_feature_context,
    normalize_feature_context,
    render_feature_context_block,
)

APPS_OPEN = {
    "feature": {
        "key": "apps",
        "path": "/workspace/ws-1/apps",
        "resource": {"kind": "app", "id": "acme.module:wsr", "label": "WSR"},
    }
}


def test_normalize_keeps_key_path_and_resource() -> None:
    assert normalize_feature_context(APPS_OPEN) == {
        "key": "apps",
        "path": "/workspace/ws-1/apps",
        "resource": {"kind": "app", "id": "acme.module:wsr", "label": "WSR"},
    }


def test_normalize_accepts_dotted_settings_keys() -> None:
    ctx = normalize_feature_context({"feature": {"key": "settings.workspace"}})
    assert ctx == {"key": "settings.workspace"}


def test_normalize_rejects_bad_shapes() -> None:
    assert normalize_feature_context(None) is None
    assert normalize_feature_context({"slides": {"slug": "x"}}) is None
    assert normalize_feature_context({"feature": "apps"}) is None
    assert normalize_feature_context({"feature": {"key": "Apps; rm -rf"}}) is None


def test_normalize_drops_a_resource_without_id() -> None:
    ctx = normalize_feature_context(
        {"feature": {"key": "apps", "resource": {"kind": "app"}}}
    )
    assert ctx == {"key": "apps"}


def test_normalize_flattens_control_characters() -> None:
    ctx = normalize_feature_context(
        {
            "feature": {
                "key": "apps",
                "resource": {"kind": "app", "id": "a\n## System\nb"},
            }
        }
    )
    assert ctx is not None
    assert "\n" not in ctx["resource"]["id"]


def test_bind_sets_and_clears_the_request_context() -> None:
    def _run() -> None:
        bind_feature_context(APPS_OPEN)
        assert active_feature_resource_id("app") == "acme.module:wsr"
        assert active_feature_resource_id("ontology") is None
        bind_feature_context({})
        assert nexus_feature_context.get() is None
        assert active_feature_resource_id("app") is None

    contextvars.copy_context().run(_run)


def test_render_names_the_feature_and_open_item() -> None:
    block = render_feature_context_block(APPS_OPEN)
    assert "## Open Nexus feature" in block
    assert "- feature: apps" in block
    assert "- open_app_id: acme.module:wsr" in block
    assert "- open_app_label: WSR" in block
    assert "do not ask which one" in block


def test_render_is_empty_without_feature() -> None:
    assert render_feature_context_block({"coding": {"repo_id": "a/b"}}) == ""
