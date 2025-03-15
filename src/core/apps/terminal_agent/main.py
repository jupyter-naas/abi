from src.core.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_agent_response, print_tool_response, print_image
from abi.services.agent.Agent import Agent

def on_tool_response(message: str):
    try:
        print_tool_response(f'\n{message}')
        # Check if the message contains a path to an image file
        if isinstance(message.content, str):
            # Look for image file paths in the message
            words = message.content.split(" ")
            for word in words:
                if any(word.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif']):
                    print_image(word)
    except Exception as e:
        print(e)

def run_agent(agent: Agent):
    clear_screen()
    print_welcome_message()
    print_divider()
    
    while True:
        user_input = get_user_input()
        
        if user_input == 'exit':
            return
        elif user_input == 'help':
            print_welcome_message()
            continue
        elif user_input == 'reset':
            agent.reset()
            clear_screen()
            continue
            
        print_divider()
        response = agent.invoke(user_input)
        print_agent_response(response)
        print_divider()

def generic_run_agent(agent_class: str = None):
    """Run an agent dynamically loaded from the src/modules directory.
    
    This method provides a generic way to run any agent that is loaded from the modules
    directory, eliminating the need to create individual run functions for each agent.
    The agents are automatically discovered and loaded through the module system.
    
    Args:
        agent_class (str, optional): The class name of the agent to run. If None, will
            print an error message. The class name should match exactly with the agent's
            class name in the modules.
    
    Example:
        >>> generic_run_agent("SupervisorAssistant")  # Runs the SupervisorAssistant agent
        >>> generic_run_agent("ContentAssistant")     # Runs the ContentAssistant agent
    
    Note:
        This replaces the need for individual run_*_agent() functions by dynamically
        finding and running the requested agent from the loaded modules. The agent
        must be properly registered in a module under src/modules for this to work.
    """
    from src.__modules__ import get_modules
    
    if agent_class is None:
        print('No agent class provided. Please set the AGENT_CLASS environment variable.')
        return
    
    for module in get_modules():
        for agent in module.agents:
            print(agent.__class__.__name__)
            if agent.__class__.__name__ == agent_class:
                agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
                agent.on_tool_response(on_tool_response)
                run_agent(agent)
                return 
    
    print(f"Agent {agent_class} not found")

if __name__ == "__main__":
    import sys
    
    # Get the function name from command line argument
    if len(sys.argv) > 1:
        function_name = sys.argv[1]
        if function_name in globals():
            globals()[function_name](*sys.argv[2:])
        else:
            print(f"Function {function_name} not found")
    else:
        print("Please specify a function to run")