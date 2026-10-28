#!/usr/bin/env bash
# CLI end-to-end smoke test: create a project with the CLI, add modules, start
# it with `abi dev up` and check it serves. CI runs it on every PR into main
# (.github/workflows/cli_e2e.yml); run it locally the same way:
#
#   scripts/cli_smoke.sh                 # both variants, one after the other
#   scripts/cli_smoke.sh nats            # the default project (NATS)
#   scripts/cli_smoke.sh without-nats    # the legacy project (--without-nats)
#
# Needs uv, git, curl, python3, pnpm (Node.js 18.17+) and, for the NATS variant,
# nats-server 2.14 or later on PATH. No Docker, no model download, no chat: the
# AI provider key is a placeholder. A run takes 5-10 minutes per variant.
#
# In a temp dir, it:
#   1. installs the CLI from this checkout (`uv tool install`, in the temp dir);
#   2. `abi new project --abi-source <this checkout>`: the project's `.abi`
#      submodule is a clone of this checkout's HEAD, so the framework comes
#      from the code under test (proto and the SDK come from it too);
#   3. adds a remote module and an in-engine one, an agent and an app, enables
#      the in-engine module the way `abi new module` says, runs their tests; in
#      the remote module also a workflow, a pipeline, an
#      integration and a second ontology, scaffolded the way a user would;
#   4. `abi dev up -d`, then waits for the API's /docs, the remote module READY
#      in discovery with its workflows, the agents and apps in Nexus, its ontologies in
#      the engine's schema graph, and the Nexus web app; calls the module's
#      workflow and pipeline by name as durable workflows, as the module itself
#      (a key of its own account), and reads a run's record
#      (scripts/cli_smoke_processes.py);
#   5. `abi dev down`.
# On failure it prints `abi dev status` and `abi dev logs` and exits non-zero.
#
# Environment:
#   ABI_SMOKE_DIR      work dir (default: a new temp dir). Logs: $ABI_SMOKE_DIR/logs
#   ABI_SMOKE_KEEP=1   keep the work dir (it is removed after a passing run)
#   ABI_SMOKE_TIMEOUT  seconds the stack has to pass every check (default 900)
#
# The project's `.abi` is a clone of HEAD: commit what you want tested under
# libs/. The CLI that creates the project is installed from the working tree.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VARIANTS=("${@:-all}")
if [[ "${VARIANTS[0]}" == all ]]; then
    VARIANTS=(nats without-nats)
fi
for variant in "${VARIANTS[@]}"; do
    case "$variant" in
        nats | without-nats) ;;
        *) echo "usage: $0 [nats|without-nats|all]" >&2; exit 2 ;;
    esac
done

WORK="${ABI_SMOKE_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/abi-cli-smoke.XXXXXX")}"
mkdir -p "$WORK/logs"
WORK="$(cd "$WORK" && pwd)"
TIMEOUT="${ABI_SMOKE_TIMEOUT:-900}"

step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null || fail "$1 is not on PATH. $2"
}
require uv "https://docs.astral.sh/uv/getting-started/installation/"
require git ""
require curl ""
require python3 ""
require pnpm "https://pnpm.io/installation"
if [[ " ${VARIANTS[*]} " == *" nats "* ]]; then
    require nats-server \
        "https://docs.nats.io/running-a-nats-service/introduction/installation"
fi

if [[ -n "$(git -C "$REPO" status --porcelain -- libs)" ]]; then
    echo "warning: uncommitted changes under libs/ are not in the project's .abi" \
        "(a clone of HEAD); the CLI that creates the project has them." >&2
fi

# The generated config names the AI provider's key and the engine will not
# load without it. The smoke test never chats: a placeholder, never a real key.
export OPENROUTER_API_KEY=smoke-test-placeholder
# Its own CLI install, never the user's `abi`.
export UV_TOOL_DIR="$WORK/tools" UV_TOOL_BIN_DIR="$WORK/bin"
export PATH="$WORK/bin:$PATH"

