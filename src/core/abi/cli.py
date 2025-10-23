"""
ABI CLI Commands Module

This module provides command-line interface commands for creating new modules and agents.
"""

import os
import shutil
import re
from rich.console import Console
from rich.prompt import Prompt
import yaml
import dotenv

console = Console(style="")

def format_module_name(name: str) -> str:
    """Format module name to lowercase with proper formatting."""
    # Convert to lowercase
    formatted = name.lower()
    # Replace spaces with underscores
    formatted = formatted.replace(' ', '_')
    # Replace dots with underscores
    formatted = formatted.replace('.', '_')
    # Remove any other special characters except letters, numbers, and underscores
    formatted = re.sub(r'[^a-z0-9_]', '', formatted)
    # Remove multiple consecutive underscores
    formatted = re.sub(r'_+', '_', formatted)
    # Remove leading/trailing underscores
    formatted = formatted.strip('_')
    return formatted

def get_component_selection():
    """Get user selection for which components to include in the module."""
    console.print("\n🔧 Which components would you like to include?\n", style="bright_blue")
    
    # List all available components
    console.print("Available components:", style="cyan")
    component_descriptions = {
        "agents": "AI agents for conversational interfaces (includes models)",
        "integrations": "External service integrations and API wrappers",
        "workflows": "Business logic workflows and processes",
        "pipelines": "Data processing and transformation pipelines",
        "ontologies": "Semantic ontologies and SPARQL queries",
        "orchestrations": "Dagster orchestration definitions"
    }
    
    for component, description in component_descriptions.items():
        console.print(f"• {component}: {description}", style="dim")
    
    console.print()  # Empty line for spacing
    
    # Ask if they want all components
    include_all = Prompt.ask("Include all template components?", choices=["y", "n"], default="y")
    
    if include_all == "y":
        return {
            "agents": True,
            "integrations": True,
            "workflows": True,
            "pipelines": True,
            "ontologies": True,
            "models": True,
            "orchestrations": True
        }
    
    # Individual component selection
    console.print("Select components to include:", style="cyan")
    components = {}
    
    for component in component_descriptions.keys():
        choice = Prompt.ask(f"Include {component}?", choices=["y", "n"], default="y")
        components[component] = choice == "y"
    
    # Models are automatically included if agents are selected
    components["models"] = components.get("agents", False)
    
    if components.get("agents", False):
        console.print("📝 Models component automatically included (required for agents)", style="yellow")
    
    return components

