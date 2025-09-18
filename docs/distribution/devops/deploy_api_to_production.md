# Deploy API to Production

This document describes the process of deploying the API to production using NAAS spaces, which is a managed Kubernetes-based service provided by NAAS.

## About NAAS Spaces

NAAS Spaces is a hosted service built on top of Kubernetes with Knative, allowing you to deploy containerized applications without managing the underlying infrastructure. The system:
- Uses AWS Kubernetes clusters with Knative
- Provides a custom API gateway
- Integrates with AWS ECR for container registry storage
- Automates deployment through GitHub Actions

## Setup Requirements

1. **Create a GitHub Classic Personal Access Token**:
   - Go to GitHub Settings > Developer Settings > Personal Access Tokens > Tokens (classic)
   - Generate a new token with the following permissions:
     - `repo` (Full control of private repositories)
     - `read:packages` and `write:packages` (For container registry access)
   - Copy the token value

2. **Get required API keys**:
   - OpenAI API key from [OpenAI Platform](https://platform.openai.com/api-keys)
   - NAAS Credentials JWT Token from your NAAS account

3. **Navigate to your repository's Settings > Secrets and variables > Actions and add the following secrets**:
   - `ACCESS_TOKEN`: Your GitHub Classic Personal Access Token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `NAAS_CREDENTIALS_JWT_TOKEN`: Your NAAS Credentials JWT Token (used to authenticate with NAAS services)
   - `ABI_API_KEY`: Your key to access the API

## Deployment Pipeline

The deployment process is fully automated through GitHub Actions workflows:

1. **Triggering Deployment**: 
   - Pushing to the `main` or `dev` branch triggers the `release.yml` workflow
   - This uses semantic-release to create a new GitHub release when commits follow conventional commit format

2. **Container Build Process**:
   - When a new release is published, the `build_abi_container.yml` workflow is triggered
   - This builds a Docker container using `docker/images/Dockerfile.linux.x86_64`
   - The container is tagged and pushed to GitHub Container Registry (ghcr.io)

3. **Deployment to NAAS**:
   - After the container build completes, the `deploy_api.yml` workflow is triggered automatically
   - This workflow:
     - Creates a NAAS container registry if it doesn't exist
     - Pulls the latest container from GitHub Container Registry
     - Tags it with a timestamp
     - Pushes it to the NAAS registry (backed by AWS ECR)
     - Creates or updates a NAAS space with environment variables and resource configurations (CPU, memory)

4. **Access the Deployed API**:
   - The API will be accessible at: `https://<github_project_repository.name>-api.default.space.naas.ai/`
   - The deployment uses the following configuration:
     - Port: 9879
     - CPU: 1 core
     - Memory: 1GB

## Manual Deployment

For manual deployment or testing, you can use the commands in the Makefile:
- `make build` - Builds the Docker image locally
- `make api-prod` - Runs the production API container locally

## Monitoring and Debugging

The deployment status can be monitored through:
- GitHub Actions workflow runs in the repository's "Actions" tab
- NAAS platform dashboard (if available)
- Using the NAAS CLI for checking space and registry status:
  ```
  naas-python space list
  naas-python registry list
  ```

## Self-Hosted Deployment

If you prefer to deploy ABI on your own hardware instead of using NAAS spaces, you can follow these instructions to run it on any machine with Docker support.

### Prerequisites

- A machine with Docker installed (any OS - Linux, Windows, or macOS)
- At least 2GB of RAM (4GB recommended)
- At least 1 CPU core (2+ cores recommended for better performance)
- Git to clone the repository

### Option 1: Direct Docker Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/abi.git
   cd abi
   ```

2. **Create a .env file** with required environment variables:
   ```bash
   touch .env
   ```
   
   Add the following to the .env file:
   ```
   OPENAI_API_KEY=your_openai_api_key
   NAAS_API_KEY=your_naas_jwt_token  # Optional if not using NAAS services
   GITHUB_ACCESS_TOKEN=your_github_token  # Optional for GitHub integration features
   ABI_API_KEY=your_api_key
   ENV=prod
   ```

3. **Build the Docker image**:
   ```bash
   make build
   ```
   This builds the container for linux/amd64 architecture.

4. **Run the API in production mode**:
   ```bash
   make api-prod
   ```
   
   Or run the Docker container directly:
   ```bash
   docker run --rm -it -p 9879:9879 --env-file .env abi:latest
   ```

5. **Access the API**:
   The API will be accessible at `http://localhost:9879`

### Option 2: Docker Compose Deployment

For a more maintainable setup, especially on a server:

1. **Create a docker/compose/docker-compose.yml file**:
   ```yaml
   version: '3'
   
   services:
     abi-api:
       image: abi:latest
       build:
         context: .
         dockerfile: docker/images/Dockerfile.linux.x86_64
       restart: unless-stopped
       ports:
         - "9879:9879"
       env_file:
         - .env
       volumes:
         - abi-data:/app/data
       environment:
         - ENV=prod
   
   volumes:
     abi-data:
   ```

2. **Build and start the service**:
   ```bash
   docker compose build
   docker compose up -d
   ```

3. **Check logs**:
   ```bash
   docker compose logs -f
   ```

### Deployment on High-Performance Hardware

For deployment on specialized hardware (e.g., GPU machines, DGX stations):

1. **GPU Support**: If your machine has GPUs that you want to make available to the container:
   
   Add to your docker/compose/docker-compose.yml:
   ```yaml
   services:
     abi-api:
       # ... other configurations
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: all
                 capabilities: [gpu]
   ```

2. **Multiple CPU cores**: For dual SCC2 or multi-core machines, you may want to adjust container resource limits:

   ```yaml
   services:
     abi-api:
       # ... other configurations
       deploy:
         resources:
           limits:
             cpus: '8'
             memory: 16G
   ```

### Production Considerations

1. **Setting up a reverse proxy**:
   For proper HTTPS support, consider using Nginx or Traefik as a reverse proxy in front of the API.

2. **Monitoring**:
   Add a monitoring solution like Prometheus with Grafana, or a simpler solution like Netdata.

3. **Automatic updates**:
   Consider setting up a CI/CD pipeline or cron job to pull the latest image from GitHub Container Registry:
   
   ```bash
   docker pull ghcr.io/your-organization/abi:latest
   docker tag ghcr.io/your-organization/abi:latest abi:latest
   docker compose restart
   ```

4. **Backup strategy**:
   Regularly backup any persistent data stored in the container volumes.