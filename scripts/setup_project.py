import os
import yaml
import sys
import subprocess
from scripts.update_readme import update_readme_structure

def create_directory_structure():
    # Base directories
    directories = [
        'api/assistants/personal',
        'api/assistants/domain',
        'api/assistants/custom',
        'api/assistants/foundation',
        'api/models',
        'api/ontology',
        'api/workflows',
        'api/integrations',
        'api/analytics',
        'api/data',
        'core/db',
        'core/services',
        'core/utils',
        'integrations',
        'models/ml_models',
        'models/generative_ai_models',
        'ontology/definitions',
        'workflows/definitions',
        'data/pipelines',
        'analytics/reports',
        'docs',
        'tests',
        'assets/images',
        'assets/static',
        'assets/templates'
    ]

    # Create directories
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # Create __init__.py in each Python package directory
        if not directory.startswith(('docs', 'tests')):
            open(os.path.join(directory, '__init__.py'), 'a').close()

    # Create base files
    files = {
        'Dockerfile': 'FROM python:3.9\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "4242"]',
        'docker-compose.yml': '''version: '3.8'
services:
  web:
    build: .
    ports:
      - "4242:4242"
    volumes:
      - .:/app
    environment:
      - ENV=development''',
        '.env.example': '''DATABASE_URL=postgresql://user:password@localhost:5432/db
API_KEY=your_api_key_here
DEBUG=True''',
        'api/main.py': '''from fastapi import FastAPI

app = FastAPI(title="ABI")

@app.get("/")
async def root():
    return {"message": "Hello world, ABI here."}'''
    }

    for file_path, content in files.items():
        with open(file_path, 'w') as f:
            f.write(content)

    # Create YAML files
    yaml_files = {
        'ontology/definitions/object_types.yaml': {'version': '1.0', 'objects': []},
        'ontology/definitions/link_types.yaml': {'version': '1.0', 'links': []},
        'ontology/definitions/action_types.yaml': {'version': '1.0', 'actions': []},
        'workflows/definitions/weekly_report.yaml': {'name': 'weekly_report', 'schedule': 'weekly'},
        'data/data_sources.yaml': {'sources': []}
    }

    for file_path, content in yaml_files.items():
        with open(file_path, 'w') as f:
            yaml.dump(content, f, default_flow_style=False)

    print("Project structure created successfully!")

    update_readme_structure()
    print("README.md updated with current folder structure!")

def check_requirements():
    try:
        # Install requirements
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Requirements installed successfully!")
    except subprocess.CalledProcessError:
        print("Error installing requirements. Please install manually using: pip install -r requirements.txt")
        sys.exit(1)

if __name__ == '__main__':
    create_directory_structure()