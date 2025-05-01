# VersionTag

## Definition
A version tag is a generically dependent continuant that provides a label assigned to a specific state or iteration of a resource.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_VersionTag(abi:VersionTag):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:DataLineageStatement** - A generically dependent continuant that documents a chain describing the origin, transformation, and usage of data assets.
- **abi:ObservationRecord** - A generically dependent continuant that provides a traceable record of an observed event or outcome, including its context and agent.
- **abi:ReviewComment** - A generically dependent continuant that captures a human-authored critique, affirmation, or clarification associated with an entity or decision. 