#!/bin/sh
# One-shot bootstrap for the coding-workspaces stack (compose `coding-init`).
# Idempotent, safe to re-run on every `up`. It NEVER fails the container (always
# exits 0) so abi/act-runner are not blocked by a transient hiccup; re-running
# `up` retries. It:
#   1. mints a long-lived Coder admin token (create first user + API token),
#   2. creates a Forgejo admin and mints an access token (Forgejo CLI as `git`),
#   3. registers the Forgejo Actions runner with the shared 40-hex secret,
# writing the two tokens into the host .env, which abi reads at startup (its
# dotenv secret adapter reads the file, not compose-injected env).

log() { echo "[coding-init] $*"; }

# docker:cli is Alpine and ships neither curl nor jq.
if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  apk add --no-cache curl jq >/dev/null 2>&1 || log "WARN: could not install curl/jq"
fi

ENV_FILE=/host/.env
CODER_URL="http://coder:7080"
FORGEJO_URL="http://forgejo:3000"
FORGEJO_ORG="${CODING_FORGEJO_ORG:-abi}"

# Resolve the Forgejo container by its compose-service label. -q avoids docker
# --format go-templates, whose double braces would collide with the Jinja that
# renders this file at `abi deploy local` time.
FJ_CID="$(docker ps -q --filter label=com.docker.compose.service=forgejo | head -1)"
fj() { docker exec -u git "$FJ_CID" "$@"; }

# Set KEY=VALUE in the host .env; never clobber an existing non-empty value.
set_env() {
  _k="$1"; _v="$2"
  if grep -qE "^${_k}=" "$ENV_FILE" 2>/dev/null; then
    _cur="$(grep -E "^${_k}=" "$ENV_FILE" | head -1 | cut -d= -f2-)"
    if [ -n "$_cur" ]; then log "$_k already set : keeping"; return 0; fi
    _tmp="$(mktemp)"; sed "s|^${_k}=.*|${_k}=${_v}|" "$ENV_FILE" > "$_tmp" && cat "$_tmp" > "$ENV_FILE"; rm -f "$_tmp"
  else
    printf '%s=%s\n' "$_k" "$_v" >> "$ENV_FILE"
  fi
  log "$_k written to .env"
}

env_has() { grep -qE "^$1=.+" "$ENV_FILE" 2>/dev/null; }

wait_url() {
  _i=0
  while [ "$_i" -lt 90 ]; do
    curl -fsS "$1" >/dev/null 2>&1 && return 0
    _i=$((_i + 1)); sleep 2
  done
  return 1
}

# --------------------------------------------------------------------- Coder
if env_has CODER_ADMIN_TOKEN; then
  log "CODER_ADMIN_TOKEN present : skipping Coder bootstrap"
else
  log "waiting for Coder..."
  if wait_url "$CODER_URL/api/v2/buildinfo"; then
    curl -fsS -X POST "$CODER_URL/api/v2/users/first" -H 'Content-Type: application/json' \
      -d "$(printf '{"email":"%s","username":"%s","password":"%s","name":"Admin","trial":false}' \
            "$CODER_ADMIN_EMAIL" "$CODER_ADMIN_USERNAME" "$CODER_ADMIN_PASSWORD")" \
      >/dev/null 2>&1 || log "  (Coder first user already exists)"
    SESSION="$(curl -fsS -X POST "$CODER_URL/api/v2/users/login" -H 'Content-Type: application/json' \
      -d "$(printf '{"email":"%s","password":"%s"}' "$CODER_ADMIN_EMAIL" "$CODER_ADMIN_PASSWORD")" \
      2>/dev/null | jq -r '.session_token // empty')"
    if [ -n "$SESSION" ]; then
      # ~1y lifetime in nanoseconds (within CODER_MAX_ADMIN_TOKEN_LIFETIME=8760h).
      KEY="$(curl -fsS -X POST "$CODER_URL/api/v2/users/me/keys/tokens" \
        -H "Coder-Session-Token: $SESSION" -H 'Content-Type: application/json' \
        -d '{"token_name":"nexus-admin","lifetime":31536000000000000}' \
        2>/dev/null | jq -r '.key // empty')"
      if [ -n "$KEY" ]; then set_env CODER_ADMIN_TOKEN "$KEY"; else log "WARN: Coder token mint failed"; fi
    else
      log "WARN: Coder login failed"
    fi
  else
    log "WARN: Coder not reachable : skipping"
  fi
fi

# ------------------------------------------------------------------- Forgejo
if [ -z "$FJ_CID" ]; then
  log "WARN: forgejo container not found : skipping Forgejo bootstrap"
