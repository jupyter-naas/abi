from src.core.apps.terminal_agent.terminal_style import clear_screen, print_welcome_message, print_divider, get_user_input, print_tool_usage, print_agent_response, print_tool_response, print_image
from abi.services.agent.Agent import Agent
# Foundation assistants
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.foundation.SupervisorAssistant import create_supervisor_agent
# Domain assistants
from src.core.assistants.domain.ContentAssistant import create_content_agent
from src.core.assistants.domain.FinanceAssistant import create_finance_agent
from src.core.assistants.domain.GrowthAssistant import create_growth_agent
from src.core.assistants.domain.OpenDataAssistant import create_open_data_agent
from src.core.assistants.domain.OperationsAssistant import create_operations_agent
from src.core.assistants.domain.SalesAssistant import create_sales_agent
# Expert integrations assistants
from src.core.assistants.expert.integrations.AWSS3Assistant import create_aws_s3_agent
from src.core.assistants.expert.integrations.AgicapAssistant import create_agicap_agent
from src.core.assistants.expert.integrations.AlgoliaAssistant import create_algolia_agent
from src.core.assistants.expert.integrations.AirtableAssistant import create_airtable_agent
from src.core.assistants.expert.integrations.BrevoAssistant import create_brevo_agent
from src.core.assistants.expert.integrations.ClockifyAssistant import create_clockify_agent
from src.core.assistants.expert.integrations.DiscordAssistant import create_discord_agent
from src.core.assistants.expert.integrations.GithubAssistant import create_github_agent
from src.core.assistants.expert.integrations.GladiaAssistant import create_gladia_agent
from src.core.assistants.expert.integrations.GmailAssistant import create_gmail_agent
from src.core.assistants.expert.integrations.GoogleAnalyticsAssistant import create_google_analytics_agent
from src.core.assistants.expert.integrations.GoogleCalendarAssistant import create_google_calendar_agent
from src.core.assistants.expert.integrations.GoogleDriveAssistant import create_google_drive_agent
from src.core.assistants.expert.integrations.GoogleSheetsAssistant import create_google_sheets_agent
from src.core.assistants.expert.integrations.GlassdoorAssistant import create_glassdoor_agent
from src.core.assistants.expert.integrations.HarvestAssistant import create_harvest_agent
from src.core.assistants.expert.integrations.HubSpotAssistant import create_hubspot_agent
from src.core.assistants.expert.integrations.LinkedInAssistant import create_linkedin_agent
from src.core.assistants.expert.integrations.MailchimpAssistant import create_mailchimp_agent
from src.core.assistants.expert.integrations.MercuryAssistant import create_mercury_agent
from src.core.assistants.expert.integrations.NaasAssistant import create_naas_agent
from src.core.assistants.expert.integrations.NewsAPIAssistant import create_news_api_agent
from src.core.assistants.expert.integrations.NotionAssistant import create_notion_agent
from src.core.assistants.expert.integrations.OneDriveAssistant import create_onedrive_agent
from src.core.assistants.expert.integrations.PennylaneAssistant import create_pennylane_agent
from src.core.assistants.expert.integrations.PipedriveAssistant import create_pipedrive_agent
from src.core.assistants.expert.integrations.PostgresAssistant import create_postgres_agent
from src.core.assistants.expert.integrations.QontoAssistant import create_qonto_agent
from src.core.assistants.expert.integrations.SendGridAssistant import create_sendgrid_agent
from src.core.assistants.expert.integrations.SerperAssistant import create_serper_agent
from src.core.assistants.expert.integrations.SlackAssistant import create_slack_agent
from src.core.assistants.expert.integrations.StripeAssistant import create_stripe_agent
from src.core.assistants.expert.integrations.SupabaseAssistant import create_supabase_agent
from src.core.assistants.expert.integrations.WhatsappAssistant import create_whatsapp_agent
from src.core.assistants.expert.integrations.InstagramAssistant import create_instagram_agent
from src.core.assistants.expert.integrations.YahooFinanceAssistant import create_yahoo_finance_agent
from src.core.assistants.expert.integrations.YouTubeAssistant import create_youtube_agent
from src.core.assistants.expert.integrations.ZeroBounceAssistant import create_zerobounce_agent
from src.core.assistants.expert.integrations.PowerPointAssistant import create_powerpoint_agent
# Expert analytics assistants
from src.core.assistants.expert.analytics.PlotlyAssistant import create_plotly_agent
from src.core.assistants.expert.analytics.MatplotlibAssistant import create_matplotlib_agent

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

def run_support_agent():
    agent = create_support_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_supervisor_agent():
    agent = create_supervisor_agent()
    run_agent(agent)

def run_opendata_agent():
    agent = create_open_data_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_content_agent():
    agent = create_content_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_growth_agent():
    agent = create_growth_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_sales_agent():
    agent = create_sales_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_operations_agent():
    agent = create_operations_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_finance_agent():
    agent = create_finance_agent()
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

def run_agicap_agent():
    agent = create_agicap_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_brevo_agent():
    agent = create_brevo_agent()
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

def run_instagram_agent():
    agent = create_instagram_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_linkedin_agent():
    agent = create_linkedin_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_mailchimp_agent():
    agent = create_mailchimp_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_mercury_agent():
    agent = create_mercury_agent()
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

def run_sendgrid_agent():
    agent = create_sendgrid_agent()
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

def run_whatsapp_agent():
    agent = create_whatsapp_agent()
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

def run_zerobounce_agent():
    agent = create_zerobounce_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_plotly_agent():
    agent = create_plotly_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_matplotlib_agent():
    agent = create_matplotlib_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_glassdoor_agent():
    agent = create_glassdoor_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

def run_powerpoint_agent():
    agent = create_powerpoint_agent()
    agent.on_tool_usage(lambda message: print_tool_usage(message.tool_calls[0]['name']))
    agent.on_tool_response(on_tool_response)
    run_agent(agent)

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