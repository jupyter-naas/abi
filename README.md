# ABI Framework

**An API-driven organizational AI system backend offering assistants, ontology, integrations, workflows, and analytics in a unified framework.**

<img src="./assets/images/abi-flywheel.png" width="100%" height="100%">

## Overview

The **ABI Framework** (Augmented Business Intelligence) is a Python-based backend framework designed to serve as the core infrastructure for building an Organizational AI System. This system empowers businesses to integrate, manage, and scale AI-driven operations with a focus on ontology, assistant-driven workflows, and analytics. Designed for flexibility and scalability, ABI provides a customizable framework suitable for organizations aiming to create intelligent, automated systems tailored to their needs.

## Key Features

- **Assistants**: Configurable AI assistants to handle specific organizational tasks and interact with users.
- **Ontology Management**: Define and manage data relationships, structures, and semantic elements.
- **Integrations**: Seamlessly connect to external data sources and APIs for unified data access.
- **Workflows**: Automate complex business processes and manage end-to-end workflows.
- **Analytics**: Access insights through integrated analytics and real-time data processing.
- **Data**: Handle diverse datasets and manage schema, versioning, deduplication, and change data capture.

## License
ABI Framework is open-source and available for non-production use under the [AGPL license](https://opensource.org/licenses/AGPL). For production deployments, a commercial license is required. Please contact us at support@naas.ai for details on licensing options.

## Folder Structure

```
├── analytics/
│   └── reports/
│       └── __init__.py
├── api/
│   ├── analytics/
│   │   └── __init__.py
│   ├── assistants/
│   │   ├── custom/
│   │   │   └── __init__.py
│   │   ├── domain/
│   │   │   └── __init__.py
│   │   ├── foundation/
│   │   │   └── __init__.py
│   │   ├── personal/
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── data/
│   │   └── __init__.py
│   ├── integrations/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── ontology/
│   │   └── __init__.py
│   ├── workflows/
│   │   └── __init__.py
│   └── main.py
├── assets/
│   ├── images/
│   │   ├── __init__.py
│   │   └── abi-flywheel.png
│   ├── static/
│   │   └── __init__.py
│   └── templates/
│       └── __init__.py
├── core/
│   ├── db/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   └── utils/
│       └── __init__.py
├── data/
│   ├── pipelines/
│   │   └── __init__.py
│   └── data_sources.yaml
├── docs/
├── integrations/
│   └── __init__.py
├── models/
│   ├── generative_ai_models/
│   │   └── __init__.py
│   └── ml_models/
│       └── __init__.py
├── ontology/
│   └── definitions/
│       ├── __init__.py
│       ├── action_types.yaml
│       ├── link_types.yaml
│       └── object_types.yaml
├── tests/
├── workflows/
│   └── definitions/
│       ├── __init__.py
│       └── weekly_report.yaml
├── Dockerfile
├── LICENSE
├── README.md
├── docker-compose.yml
├── requirements.txt
├── setup_project.py
└── update_readme.py
```

## Getting Started

1. **Prerequisites**
   - Install [Poetry](https://python-poetry.org/docs/#installation) for Python dependency management

2. **Clone the Repository**
   ```bash
   git clone https://github.com/jupyter-naas/abi-framework.git
   cd abi-framework
   ```

3. **Install Dependencies**
   ```bash
   poetry install
   ```

4. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Using the Chat Interface

ABI Framework provides two chat modes through the terminal interface:

### Single Assistant Chat

Start a conversation with a single AI assistant:

```bash
poetry run chat-single-assistant
```

### Multiple Assistant Chat

Engage with multiple AI assistants in a collaborative conversation:

```bash
poetry run chat-multiple-assistant
```

These chat interfaces provide an interactive way to test and utilize the AI assistants within the framework.

## Managing Dependencies

To add a new Python dependency to the project:

```bash
poetry add <library-name>
```

This will automatically:
- Add the dependency to your `pyproject.toml`
- Update the `poetry.lock` file
- Install the package in your virtual environment


## Contributing

1. Fork the repository.
2. Create a new branch with your feature or fix.
3. Open a pull request to the main branch.

## Support
For any questions or support requests, please reach out via support@naas.ai or on our [community forum](https://join.slack.com/t/naas-club/shared_invite/zt-1970s5rie-dXXkigAdEJYc~LPdQIEaLA) on Slack.