PROJECT=""        # the project `abi dev` runs in, while it runs
VARIANT=""
PROCESS_CHECKS=() # cli_smoke_processes.py's arguments, when the variant has any
PROCESS_MODULE_ID=""  # the module id they name: the probe holds a key of its account
PROCESS_PROJECT=""    # its discovery project (the account is module/<project>/<module id>)

dump_logs() {
    local logs="$WORK/logs/$VARIANT"
    mkdir -p "$logs"
    cp -r "$PROJECT/.abi/dev/logs/." "$logs/" 2>/dev/null || true
    (cd "$PROJECT" && abi dev status) || true
    local service
    for service in $(cd "$PROJECT" && abi dev ports 2>/dev/null | awk '{print $1}') \
        $(sed -n 's/^    - name: //p' "$PROJECT/config.yaml"); do
        [[ -s "$PROJECT/.abi/dev/logs/$service.log" ]] || continue
        printf '\n----- abi dev logs %s -----\n' "$service"
        (cd "$PROJECT" && abi dev logs "$service" -n 200) || true
    done
}

on_exit() {
    local status=$?
    if [[ -n "$PROJECT" ]]; then
        if [[ $status -ne 0 ]]; then
            step "$VARIANT failed: abi dev status and logs (also in $WORK/logs/$VARIANT)"
            dump_logs
        fi
        step "abi dev down"
        (cd "$PROJECT" && abi dev down) || true
    fi
    if [[ $status -ne 0 ]]; then
        echo "FAIL: CLI smoke test ($VARIANT). Work dir kept: $WORK" >&2
    elif [[ "${ABI_SMOKE_KEEP:-}" == 1 ]]; then
        echo "Work dir kept: $WORK"
    else
        rm -rf "$WORK"
    fi
    exit "$status"
}
trap on_exit EXIT
# A killed run (CI timeout, Ctrl-C) fails and still stops the stack.
trap 'exit 143' TERM
trap 'exit 130' INT

# `abi new module --in-engine` says to add it under `modules:` in config.yaml.
enable_module() {
    python3 - "$1" <<'PY'
import sys
from pathlib import Path

config = Path("config.yaml")
text = config.read_text(encoding="utf-8")
entry = f"modules:\n  - module: {sys.argv[1]}\n    enabled: true\n"
assert text.count("\nmodules:\n") == 1, "no top-level modules: list"
config.write_text(text.replace("\nmodules:\n", "\n" + entry, 1), encoding="utf-8")
PY
}

port() {
    abi dev ports 2>/dev/null | awk -v name="$1" '$1 == name {print $2}'
}

# A second ontology file, next to the one the module template ships.
write_ontology() {
    mkdir -p "$(dirname "$1")"
    cat >"$1" <<'TTL'
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://ontology.naas.ai/nats_smoke/ReviewOntology> a owl:Ontology ;
    rdfs:label "Review ontology"@en .

<http://ontology.naas.ai/nats_smoke/Review> a owl:Class ;
    rdfs:label "Review"@en .
TTL
}

