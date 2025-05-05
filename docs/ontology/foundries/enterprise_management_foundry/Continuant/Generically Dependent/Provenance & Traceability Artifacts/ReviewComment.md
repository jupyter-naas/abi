# ReviewComment

## Definition
A review comment is a generically dependent continuant that captures a human-authored critique, affirmation, or clarification associated with an entity or decision.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_ReviewComment(abi:ReviewComment):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ObservationRecord** - A generically dependent continuant that provides a traceable record of an observed event or outcome, including its context and agent.
- **abi:AuditLogEntry** - A generically dependent continuant that provides a time-stamped trace of an activity performed by an agent, often used for compliance or review.
- **abi:VersionTag** - A generically dependent continuant that provides a label assigned to a specific state or iteration of a resource. 