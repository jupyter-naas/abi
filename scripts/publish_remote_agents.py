from src.__modules__ import get_modules
from abi import logger
from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
    NaasIntegration,
    NaasIntegrationConfiguration,
)
from src.marketplace.modules.applications.github.integrations.GitHubIntegration import (
    GitHubIntegration,
    GitHubIntegrationConfiguration,
)
from src import load_modules, config
from fastapi import APIRouter

def publish_remote_agent(
    naas_api_key: str, 
    api_base_url: str, 
    abi_api_key: str,
    workspace_id: str,
    github_access_token: str,
    github_repository: str,
    default_agent: str = "Abi",
    agents_to_publish: list[str] = [],
    exclude_agents: list[str] = [],
    auto_publish_enabled: bool = False,
    dry_run: bool = False
    ):
    # Add dry-run header
    if dry_run:
        logger.info("🧪 DRY RUN MODE - No changes will be made")
        logger.info("=" * 50)
    
    # Init Naas Integration
    naas_integration = NaasIntegration(NaasIntegrationConfiguration(api_key=naas_api_key))
    logger.info(f"🔍 Getting existing plugins from workspace: {workspace_id}")
    
    if dry_run:
        logger.info("🧪 [DRY RUN] Would fetch existing plugins from workspace")
        existing_plugins = []  # Skip actual API call in dry run
    else:
        existing_plugins = naas_integration.get_plugins(workspace_id).get("workspace_plugins", [])

    # Init Github Integration
    if github_access_token is not None and github_repository is not None:
        if dry_run:
            logger.info(f"🧪 [DRY RUN] Would update \"ABI_API_KEY\" secret in Github repository: {github_repository}")
        else:
            try:
                github_integration = GitHubIntegration(GitHubIntegrationConfiguration(access_token=github_access_token))
                logger.info(f"🔑 Updating \"ABI_API_KEY\" secret in Github repository: {github_repository}")
                github_integration.create_or_update_repository_secret(
                    repo_name=github_repository,
                        secret_name="ABI_API_KEY",
                        value=abi_api_key
                )
            except Exception as e:
                logger.error(f"❌ Error updating \"ABI_API_KEY\" secret in Github repository: {github_repository}")
                logger.error(f"❌ Error: {e}")

    # Get all agents from the modules
    load_modules()
    modules = get_modules(config)
    for module in modules:
        logger.info(f"=> Getting agents from module: {module.module_path}")
        if "core" in module.module_path:
            agent_type = "CORE"
        elif "custom" in module.module_path:
            agent_type = "CUSTOM"
        elif "domains" in module.module_path:
            agent_type = "DOMAIN"
        # elif "applications" in module.module_path:
        #     agent_type = "APPLICATION"
        else:
            agent_type = "CUSTOM"
        for agent in module.agents:
            name = getattr(agent, "name", "")
            
            # Filter agents based on configuration
            if auto_publish_enabled:
                # When auto-publish is enabled, publish all agents except excluded ones
                if name in exclude_agents:
                    if dry_run:
                        logger.info(f"🧪 [DRY RUN] Would skip excluded agent: {name}")
                    else:
                        logger.info(f"==> Skipping excluded agent: {name}")
                    continue
            else:
                # Legacy behavior: only publish specified agents
                if len(agents_to_publish) > 0 and name not in agents_to_publish:
                    continue
            
            if dry_run:
                logger.info(f"🧪 [DRY RUN] Would publish agent: {name}")
            else:
                logger.info(f"==> Publishing agent: {name}")
            
            # Get SUGGESTIONS and AVATAR_URL from the module
            module_name = agent.__class__.__module__
            module_obj = __import__(module_name, fromlist=['SUGGESTIONS', 'AVATAR_URL'])
            suggestions = getattr(module_obj, 'SUGGESTIONS', [])
            avatar = getattr(module_obj, 'AVATAR_URL', 'https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png')

            # Get name, description, chat_model from the agent
            if name == default_agent:
                default = True
            else:
                default = False
            description = getattr(agent, "description", "")
            model = "gpt-4o"
            temperature = 0
            agent_configuration = getattr(agent, "configuration")
            if agent_configuration is not None:
                prompt = agent_configuration.system_prompt
            else:
                prompt = ""
            as_api = getattr(agent, "as_api", None)
            route_name = None
            if as_api is not None:
                # Get the index of 'route_name' in co_varnames tuple
                try:
                    router = APIRouter()
                    as_api(router)
                    
                    for route in router.routes:
                        if route.path.endswith("/stream-completion"):
                            route_name = route.path.replace("/stream-completion", "")
                            break
                except (ValueError, AttributeError):
                    route_name = name
                    
            if route_name is None:
                raise ValueError(f"Route name not found for agent {name}")
            
            # Remove double slashes in route_name
            route_name = f"agents/{route_name}/stream-completion?token={abi_api_key}".replace("//", "/")

            # Create a slug from the name
            slug = name.lower().replace(" ", "-").replace("_", "-")
            
            # Create plugin data
            plugin_data = {
                "id": slug,
                "name": name.replace("_", " "),
                "slug": slug,
                "default": default,
                "avatar": avatar,
                "description": description,
                "prompt": prompt,
                "prompt_type": "system",
                "model": model,
                "temperature": temperature,
                "type": agent_type,
                "remote": {
                    "url": f"{api_base_url}/{route_name}"
                },
                "suggestions": suggestions,
            }
            
            if dry_run:
                logger.info(f"🧪 [DRY RUN] Plugin data for '{name}':")
                logger.info(f"    - ID: {plugin_data['id']}")
                logger.info(f"    - Name: {plugin_data['name']}")
                logger.info(f"    - Type: {plugin_data['type']}")
                logger.info(f"    - Default: {plugin_data['default']}")
                logger.info(f"    - Remote URL: {plugin_data['remote']['url']}")
                logger.info(f"    - Avatar: {plugin_data['avatar']}")
                logger.info(f"    - Description: {plugin_data['description'][:100]}{'...' if len(plugin_data['description']) > 100 else ''}")
                if plugin_data['suggestions']:
                    logger.info(f"    - Suggestions: {len(plugin_data['suggestions'])} items")
                
                # Simulate checking for existing plugin
                logger.info(f"🧪 [DRY RUN] Would check if plugin '{plugin_data['id']}' already exists")
                logger.info(f"🧪 [DRY RUN] Would create/update plugin in workspace '{config.workspace_id}'")
            else:
                logger.debug(f"==> plugin_data: {plugin_data}")

                # Check if plugin already exists
                existing_plugin_id = naas_integration.search_plugin(
                    key="id", value=plugin_data["id"], plugins=existing_plugins
                )
                if existing_plugin_id:
                    naas_integration.update_plugin(
                        workspace_id=config.workspace_id,
                        plugin_id=existing_plugin_id,
                        data=plugin_data,
                    )
                    message = f"✅ Plugin '{plugin_data['name']}' updated in workspace '{config.workspace_id}'"
                else:
                    naas_integration.create_plugin(
                        workspace_id=config.workspace_id, data=plugin_data
                    )
                    message = f"✅ Plugin '{plugin_data['name']}' created in workspace '{config.workspace_id}'"
                logger.info(message)

