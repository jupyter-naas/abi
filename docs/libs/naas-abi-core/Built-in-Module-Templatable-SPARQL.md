# Built-in Module: Templatable SPARQL

`naas_abi_core.modules.templatablesparqlquery` is auto-included by engine configuration if missing.

Related pages: [[Module-System]], [[services/Triple-Store]].

## Purpose

It reads ontology-driven `TemplatableSparqlQuery` definitions from the triple store and turns them into runtime workflows/tools.

## What it loads

- Query label and description.
- SPARQL template.
- Query arguments with validation metadata.

Then it dynamically builds:

- a Pydantic argument model per templated query
- a `GenericWorkflow` runnable
- a `StructuredTool` per workflow (`workflow.as_tools()`)

## Runtime timing

The module initializes in `on_initialized()`, after triple store and ontologies are loaded.

## Why it matters

This module provides a bridge from ontology-declared query intents to executable tools without hard-coding each workflow in Python.
