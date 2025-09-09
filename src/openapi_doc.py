TAGS_METADATA = [
    {
        "name": "Overview",
        "description": """
### Project Overview
**ABI** (Agentic Brain Infrastructure) is the world's first AI Operating System built on semantic ontologies and knowledge graphs. 
ABI provides the foundational infrastructure for ontology-driven agentic computing, where intelligent agents reason over structured knowledge while coordinating complex multi-agent workflows.

At its core, ABI leverages formal ontologies to create a shared understanding between agents, tools, and data sources. This semantic foundation enables agents to make intelligent decisions based on rich contextual knowledge, maintain coherent state across interactions, and collaborate effectively within enterprise knowledge ecosystems.

### API Overview
The ABI API serves as the system interface to the ontology-driven AI Operating System, providing programmatic access to semantic agents, knowledge graphs, and reasoning capabilities.
Through this API, you can spawn ontology-aware agents, query semantic knowledge bases, and orchestrate complex reasoning workflows across structured enterprise data.

Core ontological capabilities include:
- **Semantic Agent Management**: Deploy agents that reason over formal ontologies and knowledge graphs
- **Ontology Engineering**: Build, validate, and evolve domain-specific knowledge models
- **Knowledge Graph Operations**: Query, update, and reason over enterprise semantic data
- **Contextual Reasoning**: Enable agents to make decisions based on rich ontological context
- **Multi-Modal Integration**: Connect structured knowledge with unstructured data sources
- **Workflow Orchestration**: Coordinate complex multi-step reasoning processes across agent ecosystems
        """,
    },
    {
        "name": "Authentication",
        "description": """
Authentication uses a Bearer token that can be provided either in the Authorization header or as a query parameter. 

**Getting Your API Key:**
- If you're running ABI locally, check your `.env` file for the `ABI_API_KEY` value
- For deployed instances, the API key is set during installation in your environment variables
- Generate a new key by updating the `ABI_API_KEY` in your configuration

*Authentication with Authorization header:*

```python
import requests

# For local development
url = "http://localhost:9879/agents/Abi/completion"
# For deployed instances  
# url = "https://your-domain.com/agents/Abi/completion"

headers = {
    "Authorization": f"Bearer {your_api_key}",
    "Content-Type": "application/json"
}

data = {
    "prompt": "Hello, how can you help me?",
    "thread_id": 1
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

*Authentication with query parameter:*

```python
import requests

# For local development
url = f"http://localhost:9879/agents/Abi/completion?token={your_api_key}"

data = {
    "prompt": "Hello, how can you help me?", 
    "thread_id": 1
}

response = requests.post(url, json=data)
print(response.json())
```
        """,
    },
    {
        "name": "Connections",
        "description": """
Connections are currently configured using Integration secrets (API keys, credentials) set up in the GitHub project settings. \n
Learn more about the data access and secrets key [here](https://github.com/jupyter-naas/abi/blob/main/README.md#setup-github-repository-secrets).

### Agicap
Required:
- `AGICAP_USERNAME`: Username of your Agicap account
- `AGICAP_PASSWORD`: Password of your Agicap account
- `AGICAP_CLIENT_ID`: Client ID of your Agicap account. [Get your client ID](https://app.agicap.com/fr/app/organization-advanced-settings/public-api)
- `AGICAP_CLIENT_SECRET`: Client Secret of your Agicap account. [Get your client secret](https://app.agicap.com/fr/app/organization-advanced-settings/public-api)
- `AGICAP_BEARER_TOKEN`: Bearer Token of your Agicap account.
- `AGICAP_API_TOKEN`: API token of your Agicap account. [Get your API token](https://app.agicap.com/fr/app/parametres/openapi)

### Algolia
Required:
- `ALGOLIA_API_KEY`: API key of your Algolia account. [Get your API key](https://www.algolia.com/api-keys)
- `ALGOLIA_APPLICATION_ID`: Application ID of your Algolia account. [Get your application ID](https://www.algolia.com/api-keys)

### Airtable
Required:
- `AIRTABLE_API_KEY`: API key of your Airtable account. [Get your API key](https://airtable.com/create/tokens)
- `AIRTABLE_BASE_ID`: Base ID of your Airtable account. [Get your base ID](https://airtable.com/create/tokens)

### AWS
Required:
- `AWS_ACCESS_KEY_ID`: Access key ID of your AWS account. [Get your access key ID](https://us-east-1.console.aws.amazon.com/iam/home)
- `AWS_SECRET_ACCESS_KEY`: Secret access key of your AWS account. [Get your secret access key](https://us-east-1.console.aws.amazon.com/iam/home)
- `AWS_REGION`: Region of your AWS account. [Get your region](https://us-east-1.console.aws.amazon.com/iam/home)

### Brevo
Required:
- `BREVO_API_KEY`: API key of your Brevo account. [Get your API key](https://help.brevo.com/hc/en-us/articles/209467485)

### Clockify
Required:
- `CLOCKIFY_API_KEY`: API key of your Clockify account. [Get your API key](https://clockify.me/user/settings)

### Discord
Required:
- `DISCORD_API_KEY`: API key of your Discord account. [Get your API key](https://discord.com/developers/applications)

### Github
Required:
- `GITHUB_ACCESS_TOKEN`: Access token of your Github account. [Get your access token](https://github.com/settings/tokens)

### Gladia
Required:
- `GLADIA_API_KEY`: API key of your Gladia account. [Get your API key](https://www.gladia.ai/)

### Gmail
Required:
- `GMAIL_EMAIL`: Email of your Gmail account.
- `GMAIL_APP_PASSWORD`: App password of your Gmail account. [Get your app password](https://support.google.com/mail/answer/185833)

### Harvest
Required:
- `HARVEST_API_KEY`: API key of your Harvest account. [Get your API key](https://app.harvestapp.com/account/api)
- `HARVEST_ACCOUNT_ID`: Account ID of your Harvest account.

### HubSpot
Required:
- `HUBSPOT_ACCESS_TOKEN`: Access token of your HubSpot account. [Get your access token](https://developers.hubspot.com/docs/api/private-apps)

### Instagram
Required:
- `INSTAGRAM_ACCESS_TOKEN`: Access token of your Instagram account. [Get your access token](https://developers.facebook.com/docs/instagram-api)

### LinkedIn
Required:
- `li_at` cookie: li_at cookie of your LinkedIn account. [Get your li_at cookie](https://www.notion.so/LinkedIn-driver-Get-your-cookies)
- `JSESSIONID` cookie: JSESSIONID cookie of your LinkedIn account. [Get your JSESSIONID cookie](https://www.notion.so/LinkedIn-driver-Get-your-cookies)

### Mailchimp
Required:
- `MAILCHIMP_API_KEY`: API key of your Mailchimp account. [Get your API key](https://mailchimp.com/developer/api/)
- `MAILCHIMP_SERVER_PREFIX`: Server prefix of your Mailchimp account. [Get your server prefix](https://mailchimp.com/developer/api/)

### Mercury
Required:
- `MERCURY_API_TOKEN`: API token of your Mercury account. [Get your API token](https://app.mercury.com/settings/tokens)

### NewsAPI
Required:
- `NEWSAPI_API_KEY`: API key of your NewsAPI account. [Get your API key](https://newsapi.org/register)

### Notion
Required:
- `NOTION_API_KEY`: API key of your Notion account. [Get your API key](https://www.notion.so/my-integrations)

### OneDrive
Required:
- `ONEDRIVE_ACCESS_TOKEN`: Access token of your OneDrive account. [Get your access token](https://learn.microsoft.com/en-us/onedrive/developer/rest-api/getting-started/)

### Pennylane
Required:
- `PENNYLANE_API_TOKEN`: API token of your Pennylane account. [Get your API token](https://pennylane.readme.io/docs/get-my-api-token)

### Perplexity
Required:
- `PERPLEXITY_API_KEY`: API key of your Perplexity account. [Get your API key](https://docs.perplexity.ai/docs/getting-started)

### Pipedrive
Required:
- `PIPEDRIVE_API_KEY`: API key of your Pipedrive account. [Get your API key](https://app.pipedrive.com/settings/api)

### PostgreSQL
Required:
- `POSTGRES_HOST`: Host of your PostgreSQL database.
- `POSTGRES_PORT`: Port of your PostgreSQL database.
- `POSTGRES_DB`: Database name of your PostgreSQL database.
- `POSTGRES_USER`: User of your PostgreSQL database.
- `POSTGRES_PASSWORD`: Password of your PostgreSQL database.

### Qonto
Required:
- `QONTO_ORGANIZATION_SLUG`: Organization slug of your Qonto account. [Get your organization slug](https://support-fr.qonto.com/hc/en-us/articles/23947692362513)
- `QONTO_SECRET_KEY`: Secret key of your Qonto account. [Get your secret key](https://support-fr.qonto.com/hc/en-us/articles/23947692362513)

### Replicate
Required:
- `REPLICATE_API_KEY`: API key of your Replicate account. [Get your API key](https://replicate.com/account/api-tokens)

### Serper
Required:
- `SERPER_API_KEY`: API key of your Serper account. [Get your API key](https://serper.dev/api-key)

### Slack
Required:
- `SLACK_BOT_TOKEN`: Bot token of your Slack account. [Get your bot token](https://api.slack.com/apps)

### Stripe
Required:
- `STRIPE_API_KEY`: API key of your Stripe account. [Get your API key](https://dashboard.stripe.com/apikeys)

### Supabase
Required:
- `SUPABASE_URL`: URL of your Supabase account. [Get your URL](https://app.supabase.com/project/_/settings/api)
- `SUPABASE_KEY`: Key of your Supabase account. [Get your key](https://app.supabase.com/project/_/settings/api)

### TikTok
Required:
- `TIKTOK_ACCESS_TOKEN`: Access token of your TikTok account. [Get your access token](https://developers.tiktok.com/)

### WhatsApp
Required:
- `WHATSAPP_ACCESS_TOKEN`: Access token of your WhatsApp account. [Get your access token](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started)

### Yahoo Finance
Required:
- `YAHOO_FINANCE_API_KEY`: API key of your Yahoo Finance account. [Get your API key](https://www.yahoofinanceapi.com/)

### YouTube
Required:
- `YOUTUBE_API_KEY`: API key of your YouTube account. [Get your API key](https://console.cloud.google.com/apis/credentials)

### ZeroBounce
Required:
- `ZEROBOUNCE_API_KEY`: API key of your ZeroBounce account. [Get your API key](https://app.zerobounce.net/)

        """,
    },
    {
        "name": "Agents",
        "description": """
API endpoints for interacting with ABI's agents.

### Core Agents:
- Abi: Manages and coordinates other agents
- Ontology: Manages and coordinates other agents
- Naas: Manages and coordinates other agents
- Support: Provides help and guidance for using ABI

### Marketplace Agents:
- Custom agents with deep expertise in specific domains
- Can be configured and trained for specialized tasks
- Extensible through custom tools and knowledge bases

Each agent can be accessed through dedicated endpoints that allow:
- Completion requests for generating responses
- Chat interactions for ongoing conversations
- Tool execution for specific tasks
- Configuration updates for customizing behavior

Agents leverage various tools including integrations, pipelines and workflows to accomplish tasks. They can be extended with custom tools and knowledge to enhance their capabilities.

        """,
    },
    {
        "name": "Pipelines",
        "description": """
API endpoints for interacting with ABI's pipelines.
        """,
    },
    {
        "name": "Workflows",
        "description": """
API endpoints for interacting with ABI's workflows.
        """,
    },
]

API_LANDING_HTML = """
<!DOCTYPE html>
<html>
    <head>
        <title>[TITLE]</title>
        <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                background-color: #000000;
                color: white;
            }
            .logo {
                width: 200px;
                margin-bottom: 20px;
            }
            h1 {
                font-size: 48px;
                margin-bottom: 40px;
            }
            .buttons {
                display: flex;
                gap: 20px;
            }
            a {
                padding: 12px 24px;
                font-size: 18px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                color: white;
                background-color: #007bff;
                transition: background-color 0.2s;
            }
            a:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <img src="/static/[LOGO_NAME]" alt="Logo" class="logo">
        <h1>Welcome to [TITLE]!</h1>
        <p>[TITLE] is the API gateway to ABI (Agentic Brain Infrastructure) - your central hub for AI agent orchestration and intelligent automation.</p>
        <div class="buttons">
            <a href="/redoc">Go to Documentation</a>
        </div>
    </body>
</html>
"""
