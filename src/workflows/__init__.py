# from .function_handler import handle_function_calls
# from .function_definitions import get_function_definitions

# __all__ = [
#     'handle_function_calls',
#     'get_function_definitions'
# ] 

import os
import importlib
from typing import List
from langchain_core.tools import BaseTool

def load_tools() -> List[BaseTool]:
    tools = []
    current_dir = os.path.dirname(__file__)
    
    # Get all python files in current directory
    for filename in os.listdir(current_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            # Convert filename to module name
            module_name = filename[:-3]
            
            # Import the module
            module = importlib.import_module(f'.{module_name}', package=__package__)
            
            # Check if module has as_tool function and call it
            if hasattr(module, 'as_tool'):
                tool = module.as_tool()
                if isinstance(tool, BaseTool):
                    tools.append(tool)
                elif isinstance(tool, list):
                    tools.extend([t for t in tool if isinstance(t, BaseTool)])

    return tools

# Export the tools
tools = load_tools()
