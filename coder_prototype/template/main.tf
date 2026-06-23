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

resource "coder_agent" "main" {
  arch           = "amd64"
  os             = "linux"
  startup_script = <<-EOT
    set -e
    if ! command -v code-server >/dev/null 2>&1; then
      curl -fsSL https://code-server.dev/install.sh | sh
    fi
    code-server --auth none --port 13337 --host 0.0.0.0 >/tmp/code-server.log 2>&1 &
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