def enable_module_in_config(module_path: str):
    """Enable the module in config files if they exist."""
    dotenv.load_dotenv()
    
    env = os.getenv("ENV")

    config_files = [f"config.{env}.yaml"]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                console.print(f"📝 Updating {config_file}...", style="yellow")
                
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                # Ensure modules section exists
                if 'modules' not in config:
                    config['modules'] = []
                
                # Check if module already exists
                module_exists = False
                for module in config['modules']:
                    if module.get('path') == module_path:
                        module['enabled'] = True
                        module_exists = True
                        break
                
                # Add module if it doesn't exist
                if not module_exists:
                    config['modules'].append({
                        'path': module_path,
                        'enabled': True
                    })
                
                # Sort modules by path for consistency
                config['modules'] = sorted(config['modules'], key=lambda x: x.get('path', ''))
                
                with open(config_file, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                
                console.print(f"✅ Module enabled in {config_file}", style="green")
                
            except Exception as e:
                console.print(f"⚠️ Could not update {config_file}: {e}", style="yellow")

def create_new_module():
    """Create a new module by duplicating the __templates__ folder."""
    console.print("🚀 Creating a new module...\n", style="bright_cyan")
    
    # Get module name and validate format
    while True:
        raw_module_name = Prompt.ask("What is the module name?")
        if not raw_module_name.strip():
            console.print("❌ Module name cannot be empty.", style="red")
            continue
            
        module_name = format_module_name(raw_module_name)
        if not module_name or not re.match(r'^[a-z][a-z0-9_\-\.]*$', module_name):
            console.print("❌ Invalid module name. Must start with a lowercase letter and can contain letters, numbers, underscores, dots, or hyphens.", style="red")
            continue
            
        if raw_module_name != module_name:
            console.print(f"📝 Module name formatted as: {module_name}", style="yellow")
        break
    
    # Get target path with explanations
    console.print("\nWhere would you like to create this module?\n", style="bright_blue")
    console.print("1. src/core - Core ABI functionality and essential modules", style="cyan")
    console.print("   • Built-in ABI features", style="dim")
    console.print("   • System-level integrations", style="dim")
    console.print("   • Foundation components\n", style="dim")
    
    console.print("2. src/custom - Organization-specific implementations", style="cyan")
    console.print("   • Company-specific adaptations", style="dim")
    console.print("   • Private customizations", style="dim")
    console.print("   • Internal tools and workflows\n", style="dim")
    
    console.print("3. src/marketplace/applications - Third-party service integrations", style="cyan")
    console.print("   • External API integrations", style="dim")
    console.print("   • SaaS platform connectors", style="dim")
    console.print("   • Public service wrappers\n", style="dim")
    
    console.print("4. src/marketplace/domains - Business domain specialists", style="cyan")
    console.print("   • Role-based agents (HR, Sales, etc.)", style="dim")
    console.print("   • Industry-specific solutions", style="dim")
    console.print("   • Professional domain experts\n", style="dim")
    
    path_choice = Prompt.ask("Choose location", choices=["1", "2", "3", "4"], default="1")
    
    path_mapping = {
        "1": "src/core",
        "2": "src/custom", 
        "3": "src/marketplace/applications",
        "4": "src/marketplace/domains"
    }
    
    target_base_path = path_mapping[path_choice]
    target_path = os.path.join(target_base_path, module_name)
    
    # Check if target path already exists
    if os.path.exists(target_path):
        console.print(f"❌ Module already exists at {target_path}", style="red")
        return
    
    # Get component selection
    selected_components = get_component_selection()
    
    # Create the module directory
    console.print(f"\n📁 Creating module at {target_path}...", style="green")
    
    try:
        # Create base module directory
        os.makedirs(target_path, exist_ok=True)
        
        # Copy selected components from template
        template_path = "src/core/__templates__"
        
        # Always copy base files
        base_files = ["__init__.py", "README.md"]
        for file in base_files:
            source_file = os.path.join(template_path, file)
            if os.path.exists(source_file):
                target_file = os.path.join(target_path, file)
                shutil.copy2(source_file, target_file)
        
        # Copy selected component directories
        for component, include in selected_components.items():
            if include:
                source_component_path = os.path.join(template_path, component)
                target_component_path = os.path.join(target_path, component)
                
                if os.path.exists(source_component_path):
                    console.print(f"📦 Adding {component} component...", style="dim")
                    shutil.copytree(source_component_path, target_component_path)
        
        # Update all file contents with module name replacements
        console.print("🔄 Updating template references...", style="yellow")
        
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith(('.py', '.md', '.ttl')):
                    file_path = os.path.join(root, file)
                    
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Replace template references
                    content = content.replace('Template', module_name.replace('_', '').title())
                    content = content.replace(template_path.replace('\\', '/').replace('/', '.'), target_path.replace('\\', '/').replace('/', '.'))
                    content = content.replace('__templates__', module_name)
                    content = content.replace('template', module_name.replace('_', '').lower())
                    
                    # Update path references
                    old_path_pattern = "src/core/__templates__"
                    new_path_pattern = target_path.replace('\\', '/')
                    content = content.replace(old_path_pattern, new_path_pattern)
                    
                    # Write updated content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
        
        # Rename files that contain "Template" in their names
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if 'Template' in file:
                    old_file_path = os.path.join(root, file)
                    new_file_name = file.replace('Template', module_name.replace('_', '').title())
                    new_file_path = os.path.join(root, new_file_name)
                    os.rename(old_file_path, new_file_path)
        
        # Enable module in config files
        module_config_path = target_path.replace('\\', '/')
        enable_module_in_config(module_config_path)
        
        console.print(f"✅ Module '{module_name}' created successfully at {target_path}", style="bright_green")
        
        # Show what was included
        included_components = [comp for comp, include in selected_components.items() if include]
        if included_components:
            console.print(f"\n📦 Included components: {', '.join(included_components)}", style="cyan")
        
        console.print("\n📝 Next steps:", style="bright_blue")
        console.print(f"1. Edit {target_path}/README.md to describe your module", style="dim")
        console.print(f"2. Configure your module requirements in {target_path}/__init__.py", style="dim")
        console.print("3. Implement your components based on the templates", style="dim")
        console.print("4. Module has been automatically enabled in config files", style="dim")
        
    except Exception as e:
        console.print(f"❌ Error creating module: {e}", style="red")
        # Clean up partial creation
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

def create_agent():
    """Create a new agent by duplicating TemplateAgent files."""
    console.print("🤖 Creating a new agent...\n", style="bright_cyan")
    
    # Get agent name
    while True:
        agent_name = Prompt.ask("What is the agent name?")
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', agent_name):
            break
        console.print("❌ Invalid agent name. Use only letters, numbers, and underscores. Must start with a letter.", style="red")
    
    # Get target path
    target_path = Prompt.ask("Where should the agent be created? (e.g., src/core/mymodule/agents)")
    
    # Validate path exists
    if not os.path.exists(target_path):
        create_path = Prompt.ask(f"Path {target_path} doesn't exist. Create it?", choices=["y", "n"], default="y")
        if create_path == "y":
            try:
                os.makedirs(target_path, exist_ok=True)
                console.print(f"📁 Created directory {target_path}", style="green")
            except Exception as e:
                console.print(f"❌ Error creating directory: {e}", style="red")
                return
        else:
            console.print("❌ Agent creation cancelled", style="red")
            return
    
    # Define source and target files
    template_agent_file = "src/core/__templates__/agents/TemplateAgent.py"
    template_test_file = "src/core/__templates__/agents/TemplateAgent_test.py"
    
    target_agent_file = os.path.join(target_path, f"{agent_name}Agent.py")
    target_test_file = os.path.join(target_path, f"{agent_name}Agent_test.py")
    
    # Check if files already exist
    if os.path.exists(target_agent_file) or os.path.exists(target_test_file):
        console.print(f"❌ Agent files already exist at {target_path}", style="red")
        return
    
    try:
        console.print(f"📝 Creating {agent_name}Agent.py...", style="yellow")
        
        # Copy and update agent file
        with open(template_agent_file, 'r', encoding='utf-8') as f:
            agent_content = f.read()
        
        # Replace Template with agent name
        agent_content = agent_content.replace('Template', agent_name)
        agent_content = agent_content.replace('template', agent_name.lower())
        
        # Update import paths if needed
        relative_path = os.path.relpath(target_path, "src").replace('\\', '/').replace('/', '.')
        module_path = relative_path.replace(".agents", "")
        
        if relative_path != "core.__templates__.agents":
            agent_content = agent_content.replace(
                'from src.core.__templates__.models.gpt_4_1 import model as cloud_model',
                f'from src.{module_path}.models.gpt_4_1 import model as cloud_model'
            )
            agent_content = agent_content.replace(
                'from src.core.__templates__.models.qwen3_8b import model as local_model',
                f'from src.{module_path}.models.qwen3_8b import model as local_model'
            )
        
        with open(target_agent_file, 'w', encoding='utf-8') as f:
            f.write(agent_content)
        
        console.print(f"📝 Creating {agent_name}Agent_test.py...", style="yellow")
        
        # Copy and update test file
        with open(template_test_file, 'r', encoding='utf-8') as f:
            test_content = f.read()
        
        # Replace Template with agent name and update import path
        test_content = test_content.replace('Template', agent_name)
        test_content = test_content.replace('template', agent_name.lower())
        
        # Update import path
        import_path = f"src.{relative_path}.{agent_name}Agent"
        test_content = test_content.replace(
            'from src.core.__templates__.agents.TemplateAgent import create_agent',
            f'from {import_path} import create_agent'
        )
        
        with open(target_test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        # Check if models folder exists in the module, if not, create it
        module_root_path = os.path.dirname(target_path)  # Get parent directory (module root)
        models_target_path = os.path.join(module_root_path, "models")
        
        if not os.path.exists(models_target_path):
            console.print("📦 Creating models folder (required for agents)...", style="yellow")
            
            # Copy models from template
            template_models_path = "src/core/__templates__/models"
            if os.path.exists(template_models_path):
                shutil.copytree(template_models_path, models_target_path)
                
                # Update model files with module name
                for root, dirs, files in os.walk(models_target_path):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Replace template references in model files
                            content = content.replace('__templates__', module_path.split('.')[-1])
                            content = content.replace('Template', agent_name)
                            content = content.replace('template', agent_name.lower())
                            
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                
                console.print(f"✅ Models folder created at {models_target_path}", style="green")
            else:
                console.print(f"⚠️ Template models folder not found at {template_models_path}", style="yellow")
        else:
            console.print(f"📦 Models folder already exists at {models_target_path}", style="dim")
        
        console.print(f"✅ Agent '{agent_name}Agent' created successfully!", style="bright_green")
        console.print("\n📝 Files created:", style="bright_blue")
        console.print(f"• {target_agent_file}", style="dim")
        console.print(f"• {target_test_file}", style="dim")
        if os.path.exists(models_target_path):
            console.print(f"• {models_target_path}/ (models folder)", style="dim")
        console.print("\n📝 Next steps:", style="bright_blue")
        console.print("1. Edit the agent's SYSTEM_PROMPT and capabilities", style="dim")
        console.print("2. Configure the agent's tools and intents", style="dim")
        console.print(f"3. Test your agent: uv run python -m pytest {target_test_file}", style="dim")
        console.print(f"4. Run your agent: make chat agent={agent_name}Agent", style="dim")
        
    except Exception as e:
        console.print(f"❌ Error creating agent: {e}", style="red")
        # Clean up partial creation
        for file_path in [target_agent_file, target_test_file]:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Clean up models folder if it was created during this operation
        module_root_path = os.path.dirname(target_path)
        models_target_path = os.path.join(module_root_path, "models")
        if os.path.exists(models_target_path):
            # Only remove if it's empty or was just created
            try:
                if not os.listdir(models_target_path):  # Empty directory
                    os.rmdir(models_target_path)
            except Exception:
                pass  # Don't fail if we can't clean up models folder

def create_component(component_type: str, template_files: list[str], file_suffix: str):
    """Generic function to create components (integration, workflow, pipeline, ontology)."""
    console.print(f"🔧 Creating a new {component_type}...\n", style="bright_cyan")
    
    # Get target path first
    target_path = Prompt.ask(f"Where should the {component_type} be created? (e.g., src/core/mymodule/{component_type}s)")
    
    # Validate path exists
    if not os.path.exists(target_path):
        create_path = Prompt.ask(f"Path {target_path} doesn't exist. Create it?", choices=["y", "n"], default="y")
        if create_path == "y":
            try:
                os.makedirs(target_path, exist_ok=True)
                console.print(f"📁 Created directory {target_path}", style="green")
            except Exception as e:
                console.print(f"❌ Error creating directory: {e}", style="red")
                return
        else:
            console.print(f"❌ {component_type.title()} creation cancelled", style="red")
            return
    
    # Get component name
    while True:
        component_name = Prompt.ask(f"What is the {component_type} name?")
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', component_name):
            break
        console.print("❌ Invalid name. Use only letters, numbers, and underscores. Must start with a letter.", style="red")
    
    # Define source and target files
    source_files = [f"src/core/__templates__/{component_type}s/{template_file}" for template_file in template_files]
    target_files = []
    
    for template_file in template_files:
        if template_file.endswith('.py'):
            target_file = os.path.join(target_path, template_file.replace('Template', component_name))
        else:  # For .ttl files
            target_file = os.path.join(target_path, template_file.replace('Template', component_name))
        target_files.append(target_file)
    
    # Check if files already exist
    if any(os.path.exists(target_file) for target_file in target_files):
        console.print(f"❌ {component_type.title()} files already exist at {target_path}", style="red")
        return
    
    try:
        for i, (source_file, target_file) in enumerate(zip(source_files, target_files)):
            console.print(f"📝 Creating {os.path.basename(target_file)}...", style="yellow")
            
            # Copy and update file
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace Template with component name
            content = content.replace('Template', component_name)
            content = content.replace('template', component_name.lower())
            
            # Update import paths if needed (for Python files)
            if target_file.endswith('.py'):
                relative_path = os.path.relpath(target_path, "src").replace('\\', '/').replace('/', '.')
                if relative_path != f"core.__templates__.{component_type}s":
                    # Update integration imports
                    content = content.replace(
                        'from src.core.__templates__.integrations.TemplateIntegration import',
                        f'from src.{relative_path.replace(f".{component_type}s", "")}.integrations.{component_name}Integration import'
                    )
                    # Update other template references in imports
                    content = re.sub(
                        r'from src\.core\.__templates__\.([^.]+)\.Template([^.]+) import',
                        rf'from src.{relative_path.replace(f".{component_type}s", "")}.\1.{component_name}\2 import',
                        content
                    )
            
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(content)
        
        console.print(f"✅ {component_type.title()} '{component_name}{file_suffix}' created successfully!", style="bright_green")
        console.print("\n📝 Files created:", style="bright_blue")
        for target_file in target_files:
            console.print(f"• {target_file}", style="dim")
        console.print("\n📝 Next steps:", style="bright_blue")
        console.print(f"1. Edit the {component_type}'s configuration and implementation", style="dim")
        console.print("2. Update the class names and methods as needed", style="dim")
        console.print(f"3. Test your {component_type}: uv run python -m pytest {target_files[1] if len(target_files) > 1 else target_files[0]}", style="dim")
        
    except Exception as e:
        console.print(f"❌ Error creating {component_type}: {e}", style="red")
        # Clean up partial creation
        for target_file in target_files:
            if os.path.exists(target_file):
                os.remove(target_file)

def create_integration():
    """Create a new integration by duplicating TemplateIntegration files."""
    create_component(
        component_type="integration",
        template_files=["TemplateIntegration.py", "TemplateIntegration_test.py"],
        file_suffix="Integration"
    )

def create_workflow():
    """Create a new workflow by duplicating TemplateWorkflow files."""
    create_component(
        component_type="workflow",
        template_files=["TemplateWorkflow.py", "TemplateWorkflow_test.py"],
        file_suffix="Workflow"
    )

def create_pipeline():
    """Create a new pipeline by duplicating TemplatePipeline files."""
    create_component(
        component_type="pipeline",
        template_files=["TemplatePipeline.py", "TemplatePipeline_test.py"],
        file_suffix="Pipeline"
    )

def create_ontology():
    """Create a new ontology by duplicating Template ontology files."""
    create_component(
        component_type="ontology",
        template_files=["TemplateOntology.ttl", "TemplateSparqlQueries.ttl"],
        file_suffix="Ontology"
    )

def main():
    """Main CLI entry point for ABI commands."""
    import sys
    
    if len(sys.argv) < 2:
        console.print("❌ Please specify a command:", style="red")
        console.print("Available commands: create-module, create-agent, create-integration, create-workflow, create-pipeline, create-ontology", style="dim")
        return
    
    command = sys.argv[1]
    
    if command == "create-module":
        create_new_module()
    elif command == "create-agent":
        create_agent()
    elif command == "create-integration":
        create_integration()
    elif command == "create-workflow":
        create_workflow()
    elif command == "create-pipeline":
        create_pipeline()
    elif command == "create-ontology":
        create_ontology()
    else:
        console.print(f"❌ Unknown command: {command}", style="red")
        console.print("Available commands: create-module, create-agent, create-integration, create-workflow, create-pipeline, create-ontology", style="dim")

if __name__ == "__main__":
    main()
