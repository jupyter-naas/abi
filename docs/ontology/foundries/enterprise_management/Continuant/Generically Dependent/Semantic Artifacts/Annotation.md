# Annotation

## Definition
An annotation is a generically dependent continuant that provides a contextual note or label that enriches a resource with additional meaning or reference.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Annotation(abi:Annotation):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:Tag** - A generically dependent continuant that provides a minimal semantic label used to classify, group, or annotate resources.
- **abi:Label** - A generically dependent continuant that represents a natural-language or symbolic designation assigned to an entity to distinguish or describe it.
- **abi:Definition** - A generically dependent continuant that specifies the necessary and sufficient conditions for class membership. 