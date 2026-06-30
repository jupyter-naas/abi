# Minimal Coder template: a Docker workspace running code-server (MIT),
# exposed as a subdomain coder_app shared to the owner. This is the artifact
# the embedding test provisions. Push it with `make template`.
terraform {
  required_providers {
    coder  = { source = "coder/coder" }
    docker = { source = "kreuzwerker/docker" }
  }
}

provider "coder" {}
provider "docker" {}

locals {
  # Caddy's local root CA, trusted inside the workspace so the agent can reach
  # coderd over the Caddy HTTPS edge (https://coder.nexus.localhost). LOCAL TEST.
  caddy_ca = <<-EOT
-----BEGIN CERTIFICATE-----
MIIBozCCAUmgAwIBAgIQVSBZGSjV5jfY0lWt75hloDAKBggqhkjOPQQDAjAwMS4w
LAYDVQQDEyVDYWRkeSBMb2NhbCBBdXRob3JpdHkgLSAyMDI2IEVDQyBSb290MB4X
DTI2MDYyNDA3MTMxM1oXDTM2MDUwMjA3MTMxM1owMDEuMCwGA1UEAxMlQ2FkZHkg
TG9jYWwgQXV0aG9yaXR5IC0gMjAyNiBFQ0MgUm9vdDBZMBMGByqGSM49AgEGCCqG
SM49AwEHA0IABGglg0M25kicsgEArr3UTdf742BE3/BRGp+P9MgEdKQhWNOxFZM5
IbDGeA2VcXLRlFhpMLdtKPU9bt32B457N0mjRTBDMA4GA1UdDwEB/wQEAwIBBjAS
BgNVHRMBAf8ECDAGAQH/AgEBMB0GA1UdDgQWBBSGVbqGLk6jLOHgQ5+NO+799uFB
tDAKBggqhkjOPQQDAgNIADBFAiAPHpa5ITKPiExEEY1SjRiyVpdSZec+iPHkUZ+7
8t8aGwIhAJuUGA/knZOujzAPvTvtcFFy2DR/Z8wHv8CGgUhbFBzj
-----END CERTIFICATE-----
  EOT
}

data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

# Host architecture of the provisioner (== the docker host that runs the
# workspace container). The agent binary MUST match it: declaring amd64 on an
# arm64 host (e.g. Apple Silicon) runs the agent under Rosetta, where the
# tailnet's WireGuard handshake fails ("invalid initiation message") and app
# proxying times out. Deriving the arch keeps the template portable.
data "coder_provisioner" "me" {}

# Branch-per-workspace + agent-bridge parameters (Phase 1/2). In the bundled
# stack these are set by the coding_environment service when it provisions.
data "coder_parameter" "repo_url" {
  name         = "repo_url"
  display_name = "Repository (clone URL)"
  description  = "Forgejo monorepo clone URL (with an embedded scoped token)"
  default      = ""
  mutable      = true
}

data "coder_parameter" "branch" {
  name         = "branch"
  display_name = "Branch"
  description  = "Branch to check out — one workspace per branch"
  default      = "main"
  mutable      = true
}

data "coder_parameter" "abi_api_base" {
  name         = "abi_api_base"
  display_name = "ABI API base"
  description  = "Nexus API base; the OpenAI-compatible shim is at <base>/api/v1"
  default      = "http://host.docker.internal:9879"
  mutable      = true
}

data "coder_parameter" "abi_token" {
  name         = "abi_token"
  display_name = "ABI token"
  description  = "Per-user token Continue uses to reach abi agents via the shim"
  default      = ""
  mutable      = true
}

data "coder_parameter" "abi_agents" {
  name         = "abi_agents"
  display_name = "ABI agents"
  description  = "Comma-separated abi agent ids to expose in Continue's model picker (first = default)"
  default      = "AbiAgent"
  mutable      = true
}

data "coder_parameter" "git_author_name" {
  name         = "git_author_name"
  display_name = "Git author name"
  default      = ""
  mutable      = true
}

data "coder_parameter" "git_author_email" {
  name         = "git_author_email"
  display_name = "Git author email"
  default      = ""
  mutable      = true
}

data "coder_parameter" "docker_network" {
  name         = "docker_network"
  display_name = "Docker network"
  description  = "Attach the workspace to this docker network so it can reach Forgejo/coderd directly (set by the coding_environment service)"
  default      = ""
  mutable      = true
}

data "coder_parameter" "sidecar_secret" {
  name         = "sidecar_secret"
  display_name = "Sidecar secret"
  description  = "Bearer secret the abi server uses to call this workspace's exec sidecar (set by the coding_environment service)"
  default      = ""
  mutable      = true
}

data "coder_parameter" "dev_port" {
  name         = "dev_port"
  display_name = "Dev server port"
  description  = "Port the Preview app proxies to — run your dev server here (e.g. npm run dev) and open Preview"
  default      = "3000"
  mutable      = true
}

