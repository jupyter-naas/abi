"""
Oxigraph Administrative Interface
Provides terminal-based management and monitoring for Oxigraph triple store
"""

from src.core.modules.abi.apps.oxigraph_admin.terminal_style import (
    clear_screen,
    print_welcome_message,
    print_divider,
    get_user_input,
    print_status_info,
    print_error_message,
    print_success_message,
    print_menu_options,
)
import subprocess
import requests

from src import services
from rich.table import Table
from rich.console import Console

console = Console()

class OxigraphAdmin:
    def __init__(self):
        self.oxigraph_url = "http://localhost:7878"
        self.triple_store_service = services.triple_store_service
        self.query_templates = self._init_query_templates()

    def _init_query_templates(self):
        """Initialize SPARQL query templates for common exploration tasks"""
        return {
            "1": {
                "name": "📊 Data Overview - Entity Types & Counts",
                "description": "Show all entity types and their counts",
                "query": """SELECT DISTINCT ?type (COUNT(*) AS ?count) WHERE {
    ?s a ?type
} GROUP BY ?type ORDER BY DESC(?count)"""
            },
            "2": {
                "name": "🏗️ Class Hierarchy - Top Level Classes",
                "description": "Show top-level OWL classes in the ontology",
                "query": """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?class ?label WHERE {
    ?class a owl:Class .
    OPTIONAL { ?class rdfs:label ?label }
    FILTER NOT EXISTS { ?class rdfs:subClassOf ?parent }
} ORDER BY ?label LIMIT 20"""
            },
            "3": {
                "name": "🔗 Property Relations - Object Properties",
                "description": "Explore object properties and their domains/ranges",
                "query": """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?property ?label ?domain ?range WHERE {
    ?property a owl:ObjectProperty .
    OPTIONAL { ?property rdfs:label ?label }
    OPTIONAL { ?property rdfs:domain ?domain }
    OPTIONAL { ?property rdfs:range ?range }
} ORDER BY ?label LIMIT 20"""
            },
            "4": {
                "name": "👥 ABI Entities - System Components",
                "description": "Show ABI-specific entities and components",
                "query": """PREFIX abi: <http://ontology.naas.ai/abi#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?entity ?type ?label WHERE {
    ?entity ?p ?o .
    FILTER(STRSTARTS(STR(?entity), "http://ontology.naas.ai/abi"))
    OPTIONAL { ?entity a ?type }
    OPTIONAL { ?entity rdfs:label ?label }
} LIMIT 30"""
            },
            "5": {
                "name": "🧠 Intent Mapping - System Components",
                "description": "Explore intent mapping system components",
                "query": """PREFIX intent: <http://ontology.naas.ai/intentMapping#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?intent ?label ?description WHERE {
    ?intent ?p ?o .
    FILTER(STRSTARTS(STR(?intent), "http://ontology.naas.ai/intentMapping"))
    OPTIONAL { ?intent rdfs:label ?label }
    OPTIONAL { ?intent rdfs:comment ?description }
} LIMIT 20"""
            },
            "6": {
                "name": "🌐 Namespace Analysis - Data Distribution",
                "description": "Analyze data distribution across namespaces",
                "query": """SELECT ?namespace (COUNT(*) AS ?triples) WHERE {
    ?s ?p ?o .
    BIND(REPLACE(STR(?s), "(#|/)[^#/]*$", "$1") AS ?namespace)
} GROUP BY ?namespace ORDER BY DESC(?triples) LIMIT 15"""
            },
            "7": {
                "name": "🔍 Custom Search - Find by Term",
                "description": "Search for entities containing a specific term",
                "query": """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?entity ?label ?type WHERE {
    ?entity ?p ?o .
    ?entity rdfs:label ?label .
    OPTIONAL { ?entity a ?type }
    FILTER(CONTAINS(LCASE(STR(?label)), "SEARCH_TERM"))
} LIMIT 20"""
            }
        }

    def check_oxigraph_health(self):
        """Check if Oxigraph is running and accessible"""
        try:
            response = requests.get(f"{self.oxigraph_url}/query?query=SELECT%20%3Fs%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D%20LIMIT%201", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_triple_count(self):
        """Get the total number of triples in the store"""
        try:
            results = self.triple_store_service.query("SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }")
            result_list = list(results)
            if result_list:
                return int(result_list[0].count)
        except Exception:
            pass
        return 0

    def get_class_count(self):
        """Get the number of OWL classes"""
        try:
            results = self.triple_store_service.query("""
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT (COUNT(DISTINCT ?class) AS ?count) WHERE { 
                    ?class a owl:Class 
                }
            """)
            result_list = list(results)
            if result_list:
                return int(result_list[0].count)
        except Exception:
            pass
        return 0

    def get_property_count(self):
        """Get the number of properties"""
        try:
            results = self.triple_store_service.query("""
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                SELECT (COUNT(DISTINCT ?prop) AS ?count) WHERE { 
                    { ?prop a owl:ObjectProperty } UNION 
                    { ?prop a owl:DatatypeProperty }
                }
            """)
            result_list = list(results)
            if result_list:
                return int(result_list[0].count)
        except Exception:
            pass
        return 0

    def display_dashboard(self):
        """Display the main dashboard"""
        clear_screen()
        print_welcome_message("🧠 Oxigraph Administrative Interface")
        
        # Health check
        is_healthy = self.check_oxigraph_health()
        if is_healthy:
            print_status_info("✅ Oxigraph is running and accessible")
        else:
            print_error_message("❌ Oxigraph appears to be down or unreachable")
            return

        print_divider()

        # Statistics
        console.print("📊 [bold bright_cyan]Knowledge Graph Statistics[/bold bright_cyan]")
        
        stats_table = Table(show_header=True, header_style="bold magenta")
        stats_table.add_column("Metric", style="cyan", no_wrap=True)
        stats_table.add_column("Count", style="green", justify="right")
        
        triple_count = self.get_triple_count()
        class_count = self.get_class_count()
        property_count = self.get_property_count()
        
        stats_table.add_row("Total Triples", f"{triple_count:,}")
        stats_table.add_row("OWL Classes", f"{class_count:,}")
        stats_table.add_row("Properties", f"{property_count:,}")
        stats_table.add_row("Endpoint", self.oxigraph_url)
        
        console.print(stats_table)
        print_divider()

    def query_templates_menu(self):
        """Query template exploration menu"""
        clear_screen()
        console.print("🗂️  Query Templates - Explore Your Knowledge Graph", style="bold bright_cyan")
        print_divider()

        # Show available templates
        console.print("Available Templates:", style="bold bright_white")
        for key, template in self.query_templates.items():
            console.print(f"   {key}. {template['name']}", style="white")
            console.print(f"      {template['description']}", style="dim")

        print_divider()

        choice = get_user_input("Select template (1-7) or 'back'")

        if choice.lower() == 'back':
            return
        elif choice in self.query_templates:
            template = self.query_templates[choice]
            console.print(f"\n[bold cyan]{template['name']}[/bold cyan]")
            console.print(f"[bright_black]{template['query']}[/bright_black]")

            # Ask if user wants to execute the query
            execute = get_user_input("Execute this query? (y/n)")
            if execute.lower() == 'y':
                try:
                    print_status_info("Executing query...")
                    query = template['query']

                    # Handle custom search template
                    if "SEARCH_TERM" in query:
                        search_term = get_user_input("Enter search term")
                        query = query.replace("SEARCH_TERM", search_term.lower())

                    results = self.triple_store_service.query(query)
                    console.print("[green]Query executed successfully![/green]")
                    console.print(f"[bright_black]{results}[/bright_black]")

                except Exception as e:
                    print_error_message(f"Query execution failed: {e}")

            # Wait for user to review results
            get_user_input("Press Enter to continue...")
        else:
            print_error_message("Invalid template selection")
            get_user_input("Press Enter to continue...")

    def service_control_menu(self):
        """Service control and monitoring"""
        clear_screen()
        console.print("⚙️  Service Control", style="bold bright_cyan")
        print_divider()

        print_menu_options([
            "1. Restart Oxigraph",
            "2. Check Docker status", 
            "3. View Oxigraph logs",
            "4. Back to main menu"
        ])

        choice = get_user_input("Select option")

        if choice == "1":
            print_status_info("Restarting Oxigraph...")
            try:
                subprocess.run(["docker", "compose", "--profile", "dev", "restart", "oxigraph"], check=True)
                print_success_message("Oxigraph restarted successfully")
            except subprocess.CalledProcessError:
                print_error_message("Failed to restart Oxigraph")
                
        elif choice == "2":
            print_status_info("Checking Docker services...")
            try:
                result = subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True)
                console.print(result.stdout)
            except subprocess.CalledProcessError:
                print_error_message("Failed to check Docker status")
                
        elif choice == "3":
            print_status_info("Showing Oxigraph logs...")
            try:
                subprocess.run(["docker", "compose", "logs", "--tail=50", "oxigraph"])
            except subprocess.CalledProcessError:
                print_error_message("Failed to get logs")

        if choice in ["1", "2", "3"]:
            get_user_input("Press Enter to continue...")

    def data_management_menu(self):
        """Data import/export and management"""
        clear_screen()
        console.print("📁 Data Management", style="bold bright_cyan")
        print_divider()

        print_menu_options([
            "1. Show recent changes",
            "2. Export data",
            "3. Data validation",
            "4. Back to main menu"
        ])

        choice = get_user_input("Select option")

        if choice == "1":
            # This would show recent triples or changes
            print_status_info("Feature coming soon...")
            get_user_input("Press Enter to continue...")

    def run(self):
        """Run the Oxigraph admin interface"""
        while True:
            self.display_dashboard()
            
            print_menu_options([
                "1. Refresh dashboard",
                "2. Query templates & examples",
                "3. Service control",
                "4. Data management", 
                "5. Open SPARQL terminal",
                "6. Open YasGUI web interface",
                "7. Open unified Knowledge Graph Explorer",
                "8. Exit"
            ])
            
            choice = get_user_input("Select option")
            
            if choice == "1":
                continue
            elif choice == "2":
                self.query_templates_menu()
            elif choice == "3":
                self.service_control_menu()
            elif choice == "4":
                self.data_management_menu()
            elif choice == "5":
                console.print("Opening SPARQL terminal...")
                subprocess.run(["uv", "run", "python", "-m", "src.core.modules.abi.apps.sparql_terminal.main"])
                break
            elif choice == "6":
                console.print("Opening YasGUI web interface...")
                console.print("Visit: http://localhost:3000")
                break

            elif choice == "7":
                console.print("Opening unified Knowledge Graph Explorer...")
                console.print("Visit: http://localhost:7878/explorer/")
                console.print("Features: Dashboard + iframe YasGUI + Templates + ABI Brain")
                break
            elif choice == "8":
                print_success_message("Goodbye!")
                break


def main():
    admin = OxigraphAdmin()
    admin.run()


if __name__ == "__main__":
    main()