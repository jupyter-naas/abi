import streamlit as st
from langchain_community.vectorstores.neo4j_vector import Neo4jVector
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import RetrievalQA
from llm import llm, embeddings
from os import environ

uri = environ.get("NEO4J_URI")
username = environ.get("NEO4J_USERNAME")
password = environ.get("NEO4J_PASSWORD")

neo4jvector = Neo4jVector.from_existing_index(
    embeddings,                              # <1>
    url=uri,                                 # <2>
    username=username,                       # <3>
    password=password,                       # <4>
    index_name="content",                    # <5>
    node_label="Content",                    # <6>
    text_node_property=['entity', 'scenario', 'source', 'published_date', 'id', 'title', 'text', 'concept', 'sentiment', 'target', 'objective', 'views', 'likes', 'comments', 'shares', 'engagements', 'engagement_score', 'type', 'author_name', 'author_url', 'length', 'people_mentioned', 'organization_mentioned', 'content_title_shared', 'content_url_shared', 'linkedin_links', 'image_shared', 'tags', 'url', 'date_extract', 'scenario_order'],               # <7>
    embedding_node_property="embedding",     # <8>
)

retriever = neo4jvector.as_retriever()

kg_qa = RetrievalQA.from_chain_type(
    llm,                  # <1>
    chain_type="stuff",   # <2>
    retriever=retriever,  # <3>
)
