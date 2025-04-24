### Deploy API

One of the main features of ABI is the ability to deploy an Agentic Based API.

The API deployment is automated through GitHub Actions. Every time you push to the main branch with last commit message as `feat:` or `fix:`, the API will be deployed as follow:

1. A new container is built (via the "Build ABI Container" workflow)
2. The deployment workflow creates/updates a NAAS space with the latest container image
3. The API will be accessible through the NAAS platform once deployment is complete as the following URL: `https://<github_project_repository.name>-api.default.space.naas.ai/`

#### Local Development

To run the API locally for testing:

```bash
make api
```

This will start the API server on `http://localhost:9879`.

To see all available make commands:

```bash
make
```

This will display the help menu with all available commands and their descriptions.

#### Setup Requirements

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
   - `NAAS_CREDENTIALS_JWT_TOKEN`: Your NAAS Credentials JWT Token
   - `ABI_API_KEY`: Your key to access the API

#### Monitoring

- Go to your repository's Actions tab
- Look for the "ABI API" workflow
- Check the latest workflow run for deployment status and logs