start_and_check() {
    step "abi dev up -d"
    abi dev up -d
    abi module list
    step "waiting for the stack (up to ${TIMEOUT}s)"
    python3 -u "$REPO/scripts/cli_smoke_checks.py" \
        --api "http://localhost:$(port api)" \
        --web "http://localhost:$(port nexus-web)" \
        --oxigraph "http://localhost:$(port oxigraph)" \
        --mail-dir storage/email --timeout "$TIMEOUT" "$@"
    if [[ ${#PROCESS_CHECKS[@]} -gt 0 ]]; then
        step "the remote module's workflow and pipeline over NATS"
        # As the module itself, with a key of its own service account: the
        # broker's auth callout logs it in. The key goes through the
        # environment, not argv.
        ABI_NATS_URL="nats://127.0.0.1:$(port nats)" \
            ABI_SERVICE_KEY="$(abi iam key create "module/$PROCESS_PROJECT/$PROCESS_MODULE_ID" \
                --description "CLI smoke probe" --expires-in-days 1 2>/dev/null)" \
            uv run python "$REPO/scripts/cli_smoke_processes.py" \
            --timeout "$TIMEOUT" "${PROCESS_CHECKS[@]}"
        PROCESS_CHECKS=()
    fi
    abi dev status
    mkdir -p "$WORK/logs/$VARIANT"
    cp -r .abi/dev/logs/. "$WORK/logs/$VARIANT/"
    step "abi dev down"
    abi dev down
    PROJECT=""
}

smoke_nats() {
    local name=nats-smoke
    step "abi new project $name (NATS, sources from $REPO)"
    cd "$WORK"
    abi new project "$name" --abi-source "$REPO" --domain localhost
    cd "$WORK/$name"
    PROJECT="$PWD"

    step "abi new module research (remote) and legacy (--in-engine)"
    abi new module research
    abi new module legacy --in-engine
    enable_module legacy
    step "abi new agent and abi new app, in both modules"
    (cd src/legacy && abi new agent analyst agents && abi new app reports apps)
    (cd src/research && abi new app board apps)

    step "abi new workflow, pipeline and integration, and an ontology, in the remote module"
    (
        cd src/research
        abi new workflow digest workflows
        abi new pipeline catalog pipelines
        abi new integration crm integrations
    )
    write_ontology src/research/ontologies/domain/ReviewOntology.ttl

    step "uv run pytest (the modules' scaffolded tests, the new processes' too)"
    uv run pytest -q
    # The run above collects the scaffolds' tests: make sure they exist.
    test -f src/research/workflows/DigestWorkflow_test.py \
        -a -f src/research/pipelines/CatalogPipeline_test.py \
        -a -f src/research/integrations/CrmIntegration_test.py \
        || fail "a scaffold did not write its test"

    PROCESS_MODULE_ID=nats_smoke.research
    PROCESS_PROJECT=nats_smoke
    PROCESS_CHECKS=(
        --module-id "$PROCESS_MODULE_ID" --project "$PROCESS_PROJECT"
        --workflow digest_workflow --pipeline catalog_pipeline
    )
    start_and_check \
        --remote-module "nats_smoke.research:Research" \
        --remote-jobs "workflow.digest_workflow,pipeline.catalog_pipeline" \
        --agents "Research,Legacy,Analyst" \
        --apps "remote/nats_smoke.research:board,legacy:reports" \
        --ontologies "module/nats_smoke.research/modules/ResearchOntology.ttl,module/nats_smoke.research/domain/ReviewOntology.ttl" \
        --ontology-class "http://ontology.naas.ai/nats_smoke/Review"
}

smoke_without_nats() {
    local name=classic-smoke
    step "abi new project $name --without-nats (legacy, sources from $REPO)"
    cd "$WORK"
    abi new project "$name" --without-nats --abi-source "$REPO" --domain localhost
    cd "$WORK/$name"
    PROJECT="$PWD"

    step "abi new module tools (in-engine: the project has no nats: block)"
    abi new module tools
    enable_module tools
    (cd src/tools && abi new agent helper agents)

    # No built-in identity provider without NATS: no sign-in, so no roster to read.
    start_and_check --no-sign-in
}

step "uv tool install the CLI from $REPO/libs/naas-abi-cli (in $WORK)"
uv tool install --quiet --python 3.12 "$REPO/libs/naas-abi-cli"
abi --help >/dev/null

started=$SECONDS
for VARIANT in "${VARIANTS[@]}"; do
    variant_started=$SECONDS
    case "$VARIANT" in
        nats) smoke_nats ;;
        without-nats) smoke_without_nats ;;
    esac
    step "PASS $VARIANT ($((SECONDS - variant_started))s)"
done
printf '\nCLI smoke test passed: %s in %ss.\n' "${VARIANTS[*]}" "$((SECONDS - started))"
