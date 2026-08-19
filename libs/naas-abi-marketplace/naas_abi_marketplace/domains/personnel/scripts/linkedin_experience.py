"""LinkedIn working experience transcribed for demo personnel graph.

Sources:
- Florent: https://demo.example/profiles/demo
- Jeremy: https://demo.example/profiles/emma-petit
- Maxime: https://demo.example/profiles/grace-lambert
- Anthony: https://demo.example/profiles/demo
- Martin: https://demo.example/profiles/frank-moreau
- Valentin: https://demo.example/profiles/demo
- Christophe: https://demo.example/profiles/david-leroy
- Alexis: https://demo.example/profiles/bob-martin

``mission_label`` is the opening sentence shown as the node label; ``mission``
is the full stated text. ``skills`` holds only the skills LinkedIn renders
inline - the "+N skills" tail is not guessed at.
"""

from datetime import date

from naas_abi_marketplace.domains.personnel.scripts.linkedin_experience_alexis import (
    ALEXIS_EXPERIENCES,
)

LINKEDIN_PROFILE_URLS = {
    "Alice Dupont": "https://demo.example/profiles/demo",
    "Emma Petit": "https://demo.example/profiles/emma-petit",
    "Grace Lambert": "https://demo.example/profiles/grace-lambert",
    "Claire Bernard": "https://demo.example/profiles/demo",
    "Frank Moreau": "https://demo.example/profiles/frank-moreau",
    "Hugo Girard": "https://demo.example/profiles/demo",
    "David Leroy": "https://demo.example/profiles/david-leroy",
    "Bob Martin": "https://demo.example/profiles/bob-martin",
}

# Backward compatibility for imports that expect a single Florent URL.
LINKEDIN_PROFILE_URL = LINKEDIN_PROFILE_URLS["Alice Dupont"]

