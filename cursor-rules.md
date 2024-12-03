# Guide to Create a Tool / Function Call

## Introduction

This guide helps integrate new API tools into the assistant. As an AI assistant, I will:

1. 📝 Review Your API Details:
   - API documentation/instructions you provide
   - Authentication requirements (API keys, tokens, etc.)
   - API endpoints and their functionality
   - Any rate limits or restrictions

2. ❓ Ask Clarifying Questions:
   - If any critical information is missing
   - About specific API behaviors
   - About desired error handling
   - About expected outputs

3. 🛠️ Create Integration Files:
   - Tool implementation file
   - Function definitions
   - Environment variable setup
   - Dependency requirements

4. ✅ Provide Implementation Summary:
   - List of all created/modified files
   - Required environment variables
   - New dependencies added
   - Testing instructions

Please provide:
1. API documentation or integration guide
2. Authentication details (how to get/use API key)
3. Any specific requirements or preferences

## Integration Checklist
1. ⚙️ Environment Setup
   - Add API key to .env
   - Update requirements.txt
   - Install dependencies

2. 🛠️ Tool Creation
   - Create tool file
   - Implement API functions
   - Add error handling

3. 🔗 Integration
   - Add tool definition
   - Register in handler
   - Update exports
   - Update assistant instructions

4. 🧪 Testing
   - Test direct API calls
   - Test through assistant
   - Verify error handling

## Conclusion

After completing the integration, provide the user with:

✅ Integration Summary:
1. Files created/modified:
   - List all files that were created or changed
2. Dependencies added:
   - List new packages added to requirements.txt
3. Environment variables:
   - List new environment variables needed

✅ Testing Instructions:
1. Direct testing:
   ```bash
   # Test the tool directly
   python integrations/tools/your_api_tools.py
   ```

2. Assistant testing:
   ```bash
   # Test through the assistant
   python main.py
   # Then try: "Use [your_tool] to..."
   ```

3. Expected output:
   - Describe what successful output looks like
   - Note any common error messages

✅ Next Steps:
1. Install new dependencies: `pip install -r requirements.txt`
2. Add your API key to .env
3. Run the direct test
4. Test through the assistant

## Adding New API Tools

### 1. Initial Setup
1. Add your API key to `.env`:
```bash
# .env
OPENAI_API_KEY=your_openai_key
ASSISTANT_ID=your_assistant_id
YOUR_NEW_API_KEY=your_api_key  # Add your new API's key here
```

2. Update `requirements.txt` with ALL required packages:
```bash
# Existing core dependencies
openai>=1.3.0  # OpenAI API client
python-dotenv>=0.19.0  # For environment variables
requests>=2.31.0  # For API calls

# Add your new dependencies below with version constraints
your-package>=1.0.0  # Brief description of what this package is for
another-package>=2.0.0  # Another required package

# Example:
# replicate>=0.20.0  # For Replicate API integration
# pillow>=10.0.0  # For image processing
```

IMPORTANT: After updating requirements.txt:
1. Install new dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Test imports:
   ```python
   # Create a test.py file
   import your_package
   import another_package
   print("All imports successful!")
   ```
3. Document any special installation requirements in comments

### 2. Create Tool File
Create a new file in `integrations/tools` directory (e.g., `integrations/tools/your_api_tools.py`):

