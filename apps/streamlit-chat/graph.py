import streamlit as st
from langchain_community.graphs import Neo4jGraph
from os import environ

uri = environ.get("NEO4J_URI")
username = environ.get("NEO4J_USERNAME")
password = environ.get("NEO4J_PASSWORD")

graph = Neo4jGraph(
    url=uri,
    username=username,
    password=password,
)
