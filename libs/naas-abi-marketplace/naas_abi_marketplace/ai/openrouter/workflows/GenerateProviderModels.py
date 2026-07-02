"""Generate OpenRouter provider modules and model files from templates.

Templates are loaded from the ``templates/`` subdirectory:

* ``templates/module_init.py.template`` — rendered once per provider to
  produce ``naas_abi_marketplace/ai/<module_name>/__init__.py``
* ``templates/model.py.template`` — rendered once per model to produce
  ``naas_abi_marketplace/ai/openrouter/models/<provider>/<model>.py``

Placeholder syntax: ``{{variable_name}}`` (only ``\\w+`` inside the braces).
This avoids conflicts with the ``{{ secret.X }}`` YAML/Jinja2 notation that
appears in generated docstrings.

Run::

    python libs/naas-abi-marketplace/naas_abi_marketplace/ai/openrouter/workflows/GenerateProviderModels.py

Options::

    --storage-dir   override the datastore root (default: auto-detected)
    --models-dir    override the models output dir (default: auto-detected)
    --ai-dir        override the ai/ output dir (default: auto-detected)
    --only-modules  only regenerate provider __init__.py files
    --only-models   only regenerate model files
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_TEMPLATES_DIR = _THIS_FILE.parent / "templates"
_OPENROUTER_DIR = _THIS_FILE.parent.parent
_MODELS_DIR = _OPENROUTER_DIR / "models"
_AI_DIR = _OPENROUTER_DIR.parent
_STORAGE_DIR = Path("/home/florentlvr/axi-ai/storage/datastore/openrouter/models")

# ---------------------------------------------------------------------------
# Provider metadata
# storage_key: directory name under datastore (None = no models to generate)
# models_subdir: subdirectory name under openrouter/models/ (None = skip)
# ---------------------------------------------------------------------------

PROVIDERS: list[dict] = [
    {
        "module_name": "azure",
        "storage_key": None,
        "models_subdir": None,
        "name": "Azure",
        "description": "Microsoft Azure's cloud platform for deploying AI models and cognitive services.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/azure.png",
        "tags": ["microsoft", "azure", "cloud"],
        "slug": "azure",
        "privacy_policy_url": "https://www.microsoft.com/en-us/privacy/privacystatement",
        "terms_of_service_url": "https://www.microsoft.com/en-us/legal/terms-of-use?oneroute=true",
        "status_page_url": "https://status.azure.com/",
        "headquarters": "US",
        "datacenters": None,
    },
    {
        "module_name": "openai",
        "storage_key": "openai",
        "models_subdir": "openai",
        "name": "OpenAI",
        "description": "OpenAI's API for GPT models, embeddings, and image generation capabilities.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/openai.png",
        "tags": ["openai", "gpt", "language model"],
        "slug": "openai",
        "privacy_policy_url": "https://openai.com/policies/privacy-policy/",
        "terms_of_service_url": "https://openai.com/policies/row-terms-of-use/",
        "status_page_url": "https://status.openai.com/",
        "headquarters": "US",
        "datacenters": None,
    },
    {
        "module_name": "anthropic",
        "storage_key": "anthropic",
        "models_subdir": "anthropic",
        "name": "Anthropic",
        "description": "Anthropic's AI safety company providing Claude models for safe and beneficial AI.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png",
        "tags": ["anthropic", "claude", "language model"],
        "slug": "anthropic",
        "privacy_policy_url": "https://www.anthropic.com/legal/privacy",
        "terms_of_service_url": "https://www.anthropic.com/legal/commercial-terms",
        "status_page_url": "https://status.anthropic.com/",
        "headquarters": "US",
        "datacenters": None,
    },
    {
        "module_name": "nvidia",
        "storage_key": "nvidia",
        "models_subdir": "nvidia",
        "name": "Nvidia",
        "description": "NVIDIA NIM for deploying optimized AI models on NVIDIA accelerated infrastructure.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/nvidia.png",
        "tags": ["nvidia", "nim", "foundation models"],
        "slug": "nvidia",
        "privacy_policy_url": "https://www.nvidia.com/en-us/about-nvidia/privacy-policy/",
        "terms_of_service_url": "https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf",
        "status_page_url": None,
        "headquarters": "US",
        "datacenters": ["US"],
    },
    {
        "module_name": "cloudflare",
        "storage_key": None,
        "models_subdir": None,
        "name": "Cloudflare",
        "description": "Cloudflare Workers AI for running foundation models at the edge with low latency.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/cloudflare.png",
        "tags": ["cloudflare", "workers ai", "edge"],
        "slug": "cloudflare",
        "privacy_policy_url": "https://developers.cloudflare.com/workers-ai/privacy",
        "terms_of_service_url": "https://www.cloudflare.com/service-specific-terms-developer-platform/#developer-platform-terms",
        "status_page_url": "https://www.cloudflarestatus.com/",
        "headquarters": "US",
        "datacenters": None,
    },
    {
        "module_name": "amazon_bedrock",
        "storage_key": None,
        "models_subdir": None,
        "name": "Amazon Bedrock",
        "description": "Amazon Bedrock managed service for foundation models through a unified AWS API.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/bedrock.png",
        "tags": ["aws", "bedrock", "foundation models"],
        "slug": "amazon-bedrock",
        "privacy_policy_url": "https://aws.amazon.com/privacy",
        "terms_of_service_url": "https://aws.amazon.com/service-terms/",
        "status_page_url": "https://health.aws.amazon.com/health/status",
        "headquarters": "US",
        "datacenters": None,
    },
    {
        "module_name": "mistral",
        "storage_key": "mistralai",
        "models_subdir": "mistral",
        "name": "Mistral",
        "description": "Mistral's flagship model with enhanced code generation, mathematics, and reasoning capabilities.",
        "logo_url": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/mistral.png",
        "tags": ["mistral", "code", "language model"],
        "slug": "mistral",
        "privacy_policy_url": "https://mistral.ai/terms/#privacy-policy",
        "terms_of_service_url": "https://mistral.ai/terms/#terms-of-use",
        "status_page_url": "https://status.mistral.ai/",
        "headquarters": "FR",
        "datacenters": None,
    },
]

# ---------------------------------------------------------------------------
# CanonicalModelId mapping: short model ID → enum member name
# ---------------------------------------------------------------------------

CANONICAL_MAP: dict[str, str] = {
    # Anthropic
    "claude-sonnet-4.6": "CLAUDE_SONNET_4_6",
    "claude-sonnet-4.5": "CLAUDE_SONNET_4_5",
    "claude-sonnet-4": "CLAUDE_SONNET_4",
    "claude-sonnet-3.7": "CLAUDE_SONNET_3_7",
    "claude-opus-4.7": "CLAUDE_OPUS_4_7",
    "claude-opus-4.1": "CLAUDE_OPUS_4_1",
    "claude-opus-4": "CLAUDE_OPUS_4",
    "claude-haiku-4.5": "CLAUDE_HAIKU_4_5",
    "claude-haiku-3.5": "CLAUDE_HAIKU_3_5",
    "claude-fable-5": "CLAUDE_FABLE_5",
    "claude-opus-4.5": "CLAUDE_OPUS_4_5",
    "claude-opus-4.6": "CLAUDE_OPUS_4_6",
    "claude-opus-4.6-fast": "CLAUDE_OPUS_4_6_FAST",
    "claude-opus-4.7-fast": "CLAUDE_OPUS_4_7_FAST",
    "claude-opus-4.8": "CLAUDE_OPUS_4_8",
    "claude-opus-4.8-fast": "CLAUDE_OPUS_4_8_FAST",
    "claude-3.5-haiku": "CLAUDE_3_5_HAIKU",
    "claude-3-haiku": "CLAUDE_3_HAIKU",
    # OpenAI — embeddings
    "text-embedding-3-large": "TEXT_EMBEDDING_3_LARGE",
    "text-embedding-3-small": "TEXT_EMBEDDING_3_SMALL",
    "text-embedding-ada-002": "TEXT_EMBEDDING_ADA_002",
    # OpenAI — chat
    "gpt-5": "GPT_5",
    "gpt-5-mini": "GPT_5_MINI",
    "gpt-5-nano": "GPT_5_NANO",
    "gpt-5-pro": "GPT_5_PRO",
    "gpt-5-codex": "GPT_5_CODEX",
    "gpt-5-chat": "GPT_5_CHAT",
    "gpt-5-image": "GPT_5_IMAGE",
    "gpt-5-image-mini": "GPT_5_IMAGE_MINI",
    "gpt-5.1": "GPT_5_1",
    "gpt-5.1-mini": "GPT_5_1_MINI",
    "gpt-5.1-chat": "GPT_5_1_CHAT",
    "gpt-5.1-codex": "GPT_5_1_CODEX",
    "gpt-5.1-codex-max": "GPT_5_1_CODEX_MAX",
    "gpt-5.1-codex-mini": "GPT_5_1_CODEX_MINI",
    "gpt-5.2": "GPT_5_2",
    "gpt-5.2-pro": "GPT_5_2_PRO",
    "gpt-5.2-chat": "GPT_5_2_CHAT",
    "gpt-5.2-codex": "GPT_5_2_CODEX",
    "gpt-5.3-chat": "GPT_5_3_CHAT",
    "gpt-5.3-codex": "GPT_5_3_CODEX",
    "gpt-5.4": "GPT_5_4",
    "gpt-5.4-pro": "GPT_5_4_PRO",
    "gpt-5.4-mini": "GPT_5_4_MINI",
    "gpt-5.4-nano": "GPT_5_4_NANO",
    "gpt-5.4-image-2": "GPT_5_4_IMAGE_2",
    "gpt-5.5": "GPT_5_5",
    "gpt-5.5-pro": "GPT_5_5_PRO",
    "gpt-4.1": "GPT_4_1",
    "gpt-4.1-mini": "GPT_4_1_MINI",
    "gpt-4.1-nano": "GPT_4_1_NANO",
    "gpt-4-turbo": "GPT_4_TURBO",
    "gpt-4-turbo-preview": "GPT_4_TURBO_PREVIEW",
    "gpt-4": "GPT_4",
    "gpt-4o": "GPT_4O",
    "gpt-4o-2024-11-20": "GPT_4O_2024_11_20",
    "gpt-4o-2024-08-06": "GPT_4O_2024_08_06",
    "gpt-4o-2024-05-13": "GPT_4O_2024_05_13",
    "gpt-4o-mini": "GPT_4O_MINI",
    "gpt-4o-mini-2024-07-18": "GPT_4O_MINI_2024_07_18",
    "gpt-4o-search-preview": "GPT_4O_SEARCH_PREVIEW",
    "gpt-4o-mini-search-preview": "GPT_4O_MINI_SEARCH_PREVIEW",
    "gpt-audio": "GPT_AUDIO",
    "gpt-audio-mini": "GPT_AUDIO_MINI",
    "gpt-chat-latest": "GPT_CHAT_LATEST",
    "gpt-3.5-turbo": "GPT_3_5_TURBO",
    "gpt-3.5-turbo-0613": "GPT_3_5_TURBO_0613",
    "gpt-3.5-turbo-16k": "GPT_3_5_TURBO_16K",
    "gpt-3.5-turbo-instruct": "GPT_3_5_TURBO_INSTRUCT",
    "gpt-oss-120b": "GPT_OSS_120B",
    "gpt-oss-120b:free": "GPT_OSS_120B_FREE",
    "gpt-oss-20b": "GPT_OSS_20B",
    "gpt-oss-20b:free": "GPT_OSS_20B_FREE",
    "gpt-oss-safeguard-20b": "GPT_OSS_SAFEGUARD_20B",
    "o1": "O1",
    "o1-pro": "O1_PRO",
    "o3": "O3",
    "o3-pro": "O3_PRO",
    "o3-mini": "O3_MINI",
    "o3-mini-high": "O3_MINI_HIGH",
    "o3-deep-research": "O3_DEEP_RESEARCH",
    "o4-mini": "O4_MINI",
    "o4-mini-high": "O4_MINI_HIGH",
    "o4-mini-deep-research": "O4_MINI_DEEP_RESEARCH",
    # Nvidia
    "nemotron-3.5-content-safety:free": "NEMOTRON_3_5_CONTENT_SAFETY_FREE",
    "nemotron-3-ultra-550b-a55b": "NEMOTRON_3_ULTRA_550B_A55B",
    "nemotron-3-ultra-550b-a55b:free": "NEMOTRON_3_ULTRA_550B_A55B_FREE",
    "nemotron-3-super-120b-a12b": "NEMOTRON_3_SUPER_120B_A12B",
    "nemotron-3-super-120b-a12b:free": "NEMOTRON_3_SUPER_120B_A12B_FREE",
    "nemotron-3-nano-30b-a3b": "NEMOTRON_3_NANO_30B_A3B",
    "nemotron-3-nano-30b-a3b:free": "NEMOTRON_3_NANO_30B_A3B_FREE",
    "nemotron-3-nano-omni-30b-a3b-reasoning:free": "NEMOTRON_3_NANO_OMNI_30B_A3B_REASONING_FREE",
    "nemotron-nano-9b-v2": "NEMOTRON_NANO_9B_V2",
    "nemotron-nano-9b-v2:free": "NEMOTRON_NANO_9B_V2_FREE",
    "nemotron-nano-12b-v2-vl:free": "NEMOTRON_NANO_12B_V2_VL_FREE",
    "llama-3.3-nemotron-super-49b-v1.5": "LLAMA_3_3_NEMOTRON_SUPER_49B_V1_5",
    # Mistral
    "mistral-large-2512": "MISTRAL_LARGE_2512",
    "mistral-large-2407": "MISTRAL_LARGE_2407",
    "mistral-large": "MISTRAL_LARGE",
    "mistral-medium-3": "MISTRAL_MEDIUM_3",
    "mistral-medium-3.1": "MISTRAL_MEDIUM_3_1",
    "mistral-medium-3-5": "MISTRAL_MEDIUM_3_5",
    "mistral-small-24b-instruct-2501": "MISTRAL_SMALL_24B_INSTRUCT_2501",
    "mistral-small-2603": "MISTRAL_SMALL_2603",
    "mistral-small-3.1-24b-instruct": "MISTRAL_SMALL_3_1_24B_INSTRUCT",
    "mistral-small-3.2-24b-instruct": "MISTRAL_SMALL_3_2_24B_INSTRUCT",
    "mistral-nemo": "MISTRAL_NEMO",
    "mistral-saba": "MISTRAL_SABA",
    "ministral-3b-2512": "MINISTRAL_3B_2512",
    "ministral-8b-2512": "MINISTRAL_8B_2512",
    "ministral-14b-2512": "MINISTRAL_14B_2512",
    "mixtral-8x22b-instruct": "MIXTRAL_8X22B_INSTRUCT",
    "codestral-2508": "CODESTRAL_2508",
    "devstral-2512": "DEVSTRAL_2512",
    "voxtral-small-24b-2507": "VOXTRAL_SMALL_24B_2507",
}

# ---------------------------------------------------------------------------
# Template engine
# Placeholder syntax: {{variable_name}} where variable_name matches \w+
# Leaves {{ secret.X }} and similar Jinja2/YAML expressions untouched.
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _render(template: str, variables: dict) -> str:
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return str(variables[key]) if key in variables else match.group(0)

    return _PLACEHOLDER.sub(_replace, template)


# ---------------------------------------------------------------------------
# Model file helpers
# ---------------------------------------------------------------------------


def _to_filename(model_id: str) -> str:
    short = model_id.split("/", 1)[1] if "/" in model_id else model_id
    name = re.sub(r"[^a-z0-9]", "_", short.lower())
    return re.sub(r"_+", "_", name).strip("_")


def _to_classname(model_id: str) -> str:
    short = model_id.split("/", 1)[1] if "/" in model_id else model_id
    return (
        "".join(p.capitalize() for p in re.split(r"[^a-zA-Z0-9]", short) if p)
        + "Model"
    )


def _is_embedding(model: dict) -> bool:
    arch = model.get("architecture") or {}
    return "embed" in model.get("id", "").lower() or "embed" in arch.get(
        "modality", ""
    ).lower()


def _canonical_expr(model_id: str) -> str:
    short = model_id.split("/", 1)[1] if "/" in model_id else model_id
    member = CANONICAL_MAP.get(short)
    return f"CanonicalModelId.{member}" if member else f'"{short}"'


def _py_str(value: str | None) -> str:
    if value is None:
        return "None"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _model_vars(model: dict, owner: str) -> dict:
    mid = model["id"]
    embed = _is_embedding(model)
    lc_import = "OpenAIEmbeddings" if embed else "ChatOpenAI"
    model_type = "EmbeddingModel" if embed else "ChatModel"

    if embed:
        lc_model_expr = (
            "OpenAIEmbeddings(\n"
            "            model=MODEL_ID,\n"
            "            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),\n"
            "            base_url=OPENROUTER_BASE_URL,\n"
            "        )"
        )
        context_line = ""
    else:
        lc_model_expr = (
            "ChatOpenAI(\n"
            "            model=MODEL_ID,\n"
            "            temperature=0,\n"
            "            timeout=120,\n"
            "            max_retries=3,\n"
            "            api_key=SecretStr(ABIModule.get_instance().configuration.openrouter_api_key),\n"
            "            base_url=OPENROUTER_BASE_URL,\n"
            "        )"
        )
        context_line = f"\n        context_window={model.get('context_length')},"

    created_ts = model.get("created")
    return {
        "lc_import": lc_import,
        "model_type": model_type,
        "class_name": _to_classname(mid),
        "canonical": _canonical_expr(mid),
        "model_id": mid,
        "lc_model_expr": lc_model_expr,
        "context_line": context_line,
        "name": _py_str(model.get("name")),
        "owner": _py_str(owner),
        "description": _py_str(model.get("description")),
        "canonical_slug": _py_str(model.get("canonical_slug")),
        "hugging_face_id": _py_str(model.get("hugging_face_id")),
        "created_at": f"datetime.fromtimestamp({created_ts})" if created_ts else "None",
        "pricing": repr(model.get("pricing")),
        "architecture": repr(model.get("architecture")),
        "top_provider": repr(model.get("top_provider")),
        "per_request_limits": repr(model.get("per_request_limits")),
        "supported_parameters": repr(model.get("supported_parameters")),
        "default_parameters": repr(model.get("default_parameters")),
    }


# ---------------------------------------------------------------------------
# Module init helpers
# ---------------------------------------------------------------------------


def _module_vars(p: dict) -> dict:
    module_name = p["module_name"]
    return {
        "module_name": module_name,
        "MODULE_NAME": module_name.upper(),
        "name": p["name"],
        "description": p["description"],
        "logo_url": p["logo_url"],
        "tags_repr": repr(p["tags"]),
        "slug": p["slug"],
        "privacy_policy_url": p["privacy_policy_url"],
        "terms_of_service_url": p["terms_of_service_url"],
        "status_page_url_repr": repr(p["status_page_url"]),
        "headquarters": p["headquarters"],
        "datacenters_repr": repr(p["datacenters"]),
    }


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------


def generate_provider_modules(
    ai_dir: Path = _AI_DIR,
    templates_dir: Path = _TEMPLATES_DIR,
) -> int:
    """Render module_init.py.template for every provider and write
    ``ai/<module_name>/__init__.py``. Returns count of files written."""
    template_path = templates_dir / "module_init.py.template"
    template = template_path.read_text()
    written = 0
    for p in PROVIDERS:
        module_dir = ai_dir / p["module_name"]
        module_dir.mkdir(parents=True, exist_ok=True)
        content = _render(template, _module_vars(p))
        (module_dir / "__init__.py").write_text(content)
        print(f"[module] {p['module_name']}/__init__.py")
        written += 1
    return written


def generate_provider_models(
    storage_dir: Path = _STORAGE_DIR,
    models_dir: Path = _MODELS_DIR,
    templates_dir: Path = _TEMPLATES_DIR,
) -> int:
    """Render model.py.template for every model in every provider that has
    storage data. Returns count of model files written."""
    template_path = templates_dir / "model.py.template"
    template = template_path.read_text()
    written = 0
    for p in PROVIDERS:
        if not p.get("storage_key") or not p.get("models_subdir"):
            continue
        json_path = storage_dir / p["storage_key"] / "models.json"
        if not json_path.exists():
            print(f"[SKIP] {p['storage_key']}: {json_path} not found", file=sys.stderr)
            continue
        with open(json_path) as fh:
            models: list[dict] = json.load(fh)

        provider_dir = models_dir / p["models_subdir"]
        provider_dir.mkdir(parents=True, exist_ok=True)
        init = provider_dir / "__init__.py"
        if not init.exists():
            init.write_text(f'"""OpenRouter models — {p["storage_key"]} provider."""\n')

        for model in models:
            fname = _to_filename(model["id"]) + ".py"
            content = _render(template, _model_vars(model, p["storage_key"]))
            (provider_dir / fname).write_text(content)
            written += 1

        print(f"[models] {p['models_subdir']}: {len(models)} files")
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="GenerateProviderModels", description=__doc__)
    p.add_argument("--storage-dir", type=Path, default=_STORAGE_DIR)
    p.add_argument("--models-dir", type=Path, default=_MODELS_DIR)
    p.add_argument("--ai-dir", type=Path, default=_AI_DIR)
    p.add_argument("--only-modules", action="store_true")
    p.add_argument("--only-models", action="store_true")
    return p


if __name__ == "__main__":
    args = _parser().parse_args()
    total = 0
    if not args.only_models:
        total += generate_provider_modules(ai_dir=args.ai_dir)
    if not args.only_modules:
        total += generate_provider_models(
            storage_dir=args.storage_dir,
            models_dir=args.models_dir,
        )
    print(f"\nDone — {total} files written.")
