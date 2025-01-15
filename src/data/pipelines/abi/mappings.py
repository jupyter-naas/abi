COLORS_NODES = {
    'http://ontology.naas.ai/abi/Pipeline': '#47DD82',
    'http://ontology.naas.ai/abi/Workflow': '#47DD82',
    'http://ontology.naas.ai/abi/Assistant': 'orange', 
    'http://ontology.naas.ai/abi/Ontology': 'white',
    'http://ontology.naas.ai/abi/Integration': 'white',
}

ASSISTANTS_ORDER = {
    "OpenDataAssistant": 0,
    "ContentAssistant": 1,
    "GrowthAssistant": 2,
    "SalesAssistant": 3,
    "OperationsAssistant": 4,
    "FinanceAssistant": 5,
}

ASSISTANTS_INTEGRATIONS = {
    "OpenDataAssistant": [
        "GlassdoorIntegration",
        "NewsAPIIntegration", 
        "PerplexityIntegration",
        "SerperIntegration",
        "YahooFinanceIntegration"
    ],
    "ContentAssistant": [
        "GladiaIntegration",
        "InstagramIntegration",
        "LinkedInIntegration",
        "ReplicateIntegration",
        "YouTubeIntegration"
    ],
    "GrowthAssistant": [
        "LinkedInSalesNavigatorIntegration",
        "SlackIntegration",
        "WhatsAppIntegration"
    ],
    "SalesAssistant": [
        "BrevoIntegration",
        "GmailIntegration",
        "HubSpotIntegration",
        "MailchimpMarketingIntegration",
        "PipedriveIntegration",
        "SendGridIntegration",
        "ZeroBounceIntegration"
    ],
    "OperationsAssistant": [
        "AirtableIntegration",
        "AlgoliaIntegration",
        "AWSS3Integration",
        "ClockifyIntegration",
        "DiscordIntegration",
        "GCPBigQueryIntegration",
        "GCPFunctionsIntegration",
        "GCPStorageIntegration",
        "GithubGraphqlIntegration",
        "GithubIntegration",
        "GoogleAnalyticsIntegration",
        "GoogleCalendarIntegration",
        "GoogleDriveIntegration",
        "GoogleSheetsIntegration",
        "HarvestIntegration",
        "NaasIntegration",
        "NotionIntegration",
        "OneDriveIntegration",
        "PostgresIntegration",
        "SupabaseIntegration"
    ],
    "FinanceAssistant": [
        "AgicapIntegration",
        "AiaIntegration", 
        "MercuryIntegration",
        "PennylaneIntegration",
        "QontoIntegration",
        "StripeIntegration"
    ]
}

ASSISTANTS_ONTOLOGIES = {
    "OpenDataAssistant": [
        "ResourceOntology",
        "EventsOntology",
    ],
    "ContentAssistant": [
        "PublicationOntology",
        "IdeaOntology",
        "ConversationOntology"
    ],
    "GrowthAssistant": [
        "InteractionOntology",
        "GrowthOntology",
        "PersonOntology",
        "OrganizationOntology",
    ],
    "SalesAssistant": [
        "OfferingOntology",
        "DealOntology",
        "ContactOntology",
        "ActivityOntology",
    ],
    "OperationsAssistant": [
        "TaskOntology",
        "PlatformOntology",
        "ProjectOntology",
        "AssetOntology",
    ],
    "FinanceAssistant": [
        "ContractOntology",
        "TransactionOntology",
        "AccountingOntology",
    ]
}


