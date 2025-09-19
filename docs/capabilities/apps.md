# Apps

> Note: this is a work in progress, still at specification stage and will be functional soon.

## Overview

ABI Apps are interactive user interfaces built on top of ABI modules that provide specific UI/UX experiences for end users. Apps enable developers to create dedicated interfaces for their modules, making functionality accessible through visual interfaces rather than just APIs or command-line tools.

## Purpose and Benefits

ABI Apps serve several key purposes in the ecosystem:

- **Accessibility**: Make complex ABI functionality available to non-technical users
- **Visualization**: Provide rich visual representations of data and workflows
- **Interactivity**: Enable real-time interaction with ABI modules and pipelines
- **Customization**: Allow tailored user experiences for specific use cases
- **Integration**: Bridge ABI capabilities with familiar UI frameworks

## Supported Frameworks

ABI Apps support multiple UI frameworks and interface types:

1. **Streamlit**: Python-based framework ideal for data applications
2. **Gradio**: Excellent for ML model demos and simple interfaces
3. **Dash**: More complex framework for production-grade dashboards
4. **Command-Line Interfaces (CLI)**: For terminal-based interaction and automation
5. **Custom HTML/JS/CSS**: For fully customized web interfaces

## App Architecture

ABI Apps follow a standard structure and are integrated with the module system:

```
src/custom/modules/your_module_name/
├── apps/                  # Contains UI applications
│   ├── streamlit/         # Streamlit applications
│   │   └── app.py         # Main Streamlit app
│   ├── gradio/            # Gradio applications
│   │   └── app.py         # Main Gradio app
│   ├── cli/               # Command-line interfaces
│   │   └── cli.py         # Main CLI tool
│   └── assets/            # Shared assets for apps
├── workflows/             # Module workflows used by apps
├── pipelines/             # Module pipelines used by apps
└── integrations/          # Module integrations used by apps
```

## Creating a Streamlit App

### Step 1: Set Up the Directory Structure

```bash
mkdir -p src/custom/modules/your_module_name/apps/streamlit
touch src/custom/modules/your_module_name/apps/streamlit/app.py
```

### Step 2: Build Your Streamlit Application

Create a Streamlit app that leverages your module's components:

```python
# src/custom/modules/your_module_name/apps/streamlit/app.py
import streamlit as st
from src.custom.your_module_name.workflows.YourWorkflow import YourWorkflow, YourWorkflowParameters, YourWorkflowConfiguration
from src.custom.your_module_name.integrations.YourIntegration import YourIntegration, YourIntegrationConfiguration
from src import secret

# Set up page config
st.set_page_config(
    page_title="Your ABI App",
    page_icon="🧊",
    layout="wide"
)

# Display header
st.title("Your ABI Application")
st.markdown("This app demonstrates the capabilities of your ABI module.")

# Initialize module components
integration = YourIntegration(YourIntegrationConfiguration(
    api_key=secret.get("YOUR_API_KEY")
))

workflow = YourWorkflow(YourWorkflowConfiguration(
    integration_config=integration
))

# Create UI components
user_input = st.text_input("Enter a value:")
if st.button("Process"):
    if user_input:
        # Execute workflow with user input
        result = workflow.run(YourWorkflowParameters(
            parameter_1=user_input,
            parameter_2=123
        ))
        
        # Display results
        st.success("Processing complete!")
        st.json(result)
    else:
        st.error("Please enter a value")
```

## Creating a CLI App

### Step 1: Set Up the Directory Structure

```bash
mkdir -p src/custom/modules/your_module_name/apps/cli
touch src/custom/modules/your_module_name/apps/cli/cli.py
```

### Step 2: Build Your CLI Application

Create a CLI app using Click or another Python CLI framework:

```python
# src/custom/modules/your_module_name/apps/cli/cli.py
import click
from src.custom.your_module_name.workflows.YourWorkflow import YourWorkflow, YourWorkflowParameters, YourWorkflowConfiguration
from src.custom.your_module_name.integrations.YourIntegration import YourIntegration, YourIntegrationConfiguration
from src import secret
import json

@click.group()
def cli():
    """Command line interface for your ABI module."""
    pass

@cli.command()
@click.argument('input_value')
@click.option('--parameter2', '-p', default=123, help='Value for parameter 2')
def process(input_value, parameter2):
    """Process data using your module's workflow."""
    # Initialize module components
    integration = YourIntegration(YourIntegrationConfiguration(
        api_key=secret.get("YOUR_API_KEY")
    ))
    
    workflow = YourWorkflow(YourWorkflowConfiguration(
        integration_config=integration
    ))
    
    # Execute workflow with arguments
    result = workflow.run(YourWorkflowParameters(
        parameter_1=input_value,
        parameter_2=parameter2
    ))
    
    # Display results
    click.echo(json.dumps(result, indent=2))

if __name__ == '__main__':
    cli()
```

## Running Apps

### Running a Streamlit App

```bash
# From your ABI project root
cd src/custom/modules/your_module_name/apps/streamlit
streamlit run app.py
```

### Running a CLI App

```bash
# From your ABI project root
cd src/custom/modules/your_module_name/apps/cli
python cli.py process "your input value" --parameter2 456
```

### Integrating with ABI

Apps can be registered in the module configuration to be automatically discovered:

```python
# src/custom/modules/your_module_name/__init__.py
APPS = {
    "streamlit": {
        "main": "apps/streamlit/app.py",
        "name": "Your Streamlit App",
        "description": "Interactive web interface for your module"
    },
    "cli": {
        "main": "apps/cli/cli.py",
        "name": "Your CLI App",
        "description": "Command-line interface for your module"
    }
}
```

## Deploying Apps

ABI Apps can be deployed in several ways:

1. **Local Deployment**: Run the app locally for development and testing
2. **Container Deployment**: Package the app with Docker for cloud deployment
3. **Naas.ai Deployment**: Deploy directly to the Naas.ai platform for sharing
4. **CLI Distribution**: Package CLI apps as installable Python packages

### Naas.ai Deployment

To deploy your app to Naas.ai:

```bash
# From your ABI project root
make publish-app module=your_module_name app=streamlit
```

This will package and upload your app to the Naas.ai platform, making it available at `https://app.naas.ai/your-username/your-app-name`.

## Best Practices

When developing ABI Apps:

1. **Separate UI from Logic**: Keep business logic in workflows and pipelines, UI code in the app
2. **Handle Errors Gracefully**: Provide clear error messages and recovery paths
3. **Responsive Design**: Ensure your app works well on different screen sizes
4. **Performance Optimization**: Cache results and optimize for responsive UI
5. **Security Considerations**: Never expose credentials in client-side code
6. **Documentation**: Include clear instructions for using the app
7. **Testing**: Test your app with different inputs and use cases

## Examples

ABI includes several example apps that demonstrate best practices:

- **Data Explorer**: Visualization tool for exploring ABI ontology data
- **Pipeline Builder**: Visual interface for constructing and executing pipelines
- **Integration Manager**: UI for managing external service connections
- **ABI CLI**: Command-line interface for common ABI operations

You can find these examples in the `src/core/common/apps/` directory.

## Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Gradio Documentation](https://gradio.app/docs/)
- [Dash Documentation](https://dash.plotly.com/)
- [Click Documentation](https://click.palletsprojects.com/)
- [ABI API Reference](../api/api-reference.md)
