# GPT-4o Module

This module provides integration with OpenAI's GPT-4o model, allowing the ABI system to leverage its advanced multimodal capabilities for various tasks. GPT-4o is OpenAI's most advanced model that combines high performance with cost efficiency.

## Components

- **Integration**: Provides direct access to GPT-4o via OpenAI's API
- **Model Configuration**: Sets up the GPT-4o model for use within the ABI framework
- **Tools**: Pre-configured tools for common GPT-4o operations

## Configuration

To use this module, ensure you have set the following in your `.env` file:

```
OPENAI_API_KEY=your_api_key_here
```

## Usage

Once the module is loaded, the GPT-4o model and its integration will be available to other modules and agents in the system. 