# Recommendation

## Definition
A recommendation is a generically dependent continuant that expresses a proposal for action based on observed facts, learned patterns, or reasoning.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Recommendation(abi:Recommendation):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ObservationContent** - A generically dependent continuant that provides a structured representation of an insight or finding derived from an event or process.
- **abi:Idea** - A generically dependent continuant that represents a conceptual unit originating from creative or inferential reasoning.
- **abi:ScoredAnswer** - A generically dependent continuant that provides a response to a question or observation including a value expressing confidence or quality. 