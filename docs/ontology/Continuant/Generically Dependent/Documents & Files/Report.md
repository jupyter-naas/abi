# Report

## Definition
A report is a generically dependent continuant that communicates structured analysis or findings about a specific topic.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Report(abi:Report):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ContractDocument** - A generically dependent continuant that expresses the agreed obligations and rights between agents.
- **abi:SlideDeck** - A generically dependent continuant that conveys ideas or insights through a sequential set of visual or textual frames.
- **abi:Presentation** - A generically dependent continuant that structures arrangements of messages or claims meant to inform, persuade, or explain in a time-bound setting.
