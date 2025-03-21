## Getting Started

### Prerequisites

1. **Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)**

### Installation Options

Choose one of the following options:

a. **Clone the Repository** (for personal use)
```bash
git clone https://github.com/jupyter-naas/abi.git
cd abi
```

b. **Fork the Repository** (to contribute changes)
```bash
# 1. Fork via GitHub UI
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/abi.git
cd abi
```

c. **Create a Private Fork** (for private development)
```bash
# 1. Create private repository via GitHub UI
# 2. Clone your private repository
git clone https://github.com/YOUR-USERNAME/abi-private.git
cd abi-private
git remote add upstream https://github.com/jupyter-naas/abi.git
git pull --rebase upstream main
git push
```

### Environment Setup

#### Environment Variables

1. Copy this file to .env
```bash
cp .env.example .env
```
2. Replace placeholder values with your actual credentials
3. Uncomment (remove #) from lines you want to activate. The variables are used to configure the assistant.

Note: The .env file should never be committed to version control
as it contains sensitive credentials

#### Config YAML

1. Copy the example file to config.yaml
```bash
cp config.yaml.example config.yaml
```
2. Edit the file with your configuration
3. The config.yaml file is used to configure your workflows, pipelines and the API: 
- `workspace_id`: Workspace ID linked to all components: assistants, ontologies, pipelines, workflows, etc.
- `github_project_repository`: Your Github repository name (e.g. jupyter-naas/abi). It will be used in documentation and API as registry name.
- `github_support_repository`: A Github repository name (e.g. jupyter-naas/abi) to store support issues. It will be used by the support agent to create all requests or report bugs. It can be the same as `github_project_repository`.
- `github_project_id`: Your Github project number stored in Github URL (e.g. 1 for https://github.com/jupyter-naas/abi/projects/1). It will be used to assign all your issues to your github project.
- `api_title`: API title (e.g. ABI API) displayed in the documentation.
- `api_description`: API description (e.g. API for ABI, your Artifical Business Intelligence) displayed in the documentation.
- `logo_path`: Path to the logo (e.g. assets/logo.png) used in the API documentation.
- `favicon_path`: Path to the favicon (e.g. assets/favicon.ico) used in the API documentation.

### Setup Git Remote

Once you have forked and created your own version of the ABI repository, you need to establish a Git remote. 
This will enable you to push and pull to and from the original ABI repository. Doing so will allow you to update your project with the latest changes, or contribute back to the open-source project.

Execute the following commands in your terminal:

```bash
# Access your repo
cd "your_directory_name"

# Add  remote
git remote add abi https://github.com/jupyter-naas/abi.git

# Push to main branch
git push abi main

# Pull from main branch
git pull abi main

```

**About Git default remote**

When you clone a git repository from Github or any other provider, it will always create a default remote for you, named, `origin`. You might already have asked yourself what this `origin` was. It's your default git remote.

This means that, assuming you are on the `main` branch, executing `git push` is the same as `git push origin main`.

So by default will just use:

- The branch you are actually on
- The `origin` remote. Even if other exists, it will always use `origin` by default.


### Running Python Scripts

To run a Python script, use the `__main__` block pattern in the script file and run by using the command `make sh` and then the script path: `poetry run python src/pipelines/abi/AbiApplicationPipeline.py`

Here is an example of how to run a pipeline in your terminal:

```python
# src/data/pipelines/YourPipeline.py
if __name__ == "__main__":
      from src import secret
      from src.core.modules.common.integrations import YourIntegration
      from abi.services.ontology_store import OntologyStoreService
      
      # Setup dependencies
      integration = YourIntegration(YourIntegrationConfiguration(...))
      ontology_store = OntologyStoreService()
      
      # Create pipeline configuration
      config = YourPipelineConfiguration(
         integration=integration,
         ontology_store=ontology_store
      )
      
      # Initialize and run pipeline
      pipeline = YourPipeline(config)
      result = pipeline.run(YourPipelineParameters(
         parameter_1="test",
         parameter_2=123
      ))
      
      # Print results in Turtle format to verify ontology mapping
      print(result.serialize(format="turtle"))
```

Terminal command:
```bash
poetry run python src/pipelines/YourPipeline.py
```

### Managing Dependencies

If you need to add a new Python dependency to `src` project, you can use the following command:

#### Add a new Python dependency to `src` project

```bash
make add dep=<library-name>
```

This will automatically:
- Add the dependency to your `pyproject.toml`
- Update the `poetry.lock` file
- Install the package in your virtual environment

#### Add a new Python dependency to `lib/abi` project

```bash
make abi-add dep=<library-name>
```

#### Add new secrets

The API will used the secrets stored in your github repository secrets.
If you want to add new secrets, you need to do the following:
1. **Navigate to your repository's Settings > Secrets and variables > Actions and add the new secrets**
2. **Open `.github/workflows/deploy_api.yml**
3. **Add your github secrets in the env section of the**: "Push latest abi container"
4. **Pass the secrets to space environment in `ENV_CONFIG`**
5. **Commit and push your changes**

## Additional Resources

- **lib/abi**: [lib/abi/README.md](lib/README.md)
- **src**: [src/README.md](src/README.md)

## Development Tools

For Cursor users there is the [.cursorrules](.cursorrules) file already configured to help you create new Integrations, Pipelines and Workflows.

More will be added as we add more components to the framework.

## Help & Support
For any questions or support requests, please reach out via [support@naas.ai](mailto:support@naas.ai) or on our [community forum](https://join.slack.com/t/naas-club/shared_invite/zt-2xmz8c3j8-OH3UAqvwsYkTR3BLRHGXeQ) on Slack.