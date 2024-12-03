import os
import openai
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
import shutil
import yaml
import json

# Initialize console
console = Console()

def check_api_key():
    """Verify OpenAI API key is properly set."""
    try:
        # Directly read the .env file
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    break
            else:
                console.print("[bold red]Error: OPENAI_API_KEY not found in .env file[/bold red]")
                return None
        
        console.print(f"[green]Found API key starting with: {api_key[:10]}...[/green]")
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=api_key)
        
        # Test the connection
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        
        console.print("[green]✓ API key validated successfully[/green]")
        return client
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return None

def read_yaml_file(file_path):
    """Read and parse YAML file."""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not read {file_path}: {str(e)}[/yellow]")
        return {}

def analyze_repository(repo_root):
    """Analyze repository to gather system context."""
    context = {
        "integrations": read_yaml_file(repo_root / "integrations" / "integrations.yaml"),
        "config": read_yaml_file(repo_root / "config.yaml"),
        "data_sources": read_yaml_file(repo_root / "data" / "data_sources.yaml")
    }
    return context

def generate_section_content(client, section_name, context, template):
    """Generate content for a specific section using OpenAI."""
    try:
        prompt = f"""
        Generate detailed content for the {section_name} section of an Organizational AI System document.
        
        Context about the system:
        {json.dumps(context, indent=2)}
        
        Section template:
        {template}
        
        Requirements:
        1. Follow the exact structure provided in the template
        2. Use specific details from the context provided
        3. Be practical and implementation-focused
        4. Include relevant examples where appropriate
        5. Use markdown formatting for better readability
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI system architecture expert creating documentation for an organizational AI system. Provide detailed, practical content following the given template."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        console.print(f"[red]Error generating {section_name}: {str(e)}[/red]")
        return f"# {section_name}\n\nContent generation failed. Please try again."

def get_section_templates():
    """Define templates for each section."""
    return {
        "executive_summary": """
### Purpose
- Define the objective of the AI system
- Expected outcomes and benefits

### Scope
- Focus areas (automation, analytics, etc.)
- System boundaries and limitations

### Vision
- Alignment with organizational strategy
- Long-term goals and impact
""",
        "organizational_context": """
### Mission & Goals
- Organization's mission
- How AI system supports goals

### Current State Analysis
- Existing systems and workflows
- Data landscape overview
- Key challenges to address

### Stakeholders
- Key stakeholders and roles
- Needs and expectations
""",
        # Add templates for other sections...
    }

def create_docs_structure(client, repo_root):
    """Create the complete documentation structure."""
    context = analyze_repository(repo_root)
    templates = get_section_templates()
    
    sections = {
        "1_executive_summary": "Executive Summary",
        "2_organizational_context": "Organizational Context",
        "3_system_architecture": "System Architecture",
        "4_use_cases": "Use Cases",
        "5_data_strategy": "Data Strategy",
        "6_ai_models": "AI Models",
        "7_security_compliance": "Security & Compliance",
        "8_operational_plan": "Operational Plan",
        "9_ethical_ai_framework": "Ethical AI Framework",
        "10_success_metrics": "Success Metrics",
        "11_scalability_roadmap": "Scalability & Future Roadmap",
        "12_appendix": "Appendix"
    }
    
    docs_content = {}
    for section_id, section_name in sections.items():
        console.print(f"Generating content for: [blue]{section_name}[/blue]")
        template = templates.get(section_id.split('_', 1)[1], "")
        content = generate_section_content(client, section_name, context, template)
        docs_content[section_id] = {
            "title": section_name,
            "content": content
        }
    
    return docs_content

def write_documentation(docs_content, docs_path):
    """Write the documentation files."""
    docs_path.mkdir(exist_ok=True)
    
    # Create main README
    index_content = "# Organizational AI System Documentation\n\n"
    index_content += "## Table of Contents\n\n"
    
    for section_id, section in docs_content.items():
        # Add to index
        index_content += f"- [{section['title']}]({section_id}.md)\n"
        
        # Create section file
        section_content = f"# {section['title']}\n\n{section['content']}"
        with open(docs_path / f"{section_id}.md", 'w', encoding='utf-8') as f:
            f.write(section_content)
    
    # Write index
    with open(docs_path / "README.md", 'w', encoding='utf-8') as f:
        f.write(index_content)

def main():
    console.print("[bold blue]Starting OAS documentation generation...[/bold blue]")
    
    # Check for .env file
    if not Path('.env').exists():
        console.print("[bold red]Error: .env file not found[/bold red]")
        return
    
    # Initialize OpenAI client
    client = check_api_key()
    if not client:
        return
    
    # Setup paths
    repo_root = Path(__file__).parent.parent
    docs_path = repo_root / "docs"
    
    # Clean existing docs
    if docs_path.exists():
        shutil.rmtree(docs_path)
    
    try:
        # Generate documentation content
        docs_content = create_docs_structure(client, repo_root)
        
        # Write documentation files
        write_documentation(docs_content, docs_path)
        
        console.print("[bold green]Documentation generation complete![/bold green]")
        console.print(f"Documentation has been generated in the [bold]docs/[/bold] directory")
        
    except Exception as e:
        console.print(f"[bold red]Error generating documentation: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()