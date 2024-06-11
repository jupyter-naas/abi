import streamlit as st
from langchain_community.graphs import Neo4jGraph
from os import environ
import pydash

uri = environ.get("NEO4J_URI")
username = environ.get("NEO4J_USERNAME")
password = environ.get("NEO4J_PASSWORD")

graph = Neo4jGraph(
    url=uri,
    username=username,
    password=password,
)

# Logic to initialize the Neo4j graph if it's empty.

count_query = graph.query("""
    MATCH (n)
    RETURN COUNT(n) AS nodeCount            
""")

count_query = pydash.get(count_query, "[0].nodeCount")

if count_query == 0:
    print("⚙️ Populating graph database with sample data...")
    with open('cypher_query/cypher_query.txt', 'r') as file:
        import_query = file.read()
        graph.query(import_query)