if __name__ == "__main__":
    import sys
    from src import secret, config
    
    # Check for dry-run flag
    dry_run = "--dry-run" in sys.argv or "--dryrun" in sys.argv or "-n" in sys.argv
    
    naas_api_key = secret.get("NAAS_API_KEY")
    api_base_url = f"https://{config.space_name}-api.default.space.naas.ai"
    abi_api_key = secret.get("ABI_API_KEY")
    workspace_id = config.workspace_id
    github_access_token = secret.get("GITHUB_ACCESS_TOKEN")
    github_repository = config.github_project_repository
    
    # Get auto-publish configuration
    auto_publish_config = getattr(config, 'auto_publish', {})
    auto_publish_enabled = auto_publish_config.get('enabled', False)
    exclude_agents = auto_publish_config.get('exclude_agents', [])
    default_agent = auto_publish_config.get('default_agent', "Abi")
    
    # Legacy support for manual agent selection (when auto-publish is disabled)
    agents_to_publish = []
    if not auto_publish_enabled:
        # Default agents when auto-publish is disabled (backward compatibility)
        agents_to_publish = ["Abi", "Ontology", "Naas", "Multi_Models", "Support"]
    
    # In dry-run mode, relax the API key requirements
    if not dry_run and (naas_api_key is None or api_base_url is None or abi_api_key is None or workspace_id is None):
        raise ValueError("NAAS_API_KEY, API_BASE_URL, ABI_API_KEY, WORKSPACE_ID must be set")
    
    # Set dummy values for dry-run if missing
    if dry_run:
        naas_api_key = naas_api_key or "dummy_naas_api_key"
        abi_api_key = abi_api_key or "dummy_abi_api_key"
        workspace_id = workspace_id or "dummy_workspace_id"
        github_access_token = github_access_token or "dummy_github_token"
        github_repository = github_repository or "dummy_repo"
    
    logger.info(f"🚀 Auto-publish enabled: {auto_publish_enabled}")
    if auto_publish_enabled:
        logger.info(f"🚫 Excluded agents: {exclude_agents if exclude_agents else 'None'}")
    else:
        logger.info(f"📝 Publishing specific agents: {agents_to_publish}")
    logger.info(f"⭐ Default agent: {default_agent}")
    logger.info(f"🌐 API Base URL: {api_base_url}")
    logger.info(f"🏢 Workspace ID: {workspace_id}")
    
    if dry_run:
        logger.info("🧪 DRY RUN MODE: No actual changes will be made")
    
    publish_remote_agent(
        naas_api_key, 
        api_base_url, 
        abi_api_key, 
        workspace_id, 
        github_access_token, 
        github_repository, 
        default_agent, 
        agents_to_publish,
        exclude_agents,
        auto_publish_enabled,
        dry_run
    )