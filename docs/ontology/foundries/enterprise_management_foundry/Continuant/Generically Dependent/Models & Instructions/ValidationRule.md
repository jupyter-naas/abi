# ValidationRule

## Definition
A validation rule is a generically dependent continuant that defines a logical constraint used to check whether data or behavior conforms to expectations.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_ValidationRule(abi:ValidationRule):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:WorkflowSpecification** - A generically dependent continuant that provides a prescriptive plan describing a set of interrelated tasks and their sequence.
- **abi:SPARQLQuery** - A generically dependent continuant that expresses a formal query pattern used to retrieve or manipulate information from a semantic graph.
- **abi:OntologyFile** - A generically dependent continuant that provides a formal encoding of domain-specific concepts, relations, and constraints expressed in a semantic web format. 