else
  log "waiting for Forgejo..."
  wait_url "$FORGEJO_URL/api/v1/version" || log "WARN: Forgejo API slow; trying anyway"
  fj forgejo admin user create --admin --username "$FORGEJO_ADMIN_USERNAME" \
     --email "$FORGEJO_ADMIN_EMAIL" --password "$FORGEJO_ADMIN_PASSWORD" \
     --must-change-password=false >/dev/null 2>&1 || log "  (Forgejo admin already exists)"
  if env_has FORGEJO_ADMIN_TOKEN; then
    log "FORGEJO_ADMIN_TOKEN present : skipping token mint"
  else
    TOK="$(fj forgejo admin user generate-access-token -u "$FORGEJO_ADMIN_USERNAME" \
           --raw --scopes all --token-name nexus 2>/dev/null | tr -d '\r' | tail -1)"
    case "$TOK" in
      "" | *[!0-9a-f]*) log "WARN: Forgejo token mint skipped (exists or error)" ;;
      *) set_env FORGEJO_ADMIN_TOKEN "$TOK" ;;
    esac
  fi
  # Nexus Code creates repos under owner CODING_FORGEJO_ORG (default abi) and
  # probes GET /users/<org>. Without this org, GetUserByName(abi) 404s and the
  # Code UI shows no repositories.
  FJ_TOK="$(grep -E '^FORGEJO_ADMIN_TOKEN=.+' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)"
  if [ -n "$FJ_TOK" ]; then
    if curl -fsS -H "Authorization: token $FJ_TOK" \
         "$FORGEJO_URL/api/v1/users/$FORGEJO_ORG" >/dev/null 2>&1; then
      log "Forgejo org/user $FORGEJO_ORG already exists"
    else
      log "creating Forgejo organization $FORGEJO_ORG"
      curl -fsS -X POST "$FORGEJO_URL/api/v1/orgs" \
        -H "Authorization: token $FJ_TOK" -H "Content-Type: application/json" \
        -d "$(printf '{"username":"%s","visibility":"private"}' "$FORGEJO_ORG")" \
        >/dev/null 2>&1 \
        || log "WARN: could not create Forgejo org $FORGEJO_ORG"
    fi
    if ! curl -fsS -H "Authorization: token $FJ_TOK" \
         "$FORGEJO_URL/api/v1/repos/$FORGEJO_ORG/monorepo" >/dev/null 2>&1; then
      log "creating $FORGEJO_ORG/monorepo"
      curl -fsS -X POST "$FORGEJO_URL/api/v1/admin/users/$FORGEJO_ORG/repos" \
        -H "Authorization: token $FJ_TOK" -H "Content-Type: application/json" \
        -d '{"name":"monorepo","private":true,"auto_init":true}' \
        >/dev/null 2>&1 \
        || log "WARN: could not create $FORGEJO_ORG/monorepo"
    else
      log "$FORGEJO_ORG/monorepo already exists"
    fi
  else
    log "WARN: no FORGEJO_ADMIN_TOKEN : skipping org/repo seed"
  fi
  log "registering Actions runner..."
  fj forgejo forgejo-cli actions register --secret "$FORGEJO_RUNNER_REGISTRATION_TOKEN" --scope "$FORGEJO_ORG" >/dev/null 2>&1 \
    || fj forgejo forgejo-cli actions register --secret "$FORGEJO_RUNNER_REGISTRATION_TOKEN" >/dev/null 2>&1 \
    || log "WARN: runner registration skipped"
fi

# ----------------------------------------------------------- Coder templates
CODER_CID="$(docker ps -q --filter label=com.docker.compose.service=coder | head -1)"
TEMPLATE_DIR="/host/.abi/.deploy/docker/coder_prototype/template"
CODER_TOK="$(grep -E '^CODER_ADMIN_TOKEN=.+' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-)"
if [ -z "$CODER_CID" ] || [ -z "$CODER_TOK" ]; then
  log "WARN: coder or CODER_ADMIN_TOKEN missing : skipping template push"
elif [ ! -f "$TEMPLATE_DIR/main.tf" ]; then
  # Local `abi deploy --coding` / ABI checkout: templates live under .deploy/docker.
  TEMPLATE_DIR="/host/.deploy/docker/coder_prototype/template"
  if [ ! -f "$TEMPLATE_DIR/main.tf" ]; then
    log "WARN: coder template main.tf missing : skipping template push"
    TEMPLATE_DIR=""
  fi
fi
if [ -n "${TEMPLATE_DIR:-}" ] && [ -f "$TEMPLATE_DIR/main.tf" ] && [ -n "$CODER_CID" ] && [ -n "$CODER_TOK" ]; then
  TPL_COUNT="$(curl -fsS -H "Coder-Session-Token: $CODER_TOK" \
    "$CODER_URL/api/v2/templates" 2>/dev/null | jq 'length' 2>/dev/null || echo 0)"
  if [ "${TPL_COUNT:-0}" != "0" ]; then
    log "Coder templates already present ($TPL_COUNT) : skipping push"
  else
    log "pushing Coder template abi-code-server..."
    docker exec "$CODER_CID" rm -rf /tmp/template >/dev/null 2>&1 || true
    if docker cp "$TEMPLATE_DIR" "$CODER_CID:/tmp/template" >/dev/null 2>&1 \
      && docker exec -e CODER_SESSION_TOKEN="$CODER_TOK" "$CODER_CID" \
           coder templates push abi-code-server -d /tmp/template --yes \
           --url http://127.0.0.1:7080 >/dev/null 2>&1; then
      log "Coder template abi-code-server pushed"
    else
      log "WARN: Coder template push failed"
    fi
  fi
fi

log "done."
exit 0
