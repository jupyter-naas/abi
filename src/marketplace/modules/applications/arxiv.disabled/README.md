# ArXiv Agent Module - Standard Operating Procedure

## 1. Purpose and Scope
This document provides standard operating procedures for using the ArXiv Agent module to search, download, analyze, and maintain a knowledge base of scientific papers from ArXiv.org. It covers all operations from basic paper discovery to advanced knowledge graph queries.

## 2. Module Overview
The ArXiv Agent module enables easy interaction with ArXiv's scientific paper repository. It provides a suite of tools to search for papers, extract metadata, build a knowledge graph, and perform complex queries across your personal research library.

## 3. System Components

### 3.1 ArXiv Agent
An intelligent agent that helps users discover, organize, and analyze research papers. The agent integrates all the module's capabilities into a conversational interface.

### 3.2 ArXiv Integration
Connects to the ArXiv API to search for papers and retrieve detailed metadata.

### 3.3 ArXiv Paper Pipeline
Processes papers by:
- Extracting metadata (authors, categories, publication dates, etc.)
- Converting data into a structured knowledge graph
- Storing the graph as TTL files
- Downloading PDF versions of papers

### 3.4 ArXiv Query Workflow
Enables powerful querying capabilities against your stored papers:
- Find authors of specific papers
- Find papers by author or category
- Get frequency analysis of authors
- Execute custom SPARQL queries

## 4. Directory Structure

src/marketplace/modules/arxiv/
- agents/
  • ArXivAssistant.py - Agent implementation
- integrations/
  • ArXivIntegration.py - ArXiv API connection
- ontologies/
  • ArXivOntology.ttl - ArXiv ontology schema
- pipelines/
  • ArXivPaperPipeline.py - Paper processing pipeline
- workflows/
  • ArXivQueryWorkflow.py - Knowledge graph query workflow
- README.md - This documentation

## 5. Data Storage Locations

storage/triplestore/application-level/arxiv/  # TTL metadata files
datastore/application-level/arxiv/            # PDF document files

## 6. Operating Procedures

### 6.1 Starting the ArXiv Agent

From project root directory: 

```
make chat-arxiv-agent
```

### 6.2 Paper Discovery

1. **Basic Search**
   ```
   Search for papers about quantum computing
   ```

2. **Targeted Search**
   ```
   Find papers by Yoshua Bengio about deep learning
   ```
   
3. **Recent Papers Search**
   ```
   What are the latest papers on transformers?
   ```

### 6.3 Paper Storage
1. **Adding Papers to Knowledge Graph**
   ```
   Save paper 2201.08239 to my knowledge graph
   ```
   
2. **Downloading Paper with PDF**
   ```
   Download the PDF for paper 2201.08239
   ```

### 6.4 Knowledge Graph Queries
1. **Paper Author Lookup**
   ```
   Who wrote the paper "Attention Is All You Need"?
   ```

2. **Author's Papers Lookup**
   ```
   What papers do I have by Geoffrey Hinton?
   ```

3. **Category Search**
   ```
   Find papers in the cs.AI category
   ```

4. **Author Frequency**
   ```
   Which authors appear most frequently in my papers?
   ```

### 6.5 Advanced SPARQL Queries
Execute this query:
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?paper ?title WHERE {
?paper a abi:ArXivPaper ;
rdfs:label ?title .


## 7. Troubleshooting

### 7.1 Common Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|---------------|----------|
| Paper not found | Incorrect ID or API error | Verify ID and try again |
| Query returns empty results | No papers stored or query mismatch | Check storage directory for TTL files |
| PDF download fails | Network issue or invalid URL | Check connection and try again |
| SPARQL query error | Syntax error or namespace issue | Ensure proper PREFIX declarations |

### 7.2 Error Messages

| Error Message | Meaning | Action |
|--------------|---------|--------|
| "Unknown namespace prefix" | Missing PREFIX in SPARQL | Add required PREFIX declarations |
| "No TTL files found" | Empty storage directory | Add papers using the pipeline first |
| "Query execution failed" | Malformed SPARQL | Check query syntax |

## 8. Maintenance

### 8.1 File Management
- TTL files are retained indefinitely in the storage directory
- Consider periodically backing up the storage directories
- PDF files can be substantial in size - monitor disk space usage

### 8.2 Updating the Agent
When updating the agent code:
1. Restart the agent after code changes
2. Existing data will remain accessible
3. Test queries against existing data to verify functionality

## 9. References
- ArXiv API Documentation: https://arxiv.org/help/api/
- SPARQL Query Language: https://www.w3.org/TR/sparql11-query/
- RDF Turtle Format: https://www.w3.org/TR/turtle/