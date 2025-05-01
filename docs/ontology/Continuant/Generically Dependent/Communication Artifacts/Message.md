# Message

## Definition
A message is a generically dependent continuant that represents a bounded unit of communication transmitted synchronously or asynchronously between agents.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Message(abi:Message):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ConversationThread** - A generically dependent continuant that captures a sequence of related messages exchanged among participants over time.
- **abi:EmailMessage** - A generically dependent continuant that provides a time-stamped, directed communication artifact used to convey structured or unstructured content between agents.
- **abi:Comment** - A generically dependent continuant that provides a reactive textual note attached to another artifact expressing support, disagreement, or elaboration. 