ASSISTANTS_ORDER = {
    "ContentAssistant": 0,
    "GrowthAssistant": 1,
    "SalesAssistant": 2,
    "OperationsAssistant": 3,
    "FinanceAssistant": 4,
    "OpenDataAssistant": 5, 
}

ASSISTANTS_INTEGRATIONS = {
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
    ],
    "OpenDataAssistant": [
        "GlassdoorIntegration",
        "NewsAPIIntegration", 
        "PerplexityIntegration",
        "SerperIntegration",
        "YahooFinanceIntegration"
    ]
}

ASSISTANTS_ONTOLOGIES = {
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
    ],
    "OpenDataAssistant": [
        "ResourceOntology",
        "EventsOntology",
    ],
}


