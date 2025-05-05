# Presentation

## Definition
A presentation is a generically dependent continuant that structures arrangements of messages or claims meant to inform, persuade, or explain in a time-bound setting.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Presentation(abi:Presentation):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:SlideDeck** - A generically dependent continuant that conveys ideas or insights through a sequential set of visual or textual frames.
- **abi:Report** - A generically dependent continuant that communicates structured analysis or findings about a specific topic.
- **abi:Transcript** - A generically dependent continuant that provides a verbatim or summarized textual representation of spoken dialogue captured during a conversation. 