locals {
  # The exec sidecar that lets server-side abi agents act on ~/project. Shipped
  # in the template dir and base64-injected so any content is safe in the shell.
  sidecar_b64 = base64encode(file("${path.module}/abi_sidecar.py"))

  # Build Continue's config.json from the agent list so the IDE model picker
  # lists every abi agent the gateway exposes (the first id is the default).
  abi_agent_ids = [
    for a in split(",", data.coder_parameter.abi_agents.value) : trimspace(a)
    if trimspace(a) != ""
  ]
  continue_config = jsonencode({
    models = [
      for name in local.abi_agent_ids : {
        title    = "ABI (${name})"
        provider = "openai"
        model    = name
        apiBase  = "${data.coder_parameter.abi_api_base.value}/api/v1"
        apiKey   = data.coder_parameter.abi_token.value
      }
    ]
  })

  # code-server user settings: make Continue the only AI assistant by turning off
  # VS Code's built-in Copilot/Chat (which otherwise shows the "Sign in to use
  # GitHub Copilot" panel), and quiet first-run prompts.
  code_server_settings = jsonencode({
    "github.copilot.enable"                       = { "*" = false }
    "github.copilot.editor.enableAutoCompletions" = false
    "chat.commandCenter.enabled"                  = false
    "workbench.startupEditor"                     = "none"
    "security.workspace.trust.enabled"            = false
    "telemetry.telemetryLevel"                    = "off"
    # Show the secondary (right) side bar by default so the Continue view —
    # relocated there via workbench.views.customizations (seeded into
    # state.vscdb at startup) — is visible on first load. (Code-OSS >= 1.100.)
    "workbench.secondarySideBar.defaultVisibility" = "visible"
  })
}

resource "coder_agent" "main" {
  arch           = data.coder_provisioner.me.arch
  os             = "linux"
  startup_script = <<-EOT
    set -e
    # 1) The editor.
    if ! command -v code-server >/dev/null 2>&1; then
      curl -fsSL https://code-server.dev/install.sh | sh
    fi
    # 2) Continue extension from Open VSX (the registry code-server uses) — the
    #    bridge to abi + generic agents. Pinned to the last 1.x: Continue 2.x is a
    #    Hub/sign-in rewrite that hides our injected ~/.continue/config.json models
    #    behind onboarding. 1.3.x reads the config.json `models` format natively and
    #    shows the sidebar + agents with no sign-in.
    code-server --install-extension Continue.continue@1.3.40 || true
    # 3) Point Continue at abi's OpenAI-compatible shim (Phase 2). The config is
    #    built server-side (one model entry per registered agent) so the model
    #    picker lists every agent the gateway exposes.
    mkdir -p "$HOME/.continue"
    cat > "$HOME/.continue/config.json" <<'JSON'
    ${local.continue_config}
    JSON
    # 3b) Workspace exec sidecar — lets server-side abi agents read/write files
    #     in ~/project. The abi server calls it over the docker network at
    #     coder-<owner>-<workspace>:8378 with the injected per-workspace secret.
    echo '${local.sidecar_b64}' | base64 -d > "$HOME/.abi_sidecar.py" || true
    ABI_SIDECAR_SECRET="${data.coder_parameter.sidecar_secret.value}" \
      ABI_SIDECAR_ROOT="$HOME/project" ABI_SIDECAR_PORT=8378 \
      nohup python3 "$HOME/.abi_sidecar.py" > /tmp/abi_sidecar.log 2>&1 &
    # 4) Identify the committer so pushes are attributed to the user.
    if [ -n "${data.coder_parameter.git_author_name.value}" ]; then
      git config --global user.name "${data.coder_parameter.git_author_name.value}"
    fi
    if [ -n "${data.coder_parameter.git_author_email.value}" ]; then
      git config --global user.email "${data.coder_parameter.git_author_email.value}"
    fi
    # 5) Clone the monorepo on this workspace's branch (branch-per-workspace).
    #    Always ensure the folder exists so code-server has something to open
    #    even when no repo_url is supplied (otherwise it shows "Workspace does
    #    not exist"). git clone into an existing *empty* dir is fine. The branch
    #    is created server-side before provisioning, so we just check it out.
    mkdir -p "$HOME/project"
    if [ -n "${data.coder_parameter.repo_url.value}" ] && [ ! -d "$HOME/project/.git" ]; then
      git clone "${data.coder_parameter.repo_url.value}" "$HOME/project" || true
      cd "$HOME/project" \
        && (git checkout "${data.coder_parameter.branch.value}" 2>/dev/null \
            || git checkout -b "${data.coder_parameter.branch.value}")
    fi
    # 5b) code-server user settings (written before serving so they load fresh):
    #     disable VS Code's built-in Copilot/Chat so Continue is the AI assistant.
    mkdir -p "$HOME/.config/Code/User" "$HOME/.local/share/code-server/User"
    cat > "$HOME/.config/Code/User/settings.json" <<'SETTINGS'
    ${local.code_server_settings}
    SETTINGS
    cp "$HOME/.config/Code/User/settings.json" \
      "$HOME/.local/share/code-server/User/settings.json" 2>/dev/null || true
    # 5c) Make Continue THE view in the secondary (right) side bar by default.
    #     Two relocations (profile-scoped storage values, not settings keys, so
    #     seed them into globalStorage's state.vscdb before serving):
    #       - Continue's container -> the secondary side bar (location 2).
    #       - VS Code's built-in Chat container -> the bottom panel (location 1),
    #         so it stops occupying the right bar; Continue is then the sole (and
    #         thus foreground) view there. The bar is shown via the setting above.
    python3 - <<'PY' || true
    import os, sqlite3
    d = os.path.expanduser("~/.local/share/code-server/User/globalStorage")
    os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(os.path.join(d, "state.vscdb"))
    con.execute("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    con.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", ("workbench.views.customizations", "{\"viewContainerLocations\": {\"workbench.view.extension.continue\": 2, \"workbench.panel.chat\": 1}, \"viewLocations\": {}, \"viewContainerBadgeEnablementStates\": {}}"))
    con.commit()
    con.close()
    PY
    # 6) Serve the editor on the project, then wait until it is actually up and
    #    warm the workbench once so the extension host loads Continue BEFORE the
    #    user first connects. Without this, code-server reports healthy as soon as
    #    the port is open — but the extension host is still starting, so the first
    #    session renders without the Continue sidebar until a manual reload.
    code-server --auth none --port 13337 --host 0.0.0.0 "$HOME/project" \
      >/tmp/code-server.log 2>&1 &
    for _ in $(seq 1 60); do
      curl -fsS http://localhost:13337/healthz >/dev/null 2>&1 && break
      sleep 1
    done
    # Prime the workbench so the extension host activates extensions now.
    curl -fsS http://localhost:13337/ >/dev/null 2>&1 || true
    sleep 3
  EOT
}

