# EvidenceReference

## Definition
An evidence reference is a generically dependent continuant that provides a citation or link that supports the credibility or relevance of a claim or observation.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_EvidenceReference(abi:EvidenceReference):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:DecisionExplanation** - A generically dependent continuant that offers a justification that clarifies the logic or rationale behind a specific course of action.
- **abi:ScenarioDescription** - A generically dependent continuant that provides a narrated or structured description of a hypothetical or historical event used for analysis or planning.
- **abi:NormativeStatement** - A generically dependent continuant that expresses a declarative expression prescribing what should be done or valued, rather than what is. 