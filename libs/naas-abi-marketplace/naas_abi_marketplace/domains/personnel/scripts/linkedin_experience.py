"""Alice Dupont's working experience, transcribed from the LinkedIn profile.

Source: https://demo.example/profiles/demo

``mission_label`` is the opening sentence shown as the node label; ``mission``
is the full stated text. ``skills`` holds only the skills LinkedIn renders
inline — the "+N skills" tail is not guessed at.
"""

from datetime import date

LINKEDIN_PROFILE_URL = "https://demo.example/profiles/demo"

EXPERIENCES = [
    {
        "person": ("Florent", "Ravenel"),
        "organization": "naas.ai",
        "title": "Co-Founder & COO",
        "contract_type": "Self-employed",
        "site": "World",
        "start": date(2023, 4, 1),
        "end": None,
        "duration": "3 yrs 5 mos",
        "mission_label": "Leading the development of an open Universal Data & AI Platform to help organizations create powerful ecosystems of AI Agents",
        "mission": (
            "Leading the development of an open Universal Data & AI Platform to help "
            "organizations create powerful ecosystems of AI Agents\n"
            "- Architecting and building advanced AI agent systems, including multi-agent "
            "coordination to enable complex, autonomous workflows.\n"
            "- Designing integrations with a wide range of tools and external services to "
            "enhance platform extensibility and real-world applicability.\n"
            "- Utilizing knowledge graphs and ontology engineering to create a unified "
            "semantic layer that connects data, AI models, and business logic."
        ),
        "skills": ["Python (Programming Language)", "FastAPI"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "FRV SERVICES",
        "title": "Data & AI Engineer",
        "contract_type": "Freelance",
        "site": "France · Remote",
        "start": date(2019, 10, 1),
        "end": None,
        "duration": "6 yrs 11 mos",
        "mission_label": "Delivered 15+ consulting projects across diverse industries including asset management, luxury, marketing, and growth sectors, improving clients' data & AI workflows and automation capabilities.",
        "mission": (
            "Delivered 15+ consulting projects across diverse industries including asset "
            "management, luxury, marketing, and growth sectors, improving clients' data & AI "
            "workflows and automation capabilities.\n"
            "- Collaborated with stakeholders to translate business needs into scalable "
            "technical solutions.\n"
            "- Design, implement, and manage high-performing data pipelines, focusing on "
            "scalability, efficiency, and stability.\n"
            "- Develop and execute data extraction, transformation, and loading pipelines for "
            "various data sources and destinations.\n"
            "- Automate end-to-end business processes with autonomous AI agents"
        ),
        "skills": ["Python (Programming Language)", "Business Analysis"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "CashStory",
        "title": "Co-Founder",
        "contract_type": "Self-employed",
        "site": "World · Remote",
        "start": date(2018, 10, 1),
        "end": date(2022, 12, 31),
        "duration": "4 yrs 3 mos",
        "mission_label": "We are a consulting company that specializes in helping finance and IT professionals streamline their processes and improve their data management capabilities.",
        "mission": (
            "We are a consulting company that specializes in helping finance and IT "
            "professionals streamline their processes and improve their data management "
            "capabilities.\n"
            "Key Responsibilities:\n"
            "- Identifying and analyzing business requirements.\n"
            "- Developing plans and strategies for collecting, storing, and analyzing data to "
            "meet business requirements.\n"
            "- Designing and implementing data models and data architectures that support the "
            "data strategy.\n"
            "- Creating visualizations and reports that effectively communicate data insights "
            "to clients.\n"
            "- Managing data projects from start to finish, including project planning, "
            "resource allocation, and risk management.\n"
            "- Identifying opportunities for process and tool improvements and implementing "
            "changes to improve the overall data consulting process"
        ),
        "skills": ["Python (Programming Language)", "Business Analysis"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "Groupe BPCE",
        "title": "MOA Finance Consultant",
        "contract_type": "Permanent",
        "site": "Greater Paris Metropolitan Region",
        "start": date(2017, 3, 1),
        "end": date(2019, 2, 28),
        "duration": "2 yrs",
        "mission_label": "Implementation of a technology solution for the financial controlling departments within the group",
        "mission": (
            "Project : Implementation of a technology solution for the financial controlling "
            "departments within the group\n"
            "Key Responsibilities:\n"
            "- Collaborating with the project management teams and financial controllers to "
            "understand business requirements and design an effective solution\n"
            "- Analyzing existing data (operating expenses, costs of risks, liquidity) to "
            "identify areas for improvement\n"
            "- Developing functional and technical specifications for the technology solution\n"
            "- Setting up technical tools to integrate external data sources (using VBA)\n"
            "- Working closely with the IT team to ensure data quality for end-users\n"
            "- Building reporting models for the financial communication department\n"
            "- Managing bugs and irregularities that may arise during the implementation process"
        ),
        "skills": ["Business Analysis", "Microsoft Excel"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "Alstom",
        "title": "Financial Planning Analyst",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2016, 10, 1),
        "end": date(2017, 2, 28),
        "duration": "5 mos",
        "mission_label": "Prepare the monthly instructions and build the reporting review template",
        "mission": (
            "- Prepare the monthly instructions and build the reporting review template\n"
            "- Build financial databases by unit/contract and consolidate results by region\n"
            "- Prepare financial reports by collecting, analyzing, formating and presenting "
            "information\n"
            "- Analyze forecasting operating costs from sites (Hourly Rates, Functional costs)"
        ),
        "skills": ["QlikView", "Financial Reporting"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "Hermès",
        "title": "Financial Project Manager",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2015, 3, 1),
        "end": date(2015, 12, 31),
        "duration": "10 mos",
        "mission_label": "Design and deployment of a major interface between the statutory account and group consolidation",
        "mission": (
            "Project : Design and deployment of a major interface between the statutory account "
            "and group consolidation: SAP Financial Information Management, 320 users "
            "worldwide, 139 entities\n"
            "- Manage the project planning with key stakeholders (project sponsors, "
            "consultants, users)\n"
            "- Collect information at local and corporate level\n"
            "- Build tables between the chart of Accounts and the Group Financial Rules (IFRS)\n"
            "- Work in tandem with SAP developer and Cap Gemini consultants.\n"
            "- Organize User Acceptance Testing\n"
            "- Train the key users on the Group Financial Consolidation interface\n"
            "- Support the go-live of the interface during the September financial closing, "
            "(60 users, 30 entities)\n"
            "- Work directly with Accounting, Financial Control and Treasury department during "
            "the financial closing\n"
            "- Develop BI reports for the Group Financial Controllers"
        ),
        "skills": ["SAP BFC", "IBM Cognos Analytics"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "Lagardère Sports",
        "title": "Corporate Financial Controller",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2014, 9, 1),
        "end": date(2015, 2, 28),
        "duration": "6 mos",
        "mission_label": "Manage the monthly reporting",
        "mission": (
            "- Manage the monthly reporting\n"
            "- Analyze discrepancies in the results (actual vs. budget)\n"
            "- Assist with the preparation of forecasts and budget\n"
            "- Create reports to prepare the subsidiaries for their monthly closing"
        ),
        "skills": ["Financial Reporting", "SAP BFC"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "Kedge Business School",
        "title": "Treasurer / Cash Manager in the sport Business School Association",
        "contract_type": None,
        "site": "Bordeaux",
        "start": date(2013, 9, 1),
        "end": date(2014, 7, 31),
        "duration": "11 mos",
        "mission_label": "Prepare annual budget by sports and by projects (25 sports, 8 events, 130k€)",
        "mission": (
            "- Prepare annual budget by sports and by projects (25 sports, 8 events, 130k€)\n"
            "- Perform daily treasury management\n"
            "- Monitor Cash flows (Actual vs Budget)\n"
            "- Develop relationships with banking partners"
        ),
        "skills": ["Microsoft Excel", "Leadership"],
    },
    {
        "person": ("Florent", "Ravenel"),
        "organization": "EpiSaveurs Nord Champagne Haute Normandie",
        "title": "Accountant",
        "contract_type": None,
        "site": "Rennes",
        "start": date(2012, 4, 1),
        "end": date(2012, 7, 31),
        "duration": "4 mos",
        "mission_label": "Contact with customers/suppliers (means and delay of payment)",
        "mission": (
            "- Contact with customers/suppliers (means and delay of payment)\n"
            "- Enter suppliers invoices in SAP"
        ),
        "skills": ["Microsoft Excel", "Accounting"],
    },
]
