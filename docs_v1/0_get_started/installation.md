# Installation

Get started with ABI - Install, configure and chat with your first agent.

## Prerequisites

- **Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)**
- **Create your account on [NAAS](https://naas.ai)** (Optional, only if you want to use the storage system in production)

## Set Up Repository

### For Individual

1. **Clone the Repository**
```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

2. **Fork the Repository**
```bash
# 1. Fork via GitHub UI
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

### For Enterprise

**Create a Private Fork**
```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

## Environment Setup

1. Copy this file to .env
```bash
cp .env.example .env
```
2. Replace placeholder values with your actual credentials
3. Uncomment (remove #) from lines you want to activate. The variables are used to configure the assistant.

Note: The .env file should never be committed to version control
as it contains sensitive credentials

## Configure YAML

1. Copy the example file to config.yaml
```bash
cp config.yaml.example config.yaml
```

2. Edit the file with your configuration:
- `workspace_id`: Workspace ID in Naas Platform. It will be used for storage and publishing modules components. Access it from this [link](https://naas.ai/account/settings)
- `github_project_repository`: Your Github repository name (e.g. "jupyter-naas/abi"). It will be used in documentation and API as registry name.
- `github_support_repository`: A Github repository name (e.g. "jupyter-naas/abi") to store support issues. It will be used by the support agent to create all requests or report bugs. It can be the same as `github_project_repository`.
- `github_project_id`: Your Github project number stored in Github URL (e.g. 12 for https://github.com/jupyter-naas/abi/projects/12). It will be used to assign all your issues to your github project.
- `triple_store_path`: Path to the ontology store (e.g. "storage/triplestore")
- `api_title`: API title (e.g. "ABI API") displayed in the documentation.
- `api_description`: API description (e.g. "API for ABI, your Artifical Business Intelligence") displayed in the documentation.
- `logo_path`: Path to the logo (e.g. "assets/logo.png") used in the API documentation.
- `favicon_path`: Path to the favicon (e.g. "assets/favicon.ico") used in the API documentation.
- `storage_name`: Name of the storage (e.g. "abi")
- `space_name`: Name of the space (e.g. "abi")