resource "coder_app" "code-server" {
  agent_id     = coder_agent.main.id
  slug         = "code-server"
  display_name = "code-server"
  url          = "http://localhost:13337/"
  icon         = "/icon/code.svg"
  # subdomain app => first-party cookie story works under *.coder.<domain>.
  subdomain = true
  # owner share => the authoritative auth test (a public app needs no cookie).
  share = "owner"
  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 5
    threshold = 6
  }
}

# Preview app: proxies to the user's dev server (run e.g. `npm run dev` on
# dev_port). No healthcheck — the port is down until the user starts a server,
# and a healthcheck would keep the app perpetually "unhealthy" and unproxied.
resource "coder_app" "dev" {
  agent_id     = coder_agent.main.id
  slug         = "dev"
  display_name = "Preview"
  url          = "http://localhost:${data.coder_parameter.dev_port.value}/"
  icon         = "/icon/widgets.svg"
  subdomain    = true
  share        = "owner"
}

resource "docker_image" "main" {
  name = "codercom/enterprise-base:ubuntu"
  # The base image is shared across all workspaces. Without this, destroying one
  # workspace tries to remove the image and fails ("image is in use by another
  # container"), which leaves the whole delete build failed and the workspace
  # stuck — blocking its name. keep_locally leaves the image on the host.
  keep_locally = true
}

resource "docker_container" "workspace" {
  count    = data.coder_workspace.me.start_count
  image    = docker_image.main.name
  name     = "coder-${data.coder_workspace_owner.me.name}-${lower(data.coder_workspace.me.name)}"
  hostname = data.coder_workspace.me.name
  entrypoint = ["sh", "-c", <<-EOT
    printf '%s\n' "${local.caddy_ca}" > /usr/local/share/ca-certificates/caddy-local.crt
    update-ca-certificates >/dev/null 2>&1 || true
    ${coder_agent.main.init_script}
  EOT
  ]
  env = ["CODER_AGENT_TOKEN=${coder_agent.main.token}"]
  host {
    host = "host.docker.internal"
    ip   = "host-gateway"
  }
  # Resolve the Caddy edge so the agent can reach coderd at
  # https://coder.nexus.localhost (CODER_ACCESS_URL).
  host {
    host = "coder.nexus.localhost"
    ip   = "host-gateway"
  }
  # Attach to the platform network (when set) so the workspace can reach Forgejo
  # (git clone/push) and coderd directly — the workspace can't reach the Caddy
  # edge on :443 from inside Docker Desktop, so internal DNS (forgejo:3000,
  # coder:7080) is the reliable path.
  dynamic "networks_advanced" {
    for_each = data.coder_parameter.docker_network.value == "" ? [] : [data.coder_parameter.docker_network.value]
    content {
      name = networks_advanced.value
    }
  }
}
