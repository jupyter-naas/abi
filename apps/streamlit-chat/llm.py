import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from os import environ

openai_api_key = environ.get("OPENAI_API_KEY")
model = environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

llm = ChatOpenAI(
    openai_api_key=openai_api_key,
    model=model,
)

embeddings = OpenAIEmbeddings(
    openai_api_key=openai_api_key
)
