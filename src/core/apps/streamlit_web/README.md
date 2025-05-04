# ABI Streamlit Chat Web App

A ChatGPT-like web app built with Streamlit that integrates the ABI Terminal Agent functionality.

## Features

- Login system with OpenAI API key management
- Chat history persistence using JSON database
- Model selection (supports various OpenAI models)
- Integration with ABI Terminal Agent for advanced functionality
- Toggle between direct OpenAI API calls and Terminal Agent mode
- Clear chat history functionality

## Setup

This application uses Poetry for dependency management, consistent with the rest of the ABI project.

### Prerequisites

- [Poetry](https://python-poetry.org/docs/#installation) must be installed
- ABI project dependencies must be set up

### Running the App

From the project root directory, simply run:

```bash
./src/core/apps/streamlit_web/run.sh
```

The script will:
1. Check if Poetry is installed
2. Ensure all dependencies are installed via Poetry
3. Launch the Streamlit app using Poetry

## Usage

1. On first launch, you'll need to enter your OpenAI API key
2. After logging in, you can start chatting with the assistant
3. Use the sidebar to:
   - Select different OpenAI models
   - Toggle between Terminal Agent and direct API mode
   - Clear your chat history

## Architecture

The app combines Streamlit's user interface capabilities with the ABI Terminal Agent's functionality:

- **Streamlit**: Provides the web interface, session management, and chat UI
- **Terminal Agent**: Handles advanced AI functionality and tool usage
- **OpenAI API**: Powers the chat completions for direct API mode

## Notes

- Your API keys are stored locally in a JSON file
- Chat history is also saved locally and can be cleared at any time
- For security, never share your db.json file as it contains your API keys 