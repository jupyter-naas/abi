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
#      the in-engine module the way `abi new module` says, runs their tests;
#   4. `abi dev up -d`, then waits for the API's /docs, the remote module READY
#      in discovery, the agents and apps in Nexus, and the Nexus web app;
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

start_and_check() {
    step "abi dev up -d"
    abi dev up -d
    abi module list
    step "waiting for the stack (up to ${TIMEOUT}s)"
    python3 -u "$REPO/scripts/cli_smoke_checks.py" \
        --api "http://localhost:$(port api)" \
        --web "http://localhost:$(port nexus-web)" \
        --env-file .env --timeout "$TIMEOUT" "$@"
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

    step "uv run pytest (the modules' scaffolded tests)"
    uv run pytest -q

    start_and_check \
        --remote-module "nats_smoke.research:Research" \
        --agents "Research,Legacy,Analyst" \
        --apps "remote/nats_smoke.research:board,legacy:reports"
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

    start_and_check --agents "Tools,Helper"
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
