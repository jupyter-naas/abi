from src.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_assistant_response, print_tool_response
from abi.services.agent.Agent import Agent
from src.assistants.SingleAgent import create_single_agent
from src.assistants.SupervisorAgent import create_supervisor_agent

def on_tool_response(message: str):
    try:
        print_tool_response(f'\n{message}')
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
        print_assistant_response(response)
        print_divider()
        
def run_single_agent():
    agent = create_single_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_supervisor_agent():
    agent = create_supervisor_agent()
    run_agent(agent)
    