"""The catalog sync must land new models in importable packages and leave
files that already exist alone."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "generate_provider_models",
    Path(__file__).with_name("GenerateProviderModels.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


def test_provider_dirs_stay_importable() -> None:
    assert gen.provider_dir_name("x-ai") == "xai"
    assert gen.provider_dir_name("mistralai") == "mistral"
    assert gen.provider_dir_name("z-ai") == "z_ai"
    assert gen.provider_dir_name("~openai") == "alt_openai"
    assert gen.provider_dir_name("liquid").isidentifier()


def test_add_missing_models_skips_ids_already_on_disk(tmp_path: Path) -> None:
    models = tmp_path / "models"
    openai = models / "openai"
    openai.mkdir(parents=True)
    (openai / "gpt_4o.py").write_text('MODEL_ID = "openai/gpt-4o"\n', encoding="utf-8")
    templates = Path(__file__).with_name("templates")

    added = gen.add_missing_models(
        [
            {"id": "openai/gpt-4o", "name": "GPT-4o", "created": 1},
            {
                "id": "liquid/lfm-3-1.7b:free",
                "name": "LFM3 1.7B",
                "created": 1,
                "context_length": 262144,
                "description": "small",
                "pricing": {"prompt": "0"},
                "architecture": {"modality": "text->text"},
                "top_provider": {"context_length": 262144},
                "supported_parameters": ["tools"],
                "default_parameters": {},
                "canonical_slug": "liquid/lfm-3-1.7b",
                "hugging_face_id": None,
                "per_request_limits": None,
            },
        ],
        models_dir=models,
        templates_dir=templates,
    )

    assert added == 1
    written = (models / "liquid" / "lfm_3_1_7b_free.py").read_text(encoding="utf-8")
    assert 'MODEL_ID = "liquid/lfm-3-1.7b:free"' in written
    assert 'CANONICAL_ID = "lfm-3-1.7b:free"' in written
    assert "CanonicalModelId" not in written
    assert (openai / "gpt_4o.py").read_text(encoding="utf-8") == 'MODEL_ID = "openai/gpt-4o"\n'
