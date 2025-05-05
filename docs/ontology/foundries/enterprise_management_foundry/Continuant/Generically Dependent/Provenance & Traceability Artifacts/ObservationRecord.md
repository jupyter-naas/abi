# ObservationRecord

## Definition
An observation record is a generically dependent continuant that provides a traceable record of an observed event or outcome, including its context and agent.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_ObservationRecord(abi:ObservationRecord):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:AuditLogEntry** - A generically dependent continuant that provides a time-stamped trace of an activity performed by an agent, often used for compliance or review.
- **abi:DataLineageStatement** - A generically dependent continuant that documents a chain describing the origin, transformation, and usage of data assets.
- **abi:VersionTag** - A generically dependent continuant that provides a label assigned to a specific state or iteration of a resource.
- **abi:ReviewComment** - A generically dependent continuant that captures a human-authored critique, affirmation, or clarification associated with an entity or decision. 