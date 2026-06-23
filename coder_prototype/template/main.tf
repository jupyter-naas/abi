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

data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

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

data "coder_parameter" "abi_agent" {
  name         = "abi_agent"
  display_name = "Default agent"
  default      = "aia"
  mutable      = true
}

resource "coder_agent" "main" {
  arch           = "amd64"
  os             = "linux"
  startup_script = <<-EOT
    set -e
    # 1) The editor.
    if ! command -v code-server >/dev/null 2>&1; then
      curl -fsSL https://code-server.dev/install.sh | sh
    fi
    # 2) Continue extension from Open VSX (the registry code-server uses) — the
    #    bridge to abi + generic agents.
    code-server --install-extension Continue.continue || true
    # 3) Point Continue at abi's OpenAI-compatible shim (Phase 2).
    mkdir -p "$HOME/.continue"
    cat > "$HOME/.continue/config.json" <<JSON
    {
      "models": [
        {
          "title": "ABI (${data.coder_parameter.abi_agent.value})",
          "provider": "openai",
          "model": "${data.coder_parameter.abi_agent.value}",
          "apiBase": "${data.coder_parameter.abi_api_base.value}/api/v1",
          "apiKey": "${data.coder_parameter.abi_token.value}"
        }
      ]
    }
    JSON
    # 4) Clone the monorepo on this workspace's branch (branch-per-workspace).
    if [ -n "${data.coder_parameter.repo_url.value}" ] && [ ! -d "$HOME/project/.git" ]; then
      git clone "${data.coder_parameter.repo_url.value}" "$HOME/project" || true
      cd "$HOME/project" \
        && (git checkout "${data.coder_parameter.branch.value}" 2>/dev/null \
            || git checkout -b "${data.coder_parameter.branch.value}")
    fi
    # 5) Serve the editor on the project.
    code-server --auth none --port 13337 --host 0.0.0.0 "$HOME/project" \
      >/tmp/code-server.log 2>&1 &
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

resource "docker_image" "main" {
  name = "codercom/enterprise-base:ubuntu"
}

resource "docker_container" "workspace" {
  count      = data.coder_workspace.me.start_count
  image      = docker_image.main.name
  name       = "coder-${data.coder_workspace_owner.me.name}-${lower(data.coder_workspace.me.name)}"
  hostname   = data.coder_workspace.me.name
  entrypoint = ["sh", "-c", coder_agent.main.init_script]
  env        = ["CODER_AGENT_TOKEN=${coder_agent.main.token}"]
  host {
    host = "host.docker.internal"
    ip   = "host-gateway"
  }
}
