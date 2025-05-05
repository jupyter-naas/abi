# Invoice

## Definition
An invoice is a generically dependent continuant that records a payment request for goods or services delivered.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Invoice(abi:Invoice):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ContractDocument** - A generically dependent continuant that expresses the agreed obligations and rights between agents.
- **abi:Report** - A generically dependent continuant that communicates structured analysis or findings about a specific topic.
- **abi:MeetingNote** - A generically dependent continuant that documents key points and decisions from a scheduled discussion. 