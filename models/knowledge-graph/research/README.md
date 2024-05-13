# Research Folder Objectives

This "Research" folder is designed for a comparative analysis between system prompts, vector search, and knowledge graph methodologies. 

## Step 1: Creating a Custom Plugin
In the notebook titled "Content_Create_Assistant_plugin", we developed a custom plugin using a specific Google Sheets dataset. For accurate comparison between vector search and knowledge graph, this dataset should contain a maximum of 20 posts. This ensures that the system prompt's scope aligns with that of the vector and knowledge graph, providing a true reflection of the most effective data provision method for the Language Model (LLM).

## Step 2: Pushing Data to Neo4j
In "Neo4j_Push_Content_to_Graph_Database" notebook, we push the same dataset to Neo4j. This feeds the vector search with the same data, maintaining consistency across all methods.

Additional relationships "Concepts", "Sentiments", "ProfessionalRole", "ContentType", "Objectives" have been established with the "Content" node to maximize the use of the Knowledge Graphs.

## Step 3: Comparative Analysis
Finally, in the "QA_Comparative_Analysis" notebook, we undertake the comparative analysis, drawing insights from the data provision methods in steps 1 and 2.