# ContractDocument

## Definition
A contract document is a generically dependent continuant that expresses the agreed obligations and rights between agents.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_ContractDocument(abi:ContractDocument):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:Report** - A report is a generically dependent continuant that communicates structured analysis or findings about a specific topic.
- **abi:SlideDeck** - A slide deck is a generically dependent continuant that conveys ideas or insights through a sequential set of visual or textual frames.
- **abi:Invoice** - An invoice is a generically dependent continuant that records a payment request for goods or services delivered.