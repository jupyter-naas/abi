# Triggers in ABI Modules

## What are Triggers?

Triggers are a powerful feature in the ABI system that enable reactive programming based on changes in the ontology store. They allow modules to register callbacks that are automatically executed when specific RDF triples are added to or removed from the ontology.

A trigger consists of three main components:
1. A **triple pattern** to match against (subject, predicate, object)
2. An **event type** (INSERT or DELETE)
3. A **callback function** to execute when the event occurs

Triggers transform the ontology from a passive data store into a reactive system that can automatically initiate actions when data changes. This creates an "executable ontology" or "reactive ontology" where the knowledge graph itself becomes a mechanism for coordinating system behavior.

## Why Use Triggers?

Triggers provide several key benefits:

1. **Decoupling of Components**: Modules can react to data changes without direct dependencies on each other.
2. **Event-Driven Architecture**: The system becomes more responsive and can automatically initiate processes when relevant data appears.
3. **Simplified Workflows**: Complex multi-step processes can be broken down into smaller, more manageable components that activate in sequence.
4. **Reduced Boilerplate**: No need to manually check for conditions or poll for changes.

## How Triggers Work

When a triple is added to or removed from the ontology store, the system checks if any registered triggers match the affected triple. If a match is found, the associated callback function is executed.

The triple pattern in a trigger can include specific values or `None` wildcards:
- If a specific value is provided, the trigger only matches triples with exactly that value in the corresponding position.
- If `None` is provided, the trigger matches any value in that position.

For example:
- `(ex:Person123, ex:hasProfile, None)` matches any triple with subject `ex:Person123` and predicate `ex:hasProfile`, regardless of the object.
- `(None, rdf:type, ex:LinkedInProfile)` matches any triple with predicate `rdf:type` and object `ex:LinkedInProfile`, regardless of the subject.

## Example Use Case

Consider a LinkedIn profile ingestion workflow:

1. A workflow discovers a person and their LinkedIn profile URL, adding a triple like:
   ```
   ex:Person123 ex:hasLinkedInProfile "https://linkedin.com/in/username"
   ```

2. Instead of having this workflow also handle the profile ingestion, a separate LinkedIn ingestion pipeline registers a trigger:
   ```python
   (None, ex:hasLinkedInProfile, None)  # Match any triple with this predicate
   ```

3. When the triple is added, the trigger automatically activates the LinkedIn ingestion pipeline, which:
   - Retrieves the profile URL
   - Scrapes the LinkedIn profile
   - Processes the data
   - Adds more detailed information to the ontology

This approach keeps each component focused on a single responsibility and allows the system to automatically coordinate complex workflows.

## How to Register Triggers in a Module

Triggers are registered by creating a `triggers.py` file in your module directory. This file should define a `triggers` list variable containing tuples of (triple_pattern, event_type, callback_function).

Here's an example of a `triggers.py` file:

```python
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from rdflib import URIRef
from .pipelines.LinkedInProfileIngestionPipeline import ingest_linkedin_profile

# Define the namespace
ex = URIRef("http://example.org/")

# Define the triple pattern to watch for
# (None, ex:hasLinkedInProfile, None) means "match any subject and object, but the predicate must be ex:hasLinkedInProfile"
triple_pattern = (None, URIRef(ex + "hasLinkedInProfile"), None)

# Define the callback function
def handle_new_linkedin_profile(event_type, ontology_name, triple):
    subject, predicate, profile_url = triple
    ingest_linkedin_profile(subject, profile_url)

# List of triggers to be registered
triggers = [
    (triple_pattern, OntologyEvent.INSERT, handle_new_linkedin_profile)
]
```

## How Triggers are Loaded

The ABI system automatically loads triggers from modules during the module loading process:

1. The system checks if a `triggers.py` file exists in the module directory.
2. If found, it imports the module and looks for a `triggers` variable.
3. If the `triggers` variable exists and is a list, the system registers each trigger with the ontology store.

The relevant code in `Module.py` that handles this process is:

```python
def __load_triggers(self):
    if os.path.exists(os.path.join(self.module_path, 'triggers.py')):
        module = importlib.import_module(self.module_import_path + '.triggers')
        if hasattr(module, 'triggers'):
            self.triggers = module.triggers
```

## Best Practices for Using Triggers

1. **Be Specific**: Make your triple patterns as specific as possible to avoid unnecessary callback executions.
2. **Keep Callbacks Lightweight**: Trigger callbacks should be quick and focused. For complex operations, consider having the callback initiate a separate process.
3. **Handle Errors Gracefully**: Ensure your callback functions include proper error handling to prevent failures from affecting the ontology store.
4. **Document Your Triggers**: Clearly document what triggers your module registers and what they do.
5. **Avoid Circular Triggers**: Be careful not to create circular dependencies where triggers create conditions that activate other triggers indefinitely.

## Advanced Usage: Trigger Patterns

Here are some common patterns for using triggers effectively:

### Wildcard Matching

Use `None` as a wildcard to match any value in a triple position:

```python
# Match any triple with rdf:type as predicate and ex:Person as object
(None, RDF.type, ex.Person)
```

### Chain Reactions

Create a chain of triggers where each step in a process triggers the next:

```python
# Step 1: Detect new LinkedIn profile
(None, ex.hasLinkedInProfile, None)

# Step 2: After profile data is ingested, analyze connections
(None, ex.hasConnection, None)

# Step 3: After connections are analyzed, generate recommendations
(None, ex.hasAnalyzedNetwork, None)
```

### Conditional Processing

Use triggers to implement conditional logic based on the ontology state:

```python
# Only process profiles that have both LinkedIn and Twitter
def process_if_complete(event_type, ontology_name, triple):
    subject, _, _ = triple
    # Query to check if this subject also has Twitter
    if has_twitter_profile(subject):
        process_complete_profile(subject)

# Register the trigger
(None, ex.hasLinkedInProfile, None, OntologyEvent.INSERT, process_if_complete)
```

## Conclusion

Triggers are a powerful mechanism in the ABI system that enable reactive, event-driven programming based on changes in the ontology. By registering callbacks to respond to specific triple patterns, modules can create sophisticated workflows that automatically react to new information as it becomes available.

This approach helps keep the codebase modular, maintainable, and focused on specific responsibilities while allowing complex behaviors to emerge from the interaction of simple components.
