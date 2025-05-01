# MeetingNote

## Definition
A meeting note is a generically dependent continuant that documents key points and decisions from a scheduled discussion.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_MeetingNote(abi:MeetingNote):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:Transcript** - A generically dependent continuant that provides a verbatim or summarized textual representation of spoken dialogue captured during a conversation.
- **abi:Report** - A generically dependent continuant that communicates structured analysis or findings about a specific topic.
- **abi:Invoice** - A generically dependent continuant that records a payment request for goods or services delivered. 