FLORENT_EXPERIENCES = [
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

JEREMY_EXPERIENCES = [
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "naas.ai",
        "title": "Founder & CEO",
        "contract_type": "Permanent",
        "site": "World",
        "start": date(2023, 4, 1),
        "end": None,
        "duration": "3 yrs 5 mos",
        "mission_label": (
            "Leading the development of an open Universal Data & AI Platform to help "
            "organizations create powerful ecosystems of AI assistants"
        ),
        "mission": (
            "Leading the development of an open Universal Data & AI Platform to help "
            "organizations create powerful ecosystems of AI assistants\n"
            "- Leveraging ontologies as a unifying field between data, AI models, "
            "workflows, analytics, and external systems\n"
            "- Driving innovation in making data and AI accessible and affordable for "
            "organizations of all sizes\n"
            "- Overseeing product development, business strategy, partnerships and team "
            "management"
        ),
        "skills": ["Strategic Thinking", "Data Engineering"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Forvis Mazars Group",
        "title": "Senior Advisor, Data & AI Services",
        "contract_type": "Permanent Part-time",
        "site": "Remote",
        "start": date(2024, 11, 1),
        "end": None,
        "duration": "1 yr 10 mos",
        "mission_label": (
            "Advising on projects from strategy to execution for Data & AI Products"
        ),
        "mission": (
            "Advising on projects from strategy to execution for Data & AI Products\n"
            "- Focusing on creating profitable, auditable, and trustworthy AI solutions "
            "for clients\n"
            "- Providing expert guidance on integrating data and AI technologies into "
            "business processes\n"
            "- Assisting in developing strategies for AI adoption and implementation "
            "across various industries\n"
            "- Collaborating with cross-functional teams to ensure successful delivery "
            "of data and AI initiatives"
        ),
        "skills": ["AI Strategy", "Business Intelligence (BI)"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "University at Buffalo",
        "title": "Research Associate in Applied Ontology, Department of Philosophy",
        "contract_type": "Permanent Part-time",
        "site": "Buffalo, NY",
        "start": date(2024, 11, 1),
        "end": None,
        "duration": "1 yr 10 mos",
        "mission_label": (
            "Conducting research on how executable ontologies can serve as a universal "
            "method for AI assistants/agents alignment, explainability, and compliance"
        ),
        "mission": (
            "Conducting research on how executable ontologies can serve as a universal "
            "method for AI assistants/agents alignment, explainability, and compliance\n"
            "- Exploring the intersection of philosophy, technology, and business in the "
            "context of AI systems\n"
            "- Contributing to academic publications and presentations in the field of "
            "applied ontology and AI\n"
            "- Collaborating with interdisciplinary teams to advance the understanding "
            "and application of ontologies in AI"
        ),
        "skills": ["Applied Ontology", "Explainable AI (XAI)"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "CashStory",
        "title": "Founder",
        "contract_type": None,
        "site": "Paris",
        "start": date(2016, 11, 1),
        "end": date(2023, 4, 30),
        "duration": "6 yrs 6 mos",
        "mission_label": (
            "Automation services company for business professionals."
        ),
        "mission": (
            "Automation services company for business professionals.\n"
            "- Developed a framework to help professionals approach data, automation & AI "
            "through Education and Open source products.\n"
            "- Trained business professionals on how to take back control over their data "
            "and build an infinite solution maker mindset.\n"
            "- Strived to build a better way to see financial & extra-financial information "
            "for wiser decision making, taking into consideration environmental issues & "
            "well being as much as cash, profit and value."
        ),
        "skills": ["Strategic Thinking", "Data Engineering"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Technip",
        "title": "Group Cash Manager",
        "contract_type": None,
        "site": "Paris",
        "start": date(2013, 4, 1),
        "end": date(2016, 10, 31),
        "duration": "3 yrs 7 mos",
        "mission_label": "Group Treasury Cash Management at Technip Corporate Services, Porte Maillot, Paris.",
        "mission": (
            "Technip, Paris, France (World leader in project management and engineering in "
            "the energy industry | Listed on NYSE EURONEXT CAC 40)\n"
            "Corporate Cash Manager, Group Treasury Department, April 2013 – October 2016\n"
            "Group Treasury Cash Management\n"
            "• Perform daily treasury management and driving global liquidity initiatives\n"
            "• Monitor Cash flows (by nature and by projects), Debt and Working Capital "
            "Requirement actuals and forecasts.\n"
            "• Drive implementation of new structures to maximize cash available at HQ and "
            "minimize operational cash balances\n"
            "• Work with the treasury senior management on board/other executive "
            "presentations\n"
            "• Develop sound relationships with banking partners for Working Capital "
            "Management, Financial result optimization\n"
            "• Act in constant relation with internal constituencies (Strategy, Group "
            "Consolidation, Tax, Legal, IT, Compliance)\n"
            "Strategic Business Systems & Process Management\n"
            "• Project Manager/Administrator of the Group Treasury Systems (Diapason / "
            "Treasury Management Software, Hyperion / Business Intelligence tool) focusing "
            "on the continuous development of new functionalities and implementation of "
            "the TMS\n"
            "• Define cash management and Treasury system architecture of the future\n"
            "• Lead cross organizational partnership for proposed treasury and finance "
            "strategy\n"
            "• Develop clear project plans and ownership metrics (KPI's) to drive "
            "accountability and execution throughout the group treasury organization."
        ),
        "skills": ["Strategic Thinking", "Cash Management"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "ESI Group",
        "title": "Cash Control Project Manager",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2011, 7, 1),
        "end": date(2013, 4, 30),
        "duration": "1 yr 10 mos",
        "mission_label": (
            "Corporate Cash Controller, Financial Controlling at ESI Group, Paris, France."
        ),
        "mission": (
            "ESI Group, Paris, France (Pioneer and world-leading provider in Virtual "
            "Prototyping | Listed on NYSE EURONEXT Part C)\n"
            "Corporate Cash Controller, Financial Controlling, July 2011 – April 2013\n"
            "• Work closely with Board members (CEO, CFO, Director of Financial Operations) "
            "to integrate Cash in the financial monitoring of the group: development of "
            "Cash-flow reporting process, Balance Scorecard KPI's, bi-monthly cash flow "
            "analysis consolidation, monthly usage during the Board.\n"
            "• In depth analysis of the financial impact of French R&D Tax Credit (Crédit "
            "d'impôt recherche), Taxes and Working Capital Management\n"
            "• Build operating excel models at local and group level to challenge Cash "
            "forecast direct method"
        ),
        "skills": ["Strategic Thinking", "Cash Management"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Brittany Ferries",
        "title": "Onboard Sales",
        "contract_type": None,
        "site": "At sea",
        "start": date(2009, 7, 1),
        "end": date(2009, 12, 31),
        "duration": "6 mos",
        "mission_label": "Onboard sales during cross-channel ferry crossings.",
        "mission": "Onboard sales during cross-channel ferry crossings.",
        "skills": ["Strategic Thinking"],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Schneider Electric",
        "title": "Supply Chain Financial and Administrative intern",
        "contract_type": None,
        "site": "Chartres de Bretagne, France",
        "start": date(2009, 1, 1),
        "end": date(2009, 2, 28),
        "duration": "2 mos",
        "mission_label": (
            "Supply Chain Financial and Administrative Intern, Region EMEA and Asia Pacific."
        ),
        "mission": (
            "Schneider Electric, Chartres de Bretagne, France (Worldwide energy solution "
            "provider | Listed on NYSE EURONEXT Part A)\n"
            "Supply Chain Financial and Administrative Intern, Region EMEA and Asia Pacific\n"
            "• Contact with clients/providers for credit collection (means and delay of "
            "payment)\n"
            "• Internal logistics control, order entry and invoicing and follow-up on "
            "orders in SAP\n"
            "• Relationship with logistics companies and shipping agents"
        ),
        "skills": [],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Comité National Olympique et Sportif Français",
        "title": "Volontaire, Jeux Olympiques de Pékin 2008 (Beijing 2008)",
        "contract_type": None,
        "site": "Beijing, China",
        "start": date(2008, 7, 1),
        "end": date(2008, 8, 31),
        "duration": "2 mos",
        "mission_label": (
            "Membre du Club France aux Jeux Olympiques de Pékin 2008, Novotel Xin Qiao, "
            "Pékin, Chine"
        ),
        "mission": (
            "Membre du Club France aux Jeux Olympiques de Pékin 2008, Novotel Xin Qiao, "
            "Pékin, Chine\n"
            "Au sein de l'équipe Réceptions/Bar: organisation events officiels & médias, "
            "soirées des médaillés, permanence journalière"
        ),
        "skills": [],
    },
    {
        "person": ("Jeremy", "Ravenel"),
        "organization": "Parker Hannifin",
        "title": "Marketing Intern (May 2008 : New Delhi,Inde + June 2008 : Singapour)",
        "contract_type": None,
        "site": "Asia",
        "start": date(2008, 5, 1),
        "end": date(2008, 6, 30),
        "duration": "2 mos",
        "mission_label": (
            "Qualitative study before the launch of a new product in Asia (focus on India)."
        ),
        "mission": (
            "Mission in 2 subsidies : New Delhi, Inde (May 2008), Singapore (June 2008)\n"
            "Objective : realize a qualitative study before the launch of a new product in "
            "Asia (focus on India)"
        ),
        "skills": [],
    },
]

MAXIME_EXPERIENCES = [
    {
        "person": ("Maxime", "Jublou"),
        "organization": "naas.ai",
        "title": "Chief Technology Officer",
        "contract_type": None,
        "site": "France",
        "start": date(2023, 4, 1),
        "end": None,
        "duration": "3 yrs 5 mos",
        "mission_label": (
            "The universal open source data platform, based on @jupyter — democratizing "
            "data & AI with low-code templates and generative AI models."
        ),
        "mission": (
            "The universal open source data platform, based on @jupyter\n"
            "Democratizing data & AI with low-code templates and generative AI models.\n"
            "We are creating a lean data framework to develop powerful data & AI products."
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "CashStory",
        "title": "Chief Technology Officer",
        "contract_type": None,
        "site": "France",
        "start": date(2021, 6, 1),
        "end": date(2023, 4, 30),
        "duration": "1 yr 11 mos",
        "mission_label": (
            "CashStory is an automation services company."
        ),
        "mission": (
            "CashStory is an automation services company.\n"
            "We developed a framework to help professionals approach data, automation & AI "
            "through Education and Opensource products.\n"
            "We train motivated individuals on how to take back control over their data and "
            "build an infinite solution maker mindset.\n"
            "We believe in a better way to see financial & extra-financial information for "
            "wiser decision making, taking into consideration environmental issues & well being "
            "as much as cash, profit and value.\n"
            "We are empowering contributors, partners and colleagues to help them have a "
            "huge impact through opensource contributions.\n"
            "Currently building:\n"
            "- Naas.ai : Jupyter notebooks as a service for tech savvy users.\n"
            "- CS Education : a gamified training program in French to develop data mining "
            "& soft skills.\n"
            "- BOB : opensource enterprise search & workspaces by projects. (R&D)"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "Freelance",
        "title": "Cloud Engineer / DevOps Consultant",
        "contract_type": "Freelance",
        "site": "Paris, Île-de-France, France",
        "start": date(2020, 2, 1),
        "end": date(2021, 6, 30),
        "duration": "1 yr 5 mos",
        "mission_label": (
            "Independent cloud and DevOps consulting engagements."
        ),
        "mission": (
            "- Kubernetes (EKS)\n"
            "- Helm / SOPS / Skaffold\n"
            "- Jupyter\n"
            "- Github Actions\n"
            "- Elasticsearch / Kibana\n"
            "- Caddy / NGINX\n"
            "- Terraform"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "EPITECH - European Institute of Technology",
        "title": "DevOps Teacher",
        "contract_type": "Freelance",
        "site": "Montpellier",
        "start": date(2020, 9, 1),
        "end": date(2022, 6, 30),
        "duration": "1 yr 10 mos",
        "mission_label": (
            "Teaching DevOps modules to students in first, second and third years of their "
            "bachelor degree."
        ),
        "mission": (
            "Teaching DevOps modules to students in first, second and third years of their "
            "bachelor degree.\n"
            "One of the best ways for me to contribute and share what I am learning from my "
            "work with my different clients is to share it directly with students.\n"
            "My goal is to help them learn everything needed to be prepared for real-world "
            "situations through EPITECH projects. The main topics are:\n"
            "- Docker\n"
            "- CI/CD\n"
            "- Kubernetes"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "KeyOpsTech",
        "title": "Cloud Engineer / DevOps Consultant",
        "contract_type": "Freelance",
        "site": "Lyon, Auvergne-Rhône-Alpes, France",
        "start": date(2020, 2, 1),
        "end": date(2021, 9, 30),
        "duration": "1 yr 8 mos",
        "mission_label": (
            "Cloud and DevOps consulting for KeyOpsTech clients."
        ),
        "mission": (
            "- Google Cloud Platform\n"
            "- EKS\n"
            "- GitlabCI"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "TrackIt",
        "title": "Cloud Engineer / DevOps Consultant",
        "contract_type": "Freelance",
        "site": "California, United States",
        "start": date(2019, 10, 1),
        "end": date(2021, 6, 30),
        "duration": "1 yr 9 mos",
        "mission_label": (
            "Working remotely for US-based clients."
        ),
        "mission": (
            "Working remotely for US-based clients.\n"
            "Stack:\n"
            "- AWS (EC2, VPC, Lambda, CloudWatch, S3, ECS, Cloudformation API Gateway, IAM, "
            "SQS, etc ...)\n"
            "- Terraform / Terragrunt\n"
            "- Kubernetes (EKS)\n"
            "- Packer\n"
            "- DataDog\n"
            "- PagerDuty\n"
            "- Apache Airflow (Deployed on EKS)"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "MyNotary - Lajuristech",
        "title": "DevOps Engineer & Lead Software Engineer & Associate",
        "contract_type": None,
        "site": "Greater Lyon Area",
        "start": date(2016, 9, 1),
        "end": date(2019, 9, 30),
        "duration": "3 yrs 1 mo",
        "mission_label": (
            "Infrastructure, full-stack development, and iOS application delivery at MyNotary."
        ),
        "mission": (
            "When I joined MyNotary they were only 4 peoples working there, the confounders "
            "actually.\n"
            "My first mission at MyNotary was to deploy a new infrastructure, allowing us to do:\n"
            "- Zero Downtime Deployment\n"
            "- File replication\n"
            "- Database replication\n"
            "- High Availability\n"
            "- Easily backup and restore the whole infrastructure\n"
            "So I deployed Rancher on a multitude of dedicated servers (present in different "
            "datacenters). The file replication is handled by GlusterFS and the database "
            "replication by Postgresql-BDR.\n"
            "After that mission, I worked as a Full Stack developer on the web application, "
            "powered by AngularJS and Restlet (A Java framework). I also created the first "
            "version of the iOS application of MyNotary using a \"Clean\" architecture.\n"
            "I also deployed Logstash, Elasticsearch and Kibana to improve our monitoring and "
            "to do Business Intelligence. We wanted to be able to see our KPIs in real-time, "
            "so I wrote a set of program to link our PostgreSQL to the Elasticsearch server.\n"
            "Today, I am leading a side project, for which we raised funds. Managing a team of "
            "2 people, scheduling tasks, reviewing work and taking part myself in the "
            "development.\n"
            "We are now a team of 19 people working here at MyNotary, after two successful "
            "fundraising, to make the real estate revolution happen, here in France."
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "Bress Healthcare",
        "title": "System Administrator & DevOps",
        "contract_type": None,
        "site": "Remote, United Kingdom",
        "start": date(2016, 3, 1),
        "end": date(2016, 9, 30),
        "duration": "7 mos",
        "mission_label": (
            "Deployed the whole infrastructure for Bress Healthcare while completing an MSc "
            "in Network and Networks Security at the University of Kent."
        ),
        "mission": (
            "While doing my MSc in Network and Networks Security at the University of Kent "
            "in the UK, I wanted to work on a challenging, professional project. So, I worked "
            "for Bress Healthcare as a Freelancer, remotely from the UK.\n"
            "At Bress Healthcare my main mission was to deploy the whole infrastructure, "
            "bearing in mind that I would have to deal with sensitive data. I choose to give "
            "it a go with Rancher, as they needed to upgrade the infrastructure quickly.\n"
            "The technical stack:\n"
            "- Rancher / Docker\n"
            "- NodeJS / AngularJS\n"
            "- MongoDB\n"
            "- HAProxy"
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "Etix Everywhere",
        "title": "Software Developer",
        "contract_type": None,
        "site": "Luxembourg",
        "start": date(2015, 4, 1),
        "end": date(2015, 8, 31),
        "duration": "5 mos",
        "mission_label": (
            "Building a web-based Building Management System for modular data centre "
            "operations."
        ),
        "mission": (
            "Etix Everywhere is a company based in Luxembourg, specialised in building modular "
            "data centres, allowing businesses to scale their physical infrastructure following "
            "their growth.\n"
            "I joined the web team, with the mission of building a web-based Building "
            "Management System.\n"
            "The technical stack on which I was working was:\n"
            "- Yii PHP framework\n"
            "- AngularJS\n"
            "- Redis\n"
            "- Docker\n"
            "- Jenkins\n"
            "During the internship, I was assigned to a new project. I had to write an SQL "
            "Proxy using Go (Golang), that will take the context of each request, and replicate "
            "them in the corresponding customer's data centre. This was a very interesting and "
            "challenging project, that I particularly liked."
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "IONIS Education Group",
        "title": "Teaching Assistant",
        "contract_type": None,
        "site": "Greater Montpellier Metropolitan Area",
        "start": date(2014, 9, 1),
        "end": date(2015, 3, 31),
        "duration": "7 mos",
        "mission_label": (
            "Mentoring freshmen and ensuring the quality of lecture contents."
        ),
        "mission": (
            "Being part of a small group of teaching assistant to mentor freshmen.\n"
            "My main role within the team was to ensure the good quality of lectures contents.\n"
            "Application of IONIS's pedagogy:\n"
            "- Giving lectures to first and second-year students.\n"
            "- Giving them advice and tips on their projects.\n"
            "- Monitoring their examinations.\n"
            "- Correcting and marking their projects.\n"
            "- Writing reports on their issues.\n"
            "Teaching:\n"
            "- Data structures & Algorithms.\n"
            "- Unix system programming with C Language.\n"
            "- Object-Oriented Software with C++ language.\n"
            "- Unix system administration.\n"
            "- Functional programming with OCaml.\n"
            "- Graphic bases with X11."
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "Human Coders",
        "title": "Human Talks Organizer",
        "contract_type": None,
        "site": "Greater Montpellier Metropolitan Area",
        "start": date(2014, 7, 1),
        "end": date(2015, 2, 28),
        "duration": "8 mos",
        "mission_label": (
            "Organizing monthly Human Talks developer meetups in Montpellier."
        ),
        "mission": (
            "The Human Talks are monthly events (taking place in most big cities of France), "
            "mainly for developers / by developers, to discover new technology and meet new "
            "people. These events are usually composed of five talks of 10 minutes each, "
            "followed by 5 minutes of questions. With two friends we decided to keep this event "
            "alive, as the previous organizer couldn't continue to maintain it. The Human Talks "
            "were important to us, as we really liked to bring people together, to share their "
            "knowledge and to build new relations."
        ),
        "skills": [],
    },
    {
        "person": ("Maxime", "Jublou"),
        "organization": "iD2i Groupe DFM",
        "title": "Web Developer - Software Engineer - Intern",
        "contract_type": None,
        "site": "Greater Avignon Area",
        "start": date(2013, 7, 1),
        "end": date(2013, 12, 31),
        "duration": "6 mos",
        "mission_label": (
            "First internship after a year at EPITECH, leading client project delivery."
        ),
        "mission": (
            "ID2I is a small company, building web services for clients. This was my first "
            "internship after a year at EPITECH. During the first month, I got to sharpen my "
            "PHP skills and worked on multiple projects. Then I was in charge of the "
            "development of a whole new project for a new client. I had to do the conception, "
            "meetings with the client, the development of the project and then the delivery. "
            "The client was very satisfied with what we delivered. It was very rewarding to "
            "be given such responsibilities that quickly."
        ),
        "skills": [],
    },
]

ANTHONY_EXPERIENCES = [
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "Goodweek",
        "title": "Ingénieur logiciel senior",
        "contract_type": "Permanent",
        "site": "Remote",
        "start": date(2026, 4, 1),
        "end": None,
        "duration": "5 mos",
        "mission_label": (
            "Senior software engineering role at Goodweek."
        ),
        "mission": "Senior software engineering role at Goodweek.",
        "skills": [],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "naas.ai",
        "title": "Lead Developer Frontend",
        "contract_type": "Freelance",
        "site": "Remote",
        "start": date(2024, 2, 1),
        "end": date(2026, 3, 31),
        "duration": "2 yrs 2 mos",
        "mission_label": (
            "Naas.ai construit une plateforme universelle ouverte mêlant données et IA."
        ),
        "mission": (
            "Naas.ai construit une plateforme universelle ouverte mêlant données et IA. "
            "L'objectif est d'aider n'importe quelle organisation à créer son propre "
            "écosystème d'assistants IA, en s'appuyant sur des ontologies comme terrain "
            "unificateur entre données, modèles, workflows, analytics et systèmes externes.\n"
            "Missions :\n"
            "- Réécrire des parties cruciales de l'application pour passer du POC à la prod\n"
            "- Aider l'équipe à appliquer et définir les best practices et les guidelines "
            "de l'application\n"
            "- Concevoir et développer des interfaces utilisateurs lisibles et efficaces.\n"
            "- Refondre l'application en Web App orientée ontologies et événements.\n"
            "Stack : React, TypeScript, Ontologies, Graph architecture, AI workflows, Node.js, "
            "Python"
        ),
        "skills": ["Design d'interface utilisateur", "TypeScript"],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "GoSpot.me",
        "title": "Software Developer",
        "contract_type": "Freelance",
        "site": "Remote",
        "start": date(2024, 3, 1),
        "end": date(2024, 5, 31),
        "duration": "3 mos",
        "mission_label": (
            "GoSpot.me est une agence immobilière parisienne qui propose un service en ligne "
            "de recherche de biens grâce à un système de matching."
        ),
        "mission": (
            "GoSpot.me est une agence immobilière parisienne qui propose un service en ligne "
            "de recherche de biens grâce à un système de matching avec les biens gérés par "
            "l'agence.\n"
            "Grâce à un produit low-code, l'agence permet à ses clients de définir une "
            "recherche précise et d'obtenir des notifications quand un bien correspondant est "
            "matché.\n"
            "Missions :\n"
            "- Créer l'algorithme de matching\n"
            "- Créer le système de notification"
        ),
        "skills": ["JavaScript", "Airtable"],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "MyNotary - Lajuristech",
        "title": "Fullstack Web Developer",
        "contract_type": "Permanent",
        "site": "Lyon, Auvergne-Rhône-Alpes, France",
        "start": date(2017, 7, 1),
        "end": date(2023, 11, 30),
        "duration": "6 yrs 5 mos",
        "mission_label": (
            "MyNotary est une plateforme de mise en relation entre les différents participants "
            "opérant lors d'une vente d'un bien immobilier."
        ),
        "mission": (
            "MyNotary est une plateforme de mise en relation entre les différents participants "
            "opérant lors d'une vente d'un bien immobilier. Elle permet la fluidification des "
            "échanges entre les parties, une rédaction collaborative et la signature "
            "électronique de contrats sécurisant pour les clients.\n"
            "Missions :\n"
            "- Piloter la migration progressive de l'app AngularJs vers ReactJs\n"
            "- Concevoir et développer de nouvelles fonctionnalités métier tout en assurant "
            "maintenance, support et déploiements\n"
            "- Refondre l'API Java vers NodeJs/NestJS pour homogénéiser les stacks et accélérer "
            "la livraison\n"
            "- Industrialiser la qualité : mise en place de tests unitaires/E2E (Jest, "
            "Playwright), guidelines UI/UX et design system\n"
            "- Collaborer avec les équipes produit et juridiques pour traduire les besoins "
            "réglementaires en parcours digitaux"
        ),
        "skills": ["Design d'interface utilisateur", "TypeScript"],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "MyNotary - Lajuristech",
        "title": "Fullstack Mobile Developer",
        "contract_type": "Permanent",
        "site": "Lyon, Auvergne-Rhône-Alpes, France",
        "start": date(2017, 7, 1),
        "end": date(2019, 8, 31),
        "duration": "2 yrs 2 mos",
        "mission_label": (
            "Développement d'applications mobiles Android et iOS pour la plateforme MyNotary."
        ),
        "mission": (
            "Dans la continuité de la plateforme MyNotary, l'objectif était de rendre "
            "l'expérience plus accessible au plus grand nombre. Le développement "
            "d'applications mobiles Android et iOS devenait essentiel pour fluidifier les "
            "interactions entre utilisateurs, simplifier les parcours et permettre un usage "
            "plus naturel lors des échanges, signatures et consultations de documents.\n"
            "Missions :\n"
            "- Concevoir et structurer les applications mobiles Android/iOS pour rendre "
            "accessibles les fonctionnalités clés de la plateforme.\n"
            "- Créer des interfaces utilisateur intuitives et esthétiques en collaboration "
            "avec l'équipe design, basées sur les retours clients et l'analyse des usages.\n"
            "- Développer des applications mobiles performantes en appliquant les bonnes "
            "pratiques techniques et une architecture inspirée de la Clean Architecture pour "
            "assurer scalabilité et maintenabilité.\n"
            "- Organiser des sessions d'échange avec les utilisateurs afin d'identifier les "
            "besoins, prioriser les améliorations et ajuster les parcours en continu.\n"
            "- Mettre en place des outils analytiques avancés afin de comprendre les "
            "comportements utilisateurs et guider les décisions produit.\n"
            "- Contribuer à l'amélioration stratégique de l'expérience mobile globale en "
            "intégrant des retours terrain et en optimisant les parcours existants."
        ),
        "skills": ["Design d'interface utilisateur", "Swift"],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "WeeSurf",
        "title": "Développeur Android",
        "contract_type": "Internship",
        "site": "Ville de Paris",
        "start": date(2016, 4, 1),
        "end": date(2016, 9, 30),
        "duration": "6 mos",
        "mission_label": (
            "Weesurf est une application mobile communautaire dédiée au surf."
        ),
        "mission": (
            "Weesurf est une application mobile communautaire dédiée au surf permettant de "
            "découvrir et partager des spots, équipements et bons plans. La plateforme "
            "s'appuie sur une carte interactive recensant plusieurs milliers de points "
            "d'intérêt liés à l'univers du surf et propose des fonctionnalités sociales "
            "(profils, abonnements, partage de contenus).\n"
            "Missions :\n"
            "- Concevoir et développer l'application Android native from scratch, en "
            "s'appuyant sur l'application iOS existante comme référence fonctionnelle\n"
            "- Définir l'architecture technique de l'application et assurer l'intégration avec "
            "l'API backend Ruby on Rails\n"
            "- Implémenter une carte interactive à grande échelle (≈3000 points d'intérêt) "
            "avec clustering et optimisation du rendu en fonction du viewport pour garantir de "
            "bonnes performances\n"
            "- Développer les fonctionnalités sociales de la plateforme : profils utilisateurs, "
            "système de suivi (follow) et partage de contenus\n"
            "- Gérer le processus de build et de déploiement Android jusqu'à la mise en "
            "production\n"
            "- Accompagner et former un second développeur sur la stack et les bonnes "
            "pratiques Android"
        ),
        "skills": [],
    },
    {
        "person": ("Anthony", "Chevallier"),
        "organization": "Petit Comptoir Français",
        "title": "Développeur web",
        "contract_type": "Internship",
        "site": "Remote",
        "start": date(2014, 7, 1),
        "end": date(2014, 12, 31),
        "duration": "6 mos",
        "mission_label": (
            "Petit Comptoir Français est un service d'abonnement gastronomique mettant en "
            "avant les spécialités régionales françaises."
        ),
        "mission": (
            "Petit Comptoir Français est un service d'abonnement gastronomique mettant en "
            "avant les spécialités régionales françaises à travers des coffrets mensuels, un "
            "site e-commerce et des contenus éditoriaux autour de l'œnotourisme et de la "
            "culture culinaire.\n"
            "Missions :\n"
            "- Reprendre et internaliser la gestion d'un site e-commerce PrestaShop "
            "initialement maintenu par une agence externe\n"
            "- Migrer la plateforme vers un hébergement dédié afin d'améliorer la maîtrise "
            "technique, les performances et la fiabilité du service\n"
            "- Développer des modules PrestaShop en PHP pour répondre aux besoins métier "
            "spécifiques de la plateforme d'abonnement\n"
            "- Concevoir et intégrer des thèmes et personnalisations front-end (HTML, CSS, "
            "JavaScript) pour adapter l'expérience utilisateur\n"
            "- Automatiser certaines tâches d'exploitation et de déploiement via scripts Bash"
        ),
        "skills": ["PrestaShop", "PHP"],
    },
]

MARTIN_EXPERIENCES = [
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Capgo",
        "title": "Solo Maker",
        "contract_type": "Self-employed",
        "site": "Estonia · Remote",
        "start": date(2021, 12, 1),
        "end": None,
        "duration": "4 yrs 9 mos",
        "mission_label": (
            "Live updates for Capacitor — unlock continuous delivery for your application."
        ),
        "mission": (
            "The concept:\n"
            "Live updates for Capacitor!\n"
            "Unlock continuous delivery for your application. Ship live updates, bug fixes, "
            "content changes, features and more without struggling with the App store review.\n"
            "Context:\n"
            "As part of the Forgr projects, I needed to quickly update the apps I was building "
            "for myself and my clients. With no viable solution for my scale, I decided to build "
            "it.\n"
            "50M+ devices monthly using our system\n"
            "The stack:\n"
            "- supabase\n"
            "- vuejs\n"
            "- ionic\n"
            "- capacitor"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Solos Podcast",
        "title": "Host",
        "contract_type": "Self-employed",
        "site": "Estonia · Remote",
        "start": date(2022, 12, 1),
        "end": None,
        "duration": "3 yrs 9 mos",
        "mission_label": (
            "A podcast on building a successful business as a solopreneur."
        ),
        "mission": (
            "The concept:\n"
            "Starting a business is not easy. Starting a business alone is even harder and it "
            "can often feel lonely in the process.\n"
            "With SOLOS, we remind ourselves that there are many solo creators out there and we "
            "are no longer alone.\n"
            "In this podcast, I'll discover how to create a successful business as a "
            "solopreneur, share my own solo creative journey, and hopefully make some friends "
            "along the way.\n"
            "One episode every week.\n"
            "https://solos.ventures\n"
            "Background:\n"
            "I created the concept from scratch by nesting as much as possible. I source the "
            "guest, and shoot the episodes, the rest I have an editor.\n"
            "The stack:\n"
            "- Rode wireless GO II\n"
            "- Riverside FM\n"
            "- Anchor\n"
            "- youtube"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "INDIE MAKERS",
        "title": "Podcaster",
        "contract_type": "Self-employed",
        "site": "Paris",
        "start": date(2019, 9, 1),
        "end": date(2025, 1, 31),
        "duration": "5 yrs 5 mos",
        "mission_label": (
            "Podcasts with Makers who have transformed their ideas into a thriving business."
        ),
        "mission": (
            "The concept:\n"
            "Here you will find podcasts where I chat with Makers who have transformed their "
            "ideas into a thriving business.\n"
            "Beyond their success story, we will decipher their history, their strategy, their "
            "challenges, in order to understand how they managed to become profitable.\n"
            "Every week, I interview different types of Makers, novices, seasoned, always in "
            "order to understand how they got started and how they made their business "
            "sustainable.\n"
            "Context:\n"
            "I created the concept from scratch based on the work of indie hackers in the US. "
            "I source the guests, summarize and build the podcast site.\n"
            "https://indiemakers.fr\n"
            "The stack:\n"
            "- Rode wireless GO II\n"
            "- Riverside FM\n"
            "- Anchor\n"
            "- vuejs/nuxt\n"
            "- firebase"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "naas.ai",
        "title": "CTO",
        "contract_type": "Recurring Status",
        "site": "Everywhere",
        "start": date(2020, 12, 1),
        "end": date(2024, 12, 31),
        "duration": "4 yrs 1 mo",
        "mission_label": (
            "Notebooks-as-a-service for data geeks — open source core team."
        ),
        "mission": (
            "Notebooks-as-a-service for data geeks.\n"
            "Naas helps you script faster with low-code Python formulas, and automate all your "
            "tasks in minutes.\n"
            "Open Source Core-Team — building the universal notebooks-as-a-service platform."
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Captime.app",
        "title": "Solo Maker",
        "contract_type": "Self-employed",
        "site": "Paris, Île-de-France, France",
        "start": date(2018, 1, 1),
        "end": date(2024, 1, 31),
        "duration": "6 yrs 1 mo",
        "mission_label": (
            "CapTime — the perfect timer for professional athletes and Crossfit training."
        ),
        "mission": (
            "Le concept :\n"
            "Always wanted to have your Crossfit Gym Timer in your pocket? It's now possible!\n"
            "Discover CapTime, the perfect timer for professional athletes looking for a high "
            "functionnal and straightforward timer. This new Captime version has been recently "
            "given a facelift allowing you to reach your top performance during your trainings.\n"
            "Context :\n"
            "Inside the scope of Forgr, we created this paid app, the goal was to reproduce "
            "the experience of the timer present in the crossfit box, but in your pocket.\n"
            "More than 20k downloads\n"
            "Paid app\n"
            "App with innovative voice control\n"
            "Stack :\n"
            "- firebase\n"
            "- angular\n"
            "- ionic\n"
            "- capacitor"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Forgr",
        "title": "Forge MVP for startups early stage",
        "contract_type": "Permanent",
        "site": "Estonia",
        "start": date(2017, 2, 1),
        "end": date(2024, 1, 31),
        "duration": "7 yrs",
        "mission_label": (
            "Turn startup ideas into reality with a minimum viable product for mobile."
        ),
        "mission": (
            "The concept:\n"
            "We can help you turn your idea into reality with a minimum viable product (MVP) "
            "for mobile.\n"
            "Save time, money and limit risks with a simplified version of your product that "
            "only includes the key features!\n"
            "You can therefore test it with your target audience or present it directly to "
            "investors. We are building systems that can be scaled up so that you can gain "
            "valuable knowledge and funding to further develop yourself. It's time to find out "
            "how strong your idea is.\n"
            "Background:\n"
            "As part of Forgr projects, I manage clients, prospects, developers and designers "
            "to lead the completion of projects in record time of 4 weeks.\n"
            "The stack:\n"
            "- firebase\n"
            "- angular\n"
            "- ionic\n"
            "- aws"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Bootstrapped family",
        "title": "Member - 1st batch - rank #2",
        "contract_type": "Permanent",
        "site": "Remote",
        "start": date(2022, 2, 1),
        "end": date(2022, 3, 31),
        "duration": "2 mos",
        "mission_label": (
            "Member of the biggest community of ambitious bootstrapped entrepreneurs."
        ),
        "mission": (
            "The biggest community of ambitious bootstrapped entrepreneurs to grow a profitable "
            "business."
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Timeleft",
        "title": "CTO",
        "contract_type": "Permanent",
        "site": "Paris",
        "start": date(2021, 5, 1),
        "end": date(2021, 9, 30),
        "duration": "5 mos",
        "mission_label": (
            "Timeleft — l'application pour réaliser ses rêves via une bucketlist sociale."
        ),
        "mission": (
            "Le concept :\n"
            "Timeleft est l'application pour réaliser ses rêves ! Fais ta bucketlist et rencontre "
            "d'autres personnes qui ont réalisé ce rêve, partage avec eux et tes rêves "
            "deviendrons des objectifs et des super souvenir !\n"
            "Contexte :\n"
            "J'ai rejoint l'équipe pour mener le développement avec l'agence et mener l'équipe "
            "vers une potentielle levé de fond.\n"
            "La stack :\n"
            "- react native\n"
            "- firebase"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Bucephal Digital",
        "title": "CTO",
        "contract_type": "Freelance",
        "site": "Madeira Island, Portugal",
        "start": date(2021, 4, 1),
        "end": date(2021, 7, 31),
        "duration": "4 mos",
        "mission_label": (
            "Bucephal — fond of fond algorithmic trading in cryptocurrency."
        ),
        "mission": (
            "Le concept :\n"
            "Bucephal est un found of found, et algorithmic found dans les cryptomonnaie. "
            "J'ai rejoint l'équipe dans le but de rendre les processus tech super stable.\n"
            "Contexte :\n"
            "J'ai crée toute la nouvelle stack technique, les process et former les équipes aux "
            "meilleures pratiques techniques.\n"
            "Dans le but d'avoir des process infaillible qui permet aux équipes de dormir "
            "paisiblement pendant que les algorithmes travaillent pour eux\n"
            "La stack :\n"
            "- python\n"
            "- docker\n"
            "- docker-composte\n"
            "- Google cloud"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "CashStory",
        "title": "CTO Associate",
        "contract_type": "Permanent",
        "site": "Greater Paris Metropolitan Region",
        "start": date(2018, 12, 1),
        "end": date(2021, 3, 31),
        "duration": "2 yrs 4 mos",
        "mission_label": (
            "Modern environment to migrate Excel financial files to python via jupyter."
        ),
        "mission": (
            "The concept:\n"
            "Create a modern environment as close as possible to the old Excel financial files "
            "to migrate them to python via jupyter and automate their workflow to apply the DRY "
            "principle (don't repeat yourself) to the world of finance.\n"
            "Context:\n"
            "CTO of CashStory I created and implemented the entire service galaxy of our "
            "financial data pipeline, all in docker and kubernet.\n"
            "Our galaxy is more than 50 docker machines\n"
            "The stack:\n"
            "- JupyterLab increased by our library, which allows among other things to "
            "automate (CRON) and call notebooks via API\n"
            "- FTP connected to Jupyter users controlled by house API\n"
            "- BOB workspace which brings together all of our services and who knows how to "
            "chat with them on the front via secure message iframe or back via API, the "
            "workspace works LOGINLESS for the services that accompany it.\n"
            "(Angular, .Net, mySQL)\n"
            "- Wekan, to manage tasks on data workflow\n"
            "- Filestash to access our ftp via web interface\n"
            "- Graphana for internal metrics in the galaxy\n"
            "- Mongo, prometheus, postgres, redis, snowflake for database\n"
            "- Toucan toco to view data at the end of the chain\n"
            "- Caddy server for SSL certificates and http / 2 by default"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "LK Stats",
        "title": "INDIE MAKER",
        "contract_type": "Permanent Part-time",
        "site": "Paris, Île-de-France, France",
        "start": date(2020, 2, 1),
        "end": date(2021, 1, 31),
        "duration": "1 yr",
        "mission_label": (
            "Lk Stats helps you understand the numbers behind your LinkedIn activity."
        ),
        "mission": (
            "The concept:\n"
            "Lk Stats helps you to understand the numbers behind your LinkedIn activity. so "
            "you can reach a much bigger audience with your content.\n"
            "Context:\n"
            "By dint of doing social selling articles on Linkedin, I found myself confronting "
            "the lack of data, to analyze my ROI, on my posts, not wanting to pay 40 euro per "
            "month for that I created a tool for me and made it public\n"
            "The stack:\n"
            "- vuejs\n"
            "- firebase\n"
            "- puppeteer"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Fairwai",
        "title": "Technical Lead",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2018, 5, 1),
        "end": date(2019, 1, 31),
        "duration": "9 mos",
        "mission_label": (
            "Web app for commercial proposition with integrated chat and chatbot."
        ),
        "mission": (
            "The concept :\n"
            "Web app for Commercial proposition with integrated chat + chat bot to facilitate "
            "the sale and analysis of reading the proposition.\n"
            "Background :\n"
            "As part of Forgr projects, after building the Fairwai MVP I took the technical "
            "lead of the platform to take into account user feedback and build the Fairwai V2.\n"
            "The stack :\n"
            "- Firebase\n"
            "- AWS lambda\n"
            "- Angular\n"
            "- Dialogflow"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Wild Code School",
        "title": "Web teacher | project leader",
        "contract_type": None,
        "site": "La loupe",
        "start": date(2018, 2, 1),
        "end": date(2018, 8, 31),
        "duration": "7 mos",
        "mission_label": (
            "Intensive web developer training — become a developer in 5 months."
        ),
        "mission": (
            "The concept:\n"
            "Intensive web developer training: become a developer in 5 months and learn to "
            "code in Javascript. Training which leads to the professional title \"Web and Web "
            "Mobile Developer\" (equivalent Bac + 2), registered with RNCP.\n"
            "Context:\n"
            "Trainer during a 5 month session in the web developer profession mainly on "
            "javascript techno.\n"
            "I have acquired the status of jury approved by the RNCP title \"Web and Web "
            "Developer\"\n"
            "The stack:\n"
            "- Angular\n"
            "- NodeJS\n"
            "- MongoDB\n"
            "- Express\n"
            "- Extreme Programming\n"
            "- project management\n"
            "- lead development\n"
            "- TDD\n"
            "- good practices\n"
            "- technical watch\n"
            "- communication\n"
            "- team work\n"
            "- crisis management"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Toucan Toco",
        "title": "QA engineer",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2017, 6, 1),
        "end": date(2017, 11, 30),
        "duration": "6 mos",
        "mission_label": (
            "First QA engineer — set up testing and test automation practices."
        ),
        "mission": (
            "The concept:\n"
            "Simply visualize your data in business with our data storytelling solution. Make "
            "informed decisions through our application, available on mobile, tablets and pc.\n"
            "Context:\n"
            "I joined Toucan Toco first engineer for quality assurance (QA), my goal was to set "
            "up, good practice of testing and test automation, it was a particular challenge "
            "because Toucan Toco is a fully configurable solution. This mission I failed, "
            "End-to-End testing, in a non-constant environment is a big challenge, in addition "
            "to the human challenge that it represents to engage people on in-depth testing.\n"
            "I made the decision with them to end our trial period and advise them to empower "
            "each developer in this mission rather than appointing a manager, and this solution "
            "is still the one in place with them today.\n"
            "The stack:\n"
            "- End to End Test nightwatchjs\n"
            "- Angularjs\n"
            "- Docker\n"
            "- vuejs\n"
            "- Python\n"
            "- CircleCI\n"
            "- Ansible"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "you2you",
        "title": "Lead Dev mobile application",
        "contract_type": None,
        "site": "Paris Area, France",
        "start": date(2016, 7, 1),
        "end": date(2017, 7, 31),
        "duration": "1 yr 1 mo",
        "mission_label": (
            "Creation of the delivery application, from prototype to production."
        ),
        "mission": (
            "The concept:\n"
            "Rethink your customers' delivery!\n"
            "- Urban storage.\n"
            "Our urban storage points allow us to act on a short circuit.\n"
            "- A digital customer journey.\n"
            "Give your customers the opportunity to choose their delivery window.\n"
            "- 100% green deliveries.\n"
            "Our deliveries are made by our fleet of bicycle couriers.\n"
            "- Superior quality.\n"
            "Our packages are hand delivered against signature.\n"
            "Context:\n"
            "Creation of the delivery application, from prototype to production.\n"
            "List of deliveries available, followed in real time by the deliverers, selection "
            "and notifications of the most suitable deliverers, signature in the app, rating of "
            "the deliverers.\n"
            "Over 30,000 downloads of the app in 1 year.\n"
            "Over 2000 active users per month.\n"
            "Rated 4.6 on blinds over 500 ratings\n"
            "The stack:\n"
            "- Ionic\n"
            "- Cordova\n"
            "- Angularjs\n"
            "- Nodejs\n"
            "- GULP\n"
            "- SCSS,\n"
            "- pm2"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "you2you",
        "title": "Free-lance FullStack Telecommuting",
        "contract_type": None,
        "site": "Helsinki Metropolitan Area",
        "start": date(2015, 8, 1),
        "end": date(2016, 7, 31),
        "duration": "1 yr",
        "mission_label": (
            "First developer from Finland — MVP in 3 days and platform migration in one week."
        ),
        "mission": (
            "The concept:\n"
            "Rethink your customers' delivery!\n"
            "- Urban storage.\n"
            "Our urban storage points allow us to act on a short circuit.\n"
            "- A digital customer journey.\n"
            "Give your customers the opportunity to choose their delivery window.\n"
            "- 100% green deliveries.\n"
            "Our deliveries are made by our fleet of bicycle couriers.\n"
            "- Superior quality.\n"
            "Our packages are hand delivered against signature.\n"
            "Context:\n"
            "I joined You2you as the first developer from Finland, I arrived when the "
            "management of deliveries was done on google sheets and it was necessary to migrate "
            "on a webapp to have a better follow-up of the deliverers.\n"
            "So I developed the MVP in 3 days, which allowed us to migrate the users on my "
            "platform in one week, join TheFamily and raise our first funds on loan from VC.\n"
            "I then structured the platform, created an API, chose the NodeJs, AngularJs, "
            "Grunt, Bootstrap techno.\n"
            "I implemented the You2You business API which is still in production.\n"
            "I administer the servers\n"
            "I recruit the first 5 developers to help me build more tools to manage our "
            "processes.\n"
            "The stack:\n"
            "- Angularjs\n"
            "- Nodejs\n"
            "- GULP\n"
            "- SCSS,\n"
            "- pm2"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Bress",
        "title": "Lead Dev in hacker house",
        "contract_type": "Full-time",
        "site": "Montpellier Area, France",
        "start": date(2014, 7, 1),
        "end": date(2015, 6, 30),
        "duration": "1 yr",
        "mission_label": (
            "Digitalisation of orthoptist tools and first telemedicine prototype in France."
        ),
        "mission": (
            "The concept:\n"
            "- Digitalisation of orthoptist tools (5000 users out of 7000 practitioners), then "
            "creations of the first telemedicine prototype in France.\n"
            "Bress is initially an Epitech Innovative Project\n"
            "Bress brings together designers, developers and healthcare professionals.\n"
            "In this context, we are developing innovative solutions for doctors.\n"
            "Ultimately Bress aims to reshape the way doctors work, by providing them with "
            "\"turnkey\" solutions in the cloud.\n"
            "Context:\n"
            "- Starting from a student project towards an entrepreneurship project, I implemented "
            "technical solutions according to needs, I selected tools to increase the team's "
            "efficiency, organize sessions work, create and assign tickets with the product "
            "owner.\n"
            "I implemented the Agile method, TDD and SCRUM.\n"
            "I integrate the CNIL standard\n"
            "I implemented the modular programming method\n"
            "I created the first Bress application\n"
            "The stack:\n"
            "- nodeJS\n"
            "- AngularJS\n"
            "- redine\n"
            "- gitlab"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Epitech Montpellier",
        "title": "Assisting Epitech Region (AER)",
        "contract_type": "Part-time",
        "site": "Greater Montpellier Metropolitan Area",
        "start": date(2014, 2, 1),
        "end": date(2015, 2, 28),
        "duration": "1 yr 1 mo",
        "mission_label": (
            "Support students in difficulty and organize technical events at Epitech."
        ),
        "mission": (
            "The concept:\n"
            "The benchmark school for IT expertise has been training the experts who will "
            "shape the world of tomorrow for 20 years.\n"
            "A school accessible to everyone from 18 years old\n"
            "A unique active pedagogy that forges personalities\n"
            "An international ecosystem\n"
            "High impact careers\n"
            "Context:\n"
            "- Create and implement effective solutions for students in difficulty\n"
            "- Meeting with students in difficulty during their internship\n"
            "- Creation of a project adapted to students in difficulty\n"
            "- Implementation of tools for students (test server, site hosting)\n"
            "- Organization of a Summer camps to introduce high school students to development.\n"
            "- Technical support for first and second year students.\n"
            "- Organization of conferences on the discovery of new technology for the Epitech "
            "Innovation Hub\n"
            "- Project correction during the defense.\n"
            "The stack:\n"
            "- empathy\n"
            "- teamwork\n"
            "- c\n"
            "- c ++\n"
            "- shell"
        ),
        "skills": [],
    },
    {
        "person": ("Martin", "Donadieu"),
        "organization": "Creoze",
        "title": "Project manager",
        "contract_type": None,
        "site": "Montpellier Area, France",
        "start": date(2012, 6, 1),
        "end": date(2014, 7, 31),
        "duration": "2 yrs 2 mos",
        "mission_label": (
            "First entrepreneurial project — agency site, client delivery, and commercial "
            "prospecting."
        ),
        "mission": (
            "The concept:\n"
            "Creoze embodies the new media generation: Internet, mobile and social networks "
            "are now part of all communication strategies.\n"
            "Creoze brings together the experience, creativity and technicality of our team to "
            "stand out in the market.\n"
            "Context:\n"
            "First entrepreneurial project, with a childhood friend, I created the company site, "
            "participated in financial management and commercial prospecting, made contracts, "
            "invoices and created sites for clients with the wordpress CMS.\n"
            "The stack:\n"
            "- wordpress\n"
            "- php"
        ),
        "skills": [],
    },
]

VALENTIN_EXPERIENCES = [
    {
        "person": ("Valentin", "Piquard"),
        "organization": "Acolad group",
        "title": "Strategic Account Manager",
        "contract_type": "Permanent",
        "site": "Remote",
        "start": date(2024, 12, 1),
        "end": None,
        "duration": "1 yr 9 mos",
        "mission_label": (
            "Strategic account management at Acolad group."
        ),
        "mission": "Strategic account management at Acolad group.",
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "HubSpot",
        "title": "Account Executive SMB",
        "contract_type": None,
        "site": "Remote",
        "start": date(2023, 1, 1),
        "end": date(2024, 12, 31),
        "duration": "2 yrs",
        "mission_label": (
            "Account executive for SMB customers at HubSpot."
        ),
        "mission": "Account executive for SMB customers at HubSpot.",
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "CashStory",
        "title": "Associate",
        "contract_type": None,
        "site": "France",
        "start": date(2020, 1, 1),
        "end": date(2022, 12, 31),
        "duration": "3 yrs",
        "mission_label": (
            "Associate at CashStory."
        ),
        "mission": "Associate at CashStory.",
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "naas.ai",
        "title": "Head of Growth - Associate",
        "contract_type": "Permanent",
        "site": "France",
        "start": date(2020, 1, 1),
        "end": date(2022, 12, 31),
        "duration": "3 yrs",
        "mission_label": (
            "Associate & co-founder — Data Science Notebooks as a Service."
        ),
        "mission": (
            "Associate & co-founder\n"
            "Data Science Notebooks as a Service : make data science accessible to anyone "
            "using low-code templates\n"
            "→ Aiming to reduce as much as possible the time to value for users\n"
            "➡️ Outbound & Inbound Sales\n"
            "➡️ User relationship\n"
            "➡️ Sales automation"
        ),
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "TransPerfect",
        "title": "Account Executive",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(2018, 2, 1),
        "end": date(2019, 12, 31),
        "duration": "1 yr 11 mos",
        "mission_label": (
            "Account executive at TransPerfect."
        ),
        "mission": (
            "Navigate the global marketplace with TransPerfect business solutions."
        ),
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "TransPerfect",
        "title": "Account Manager",
        "contract_type": None,
        "site": "Paris",
        "start": date(2017, 2, 1),
        "end": date(2018, 1, 31),
        "duration": "1 yr",
        "mission_label": (
            "Account manager at TransPerfect, 1 Rue Paul Cézanne, 75008 Paris."
        ),
        "mission": (
            "Account manager at TransPerfect, 1 Rue Paul Cézanne, 75008 Paris."
        ),
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "TF1 Events",
        "title": "Business Developer",
        "contract_type": None,
        "site": "Boulogne-Billancourt, Île-de-France, France",
        "start": date(2016, 9, 1),
        "end": date(2016, 12, 31),
        "duration": "4 mos",
        "mission_label": (
            "Business development at TF1 Events."
        ),
        "mission": "Business development at TF1 Events.",
        "skills": [],
    },
    {
        "person": ("Valentin", "Piquard"),
        "organization": "Canal+",
        "title": "Compte clé junior Grands Comptes",
        "contract_type": None,
        "site": "Paris, France",
        "start": date(2015, 7, 1),
        "end": date(2015, 12, 31),
        "duration": "6 mos",
        "mission_label": (
            "Junior key account manager for Grands Comptes at Canal+."
        ),
        "mission": (
            "Compte clé junior Grands Comptes at Canal+, Région de Paris, France."
        ),
        "skills": [],
    },
]

CHRISTOPHE_EXPERIENCES = [
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Crunchyroll",
        "title": "Vice President Technology Partnerships & R&D @ Sony Pictures Entertainment",
        "contract_type": None,
        "site": "San Diego, California, United States",
        "start": date(2023, 11, 1),
        "end": None,
        "duration": "2 yrs 10 mos",
        "mission_label": (
            "Technology partnerships and R&D leadership at Crunchyroll / Sony Pictures "
            "Entertainment."
        ),
        "mission": (
            "Technology partnerships and R&D leadership at Crunchyroll / Sony Pictures "
            "Entertainment."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Oriane",
        "title": "Board Advisor",
        "contract_type": None,
        "site": "Remote",
        "start": date(2025, 8, 1),
        "end": None,
        "duration": "1 yr 1 mo",
        "mission_label": "Board advisor at Oriane.",
        "mission": "Board advisor at Oriane.",
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Invexa (ex Jaylo)",
        "title": "Board Advisor",
        "contract_type": None,
        "site": "San Diego, California, United States",
        "start": date(2023, 9, 1),
        "end": None,
        "duration": "3 yrs",
        "mission_label": "Board advisor at Invexa (ex Jaylo).",
        "mission": "Board advisor at Invexa (ex Jaylo).",
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "naas.ai",
        "title": "Board Advisor",
        "contract_type": None,
        "site": "Paris, Île-de-France, France",
        "start": date(2022, 1, 1),
        "end": None,
        "duration": "4 yrs 8 mos",
        "mission_label": "Board advisor at naas.ai.",
        "mission": "Board advisor at naas.ai.",
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Netflix",
        "title": "Head of Partner Experiences",
        "contract_type": None,
        "site": "Los Gatos, California, United States",
        "start": date(2015, 2, 1),
        "end": date(2023, 9, 30),
        "duration": "8 yrs 8 mos",
        "mission_label": (
            "Led a large global team managing product enablement with over 500 partners "
            "worldwide."
        ),
        "mission": (
            "I lead a large global team managing product enablement with over 500 partners "
            "worldwide, working to innovate on joint products and creating impactful "
            "go-to-market strategies for Streaming/Live, Payment, Cloud Games and Ad "
            "services. I drive innovation and product development with internal Netflix teams "
            "and leading technology providers in the ecosystem.\n"
            "Co-innovate with partners and influence partners' roadmaps.\n"
            "- Grew Netflix active living room devices from 50M to 500M.\n"
            "- Grew Netflix member billing via partners' payment to 15% of total Netflix "
            "billing\n"
            "- First deployment ever on SmartTV, and at scale, of new technologies such as "
            "4K, HDR, Voice.\n"
            "- Worked with industry leaders, such as ARM, Broadcom, Google, Samsung and many "
            "others, to redefine SmartTV HW and SW architecture for no-rebuffers and low "
            "latency.\n"
            "- Introduced new and innovative data science based, in-field monitoring systems, "
            "improving device reliability by over 25% and making Netflix the most reliable "
            "streaming app on TV.\n"
            "Partners advocate within Netflix.\n"
            "- Balanced business needs and partner capital, with investments and ROI.\n"
            "Scale teams globally.\n"
            "- Grew my team from 10 to over 120 and set up offices in Taiwan, Singapore, "
            "Amsterdam, São Paulo and the US.\n"
            "- Received 2022 best employee survey score across all Netflix engineering for team "
            "trust in Leadership.\n"
            "Build platforms, reference designs, A/V automation systems.\n"
            "- Enabled positive ROI for long tail partners through innovative turnkey "
            "solutions that later became a reference for Google.\n"
            "Deliver and integrate SDKs and API based solutions with partners.\n"
            "- Full lifecycle management for Device integration and Partner Payment systems "
            "integration\n"
            "- Over 1.5B devices enabled, over 500M monitored."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Hisense Group",
        "title": "Hisense USA CTO & Hisense/Flextronics Joint Venture President",
        "contract_type": None,
        "site": "Toronto, Ontario, Canada",
        "start": date(2011, 10, 1),
        "end": date(2015, 1, 31),
        "duration": "3 yrs 4 mos",
        "mission_label": (
            "Led strategic partnership with Roku and built the Hisense/Flextronics Joint "
            "Venture for Vidaa."
        ),
        "mission": (
            "I led a strategic partnership with Roku that drove Hisense to become the #1 "
            "Chinese OEM in the US and I established key partnerships with Netflix, Amazon, "
            "YouTube.\n"
            "I built, from the ground up, a Joint Venture between Hisense and Flextronics to "
            "design and launch Vidaa, a new smartTV concept for the Chinese market. Vidaa "
            "quickly became the leading Smart TV UI in China and it is Hisense's global Smart "
            "TV solution."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Flextronics Computing",
        "title": "Vice President",
        "contract_type": None,
        "site": "Toronto, Ontario, Canada",
        "start": date(2010, 2, 1),
        "end": date(2012, 9, 30),
        "duration": "2 yrs 8 mos",
        "mission_label": (
            "Led incubator teams that created the SmartTV platform concept for the Jamdeo "
            "joint venture."
        ),
        "mission": (
            "Led the Flextronics incubator teams that put forward the concept for a new "
            "SmartTV platform and UI that became the base for the Joint Venture (Jamdeo) "
            "between Flextronics and Hisense."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "SKY MobileMedia",
        "title": "Chief Operating Officer",
        "contract_type": None,
        "site": "San Diego County, California, United States",
        "start": date(2007, 5, 1),
        "end": date(2008, 12, 31),
        "duration": "1 yr 8 mos",
        "mission_label": (
            "Strategy and operations for Sky MobileMedia, a smartphone UI and middleware "
            "startup."
        ),
        "mission": (
            "I was responsible for strategy and operations for Sky MobileMedia, a startup "
            "delivering UI and middleware SW for smartphones. Sky MobileMedia was subsequently "
            "acquired by Flextronics, our key partner."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Quorum Systems",
        "title": "Board Advisor",
        "contract_type": None,
        "site": "San Diego County, California, United States",
        "start": date(2006, 1, 1),
        "end": date(2008, 12, 31),
        "duration": "2 yrs",
        "mission_label": (
            "Board advisor at Quorum Systems, a fabless semiconductor RF transceiver company."
        ),
        "mission": (
            "Quorum Systems was a fabless semiconductor company developing and delivering "
            "integrated single-chip CMOS radio frequency transceivers.\n"
            "Quorum Systems was acquired by Spreadtrum communication."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Broken Windows (movie)",
        "title": "Executive Producer",
        "contract_type": None,
        "site": "Los Angeles Metropolitan Area",
        "start": date(2006, 11, 1),
        "end": date(2007, 7, 31),
        "duration": "9 mos",
        "mission_label": (
            "Executive Producer of the feature film Broken Windows."
        ),
        "mission": (
            "Took a career break from tech and media to serve as Executive Producer of the "
            "feature film Broken Windows, overseeing end-to-end production and delivery.\n"
            "Collaborated with a diverse team to ensure creative vision and project goals were "
            "met.\n"
            "Managed distribution partnerships, leading to successful releases on Netflix and "
            "HBO Eastern Europe.\n"
            "https://www.youtube.com/watch?v=NoOT7fltUQM"
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Texas Instruments",
        "title": "General Manager 3G Wireless Business Unit",
        "contract_type": None,
        "site": "San Diego County, California, United States",
        "start": date(2003, 10, 1),
        "end": date(2006, 11, 30),
        "duration": "3 yrs 2 mos",
        "mission_label": (
            "P&L, R&D and product management for 3G smartphone chipsets at Texas Instruments."
        ),
        "mission": (
            "P&L, R&D and product management responsibility for 3G smartphone chipsets. "
            "Launched the first mobile application and wireless processor combined, "
            "significantly driving down the BOM cost of smartphones."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Texas Instruments",
        "title": "Head of Berlin R&D center",
        "contract_type": None,
        "site": "Berlin, Germany",
        "start": date(2002, 5, 1),
        "end": date(2003, 10, 31),
        "duration": "1 yr 6 mos",
        "mission_label": (
            "Head of Berlin R&D center at Texas Instruments."
        ),
        "mission": "Head of Berlin R&D center at Texas Instruments.",
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Condat",
        "title": "Board Member",
        "contract_type": None,
        "site": "Berlin, Germany",
        "start": date(2002, 5, 1),
        "end": date(2003, 10, 31),
        "duration": "1 yr 6 mos",
        "mission_label": (
            "Board Member of Condat AG supporting the acquisition by Texas Instruments."
        ),
        "mission": (
            "Board Member of Condat AG supporting the acquisition by Texas Instruments.\n"
            "Condat was bringing to market middleware software for mobile phones."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Symbian PLC",
        "title": "Vice President Of Engineering",
        "contract_type": None,
        "site": "London Area, United Kingdom",
        "start": date(2000, 1, 1),
        "end": date(2002, 12, 31),
        "duration": "3 yrs",
        "mission_label": (
            "Led Symbian Smartphone OS engineering teams and supported the first global "
            "smartphones by Nokia and Ericsson."
        ),
        "mission": (
            "Led the Symbian Smartphone OS engineering teams. Supported the launch of the first "
            "two global smartphones by Nokia and Ericsson. Represented Symbian at the "
            "shareholders technical board."
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "NEC Technologies UK",
        "title": "General Manager - UK Mobile Phone R&D",
        "contract_type": None,
        "site": "Greater Reading Area",
        "start": date(1995, 1, 1),
        "end": date(2000, 12, 31),
        "duration": "6 yrs",
        "mission_label": (
            "Led NEC UK R&D teams developing GSM phones for the EU market."
        ),
        "mission": (
            "Led NEC UK R&D teams developing GSM phones for the EU market. Shipped products "
            "to tier-one operators in EU, Asia and Africa"
        ),
        "skills": [],
    },
    {
        "person": ("Christophe", "Jouin"),
        "organization": "Alcatel-Lucent",
        "title": "Project Manager",
        "contract_type": None,
        "site": "Greater Paris Metropolitan Region",
        "start": date(1991, 1, 1),
        "end": date(1995, 12, 31),
        "duration": "5 yrs",
        "mission_label": (
            "Led protocol stack software development for early GSM phones at Alcatel-Lucent."
        ),
        "mission": (
            "Led the protocol stack software development teams for one of the first 4 GSM "
            "phones ever to be launched and then led the SW project for Alcatel second "
            "generation of GSM phones."
        ),
        "skills": [],
    },
]

EXPERIENCES = (
    FLORENT_EXPERIENCES
    + JEREMY_EXPERIENCES
    + MAXIME_EXPERIENCES
    + ANTHONY_EXPERIENCES
    + MARTIN_EXPERIENCES
    + VALENTIN_EXPERIENCES
    + CHRISTOPHE_EXPERIENCES
    + ALEXIS_EXPERIENCES
)
