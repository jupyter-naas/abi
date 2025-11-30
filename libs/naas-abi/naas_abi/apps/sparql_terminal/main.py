from naas_abi import services
from naas_abi.apps.sparql_terminal.terminal_style import (
    clear_screen,
    get_user_input,
    print_divider,
    print_query,
    print_query_error,
    print_query_result,
    print_system_message,
    print_welcome_message,
)


class SPARQLTerminal:
    def __init__(self):
        self.triple_store_service = services.triple_store_service

    def execute_query(self, query):
        """Execute a SPARQL query and return the results"""
        try:
            results = self.triple_store_service.query(query)
            return results
        except Exception as e:
            raise Exception(f"Error executing query: {str(e)}")

    def run(self):
        """Run the SPARQL terminal interface"""
        clear_screen()
        print_welcome_message()
        print_divider()

        while True:
            user_input = get_user_input()

            if user_input.lower() == "exit":
                print_system_message("Goodbye!")
                return
            elif user_input.lower() == "help":
                print_welcome_message()
                continue
            elif user_input.lower() == "clear":
                clear_screen()
                continue
            elif not user_input.strip():
                continue

            try:
                # Print the query being executed
                print_query(user_input)
                print_divider()

                # Execute the query and print results
                results = self.execute_query(user_input)
                print_query_result(results)
                print_divider()

            except Exception as e:
                print_query_error(str(e))
                print_divider()


def main():
    terminal = SPARQLTerminal()
    terminal.run()


if __name__ == "__main__":
    main()
