from src.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_assistant_response, print_tool_response
from abi.services.agent.Agent import Agent
from src.assistants.domain.ContentAssistant import create_content_assistant
from src.assistants.domain.FinanceAssistant import create_finance_assistant
from src.assistants.domain.GrowthAssistant import create_growth_assistant
from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
from src.assistants.domain.OperationsAssistant import create_operations_assistant
from src.assistants.domain.SalesAssistant import create_sales_assistant
from src.assistants.foundation.IntegrationAssistant import create_integration_agent
from src.assistants.foundation.SupportAssitant import create_support_assistant
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

def run_opendata_agent():
    agent = create_open_data_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_content_agent():
    agent = create_content_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_growth_agent():
    agent = create_growth_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_sales_agent():
    agent = create_sales_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_operations_agent():
    agent = create_operations_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_finance_agent():
    agent = create_finance_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)
 
def run_integration_agent():
    agent = create_integration_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_support_agent():
    agent = create_support_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_supervisor_agent():
    agent = create_supervisor_agent()
    run_agent(agent)
    