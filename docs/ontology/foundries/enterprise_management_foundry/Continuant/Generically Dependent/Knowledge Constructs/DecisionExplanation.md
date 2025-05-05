# DecisionExplanation

## Definition
A decision explanation is a generically dependent continuant that offers a justification that clarifies the logic or rationale behind a specific course of action.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_DecisionExplanation(abi:DecisionExplanation):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ScenarioDescription** - A generically dependent continuant that provides a narrated or structured description of a hypothetical or historical event used for analysis or planning.
- **abi:ConceptualModel** - A generically dependent continuant that provides a representation that structures and relates concepts relevant to a domain or system.
- **abi:NormativeStatement** - A generically dependent continuant that expresses a declarative expression prescribing what should be done or valued, rather than what is. 