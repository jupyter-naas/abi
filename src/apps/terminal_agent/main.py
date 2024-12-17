from src.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_assistant_response, print_tool_response
from abi.services.agent.Agent import Agent
from src.assistants.foundation.SupportAssitant import create_support_assistant
from src.assistants.foundation.SupervisorAgent import create_supervisor_agent
from src.assistants.domain.ContentAssistant import create_content_assistant
from src.assistants.domain.FinanceAssistant import create_finance_assistant
from src.assistants.domain.GrowthAssistant import create_growth_assistant
from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
from src.assistants.domain.OperationsAssistant import create_operations_assistant
from src.assistants.domain.SalesAssistant import create_sales_assistant
from src.assistants.custom.AWSS3Assistant import create_aws_s3_agent
from src.assistants.custom.AlgoliaAssistant import create_algolia_agent
from src.assistants.custom.AirtableAssistant import create_airtable_agent
from src.assistants.custom.ClockifyAssistant import create_clockify_agent
from src.assistants.custom.DiscordAssistant import create_discord_agent
from src.assistants.custom.GithubAssistant import create_github_agent
from src.assistants.custom.GladiaAssistant import create_gladia_agent
from src.assistants.custom.GmailAssistant import create_gmail_agent
from src.assistants.custom.GoogleAnalyticsAssistant import create_google_analytics_agent
from src.assistants.custom.GoogleCalendarAssistant import create_google_calendar_agent
from src.assistants.custom.GoogleDriveAssistant import create_google_drive_agent
from src.assistants.custom.GoogleSheetsAssistant import create_google_sheets_agent
from src.assistants.custom.HarvestAssistant import create_harvest_agent
from src.assistants.custom.HubspotAssistant import create_hubspot_agent
from src.assistants.custom.LinkedInAssistant import create_linkedin_agent
from src.assistants.custom.NaasAssistant import create_naas_agent
from src.assistants.custom.NewsAPIAssistant import create_news_api_agent
from src.assistants.custom.NotionAssistant import create_notion_agent
from src.assistants.custom.OneDriveAssistant import create_onedrive_agent
from src.assistants.custom.PennylaneAssistant import create_pennylane_agent
from src.assistants.custom.PipedriveAssistant import create_pipedrive_agent
from src.assistants.custom.PostgresAssistant import create_postgres_agent
from src.assistants.custom.QontoAssistant import create_qonto_agent
from src.assistants.custom.SerperAssistant import create_serper_agent
from src.assistants.custom.SlackAssistant import create_slack_agent
from src.assistants.custom.StripeAssistant import create_stripe_agent
from src.assistants.custom.SupabaseAssistant import create_supabase_agent
from src.assistants.custom.YahooFinanceAssistant import create_yahoo_finance_agent
from src.assistants.custom.YouTubeAssistant import create_youtube_agent

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

def run_support_agent():
    agent = create_support_assistant()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_supervisor_agent():
    agent = create_supervisor_agent()
    run_agent(agent)

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

def run_airtable_agent():
    agent = create_airtable_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_algolia_agent():
    agent = create_algolia_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_aws_s3_agent():
    agent = create_aws_s3_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_clockify_agent():
    agent = create_clockify_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_discord_agent():
    agent = create_discord_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_github_agent():
    agent = create_github_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_gladia_agent():
    agent = create_gladia_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_gmail_agent():
    agent = create_gmail_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_google_analytics_agent():
    agent = create_google_analytics_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_google_calendar_agent():
    agent = create_google_calendar_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_google_drive_agent():
    agent = create_google_drive_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_google_sheets_agent():
    agent = create_google_sheets_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_harvest_agent():
    agent = create_harvest_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_hubspot_agent():
    agent = create_hubspot_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_linkedin_agent():
    agent = create_linkedin_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_naas_agent():
    agent = create_naas_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_news_api_agent():
    agent = create_news_api_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_notion_agent():
    agent = create_notion_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_onedrive_agent():
    agent = create_onedrive_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_pennylane_agent():
    agent = create_pennylane_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_pipedrive_agent():
    agent = create_pipedrive_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_postgres_agent():
    agent = create_postgres_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_qonto_agent():
    agent = create_qonto_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_serper_agent():
    agent = create_serper_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_slack_agent():
    agent = create_slack_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_stripe_agent():
    agent = create_stripe_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_supabase_agent():
    agent = create_supabase_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_yahoo_finance_agent():
    agent = create_yahoo_finance_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_youtube_agent():
    agent = create_youtube_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)