```python
import os
import requests
from functools import lru_cache
from cachetools import TTLCache, cached
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load environment variables
load_dotenv()

# Cache setup (optional)
response_cache = TTLCache(maxsize=100, ttl=3600)  # Cache for 1 hour

@lru_cache(maxsize=1)
def get_api_key() -> str:
    """Get API key from environment variables."""
    api_key = os.getenv("YOUR_NEW_API_KEY")
    if not api_key:
        raise ValueError("YOUR_NEW_API_KEY environment variable not set")
    return api_key

@cached(cache=response_cache)
def your_api_function(param1: str, param2: str = "default") -> str:
    """
    Call your API endpoint.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter (default: "default")
    Returns:
        str: Response from API or error message
    """
    try:
        url = "https://api.example.com/v1/endpoint"
        headers = {"Authorization": f"Bearer {get_api_key()}"}
        
        response = requests.get(
            url, 
            headers=headers,
            params={"param1": param1, "param2": param2},
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        return f"Result: {data['relevant_field']}"
        
    except requests.exceptions.RequestException as e:
        return f"API request failed: {str(e)}"
    except json.JSONDecodeError:
        return "Error: Invalid JSON response from API"
    except Exception as e:
        return f"Error calling API: {str(e)}"

# Direct testing
if __name__ == "__main__":
    print("\nTesting API function:")
    try:
        result = your_api_function("test1")
        print(f"Success: {result}")
    except Exception as e:
        print(f"Test failed: {str(e)}")
```

### 3. Add Function Definition
Add your function definition to `workflows/functions/function_definitions.py`:

```python
def get_function_definitions() -> List[Dict]:
    return [
        # ... existing definitions ...
        {
            "type": "function",
            "function": {
                "name": "your_api_function",
                "description": "Clear description of what this API does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "Description of first parameter"
                        },
                        "param2": {
                            "type": "string",
                            "description": "Description of second parameter"
                        }
                    },
                    "required": ["param1", "param2"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    ]
```

### 4. Register Function in Handler
Update `workflows/functions/function_handler.py`:

```python
from integrations.tools import your_api_function

@lru_cache(maxsize=1)
def get_function_map():
    return {
        # ... existing functions ...
        "your_api_function": your_api_function,
    }
```

### 5. Export Function
Update `integrations/tools/__init__.py`:

```python
from .your_api_tools import your_api_function

__all__ = [
    # ... existing exports ...
    'your_api_function',
]
```

### 6. Update Assistant Instructions
Update `prompts.py` to include your new tool:

```python
SUPER_ASSISTANT_INSTRUCTIONS = """
{
    # ... other sections ...
    "tools": {
        # ... existing tools ...
        "your_api_name": {
            "capabilities": ["List what your API can do"],
            "usage": "When to use this API",
            "restrictions": "Any API limitations or requirements",
            "error_handling": "How to handle common errors"
        }
    }
}
"""
```

### 7. Best Practices

#### Code Organization
1. Type Hints:
   - Use proper type hints for all functions
   - Import typing modules needed
   - Document return types

2. Environment Variables:
   - Always use python-dotenv
   - Check for missing variables early
   - Provide clear error messages

3. Error Handling:
   - Use specific exception types
   - Provide detailed error messages
   - Add timeouts to API calls
   - Handle rate limits
   - Log errors appropriately

4. Testing:
   - Include unit tests
   - Test with real API keys
   - Test error conditions
   - Test rate limits
   - Test with various inputs

#### OpenAI Function Schema
1. Parameter Definitions:
   - NEVER use 'default' in parameter definitions
   - List ALL parameters in 'required' array
   - Use 'enum' for fixed values
   - Example:
     ```python
     # CORRECT
     {
         "type": "object",
         "properties": {
             "param1": {
                 "type": "string",
                 "description": "Description (uses 'default' if not specified)"
             },
             "fixed_param": {
                 "type": "integer",
                 "description": "Fixed value parameter",
                 "enum": [1024]
             }
         },
         "required": ["param1", "fixed_param"]
     }
     ```

2. Common Schema Mistakes:
   - Using 'default' in parameters
   - Missing parameters in 'required'
   - Incorrect type definitions
   - Missing descriptions

### 8. Common Issues and Solutions

1. API Integration:
   ```python
   # CORRECT
   try:
       response = requests.get(url, timeout=10)
       response.raise_for_status()
   except requests.exceptions.RequestException as e:
       return f"API error: {str(e)}"
   ```

2. Environment Variables:
   ```python
   # CORRECT
   if not (api_key := os.getenv("YOUR_API_KEY")):
       raise ValueError("YOUR_API_KEY not set")
   ```
