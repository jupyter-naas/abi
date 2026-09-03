"""Run the Periodic Table ontology graph (pyvis).

    uv run python -m naas_abi.apps.periodic_table
"""

from naas_abi.apps.periodic_table.graph import serve_graph

if __name__ == "__main__":
    serve_graph()
