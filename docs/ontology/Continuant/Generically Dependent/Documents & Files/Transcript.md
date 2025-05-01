# Transcript

## Definition
A transcript is a generically dependent continuant that provides a verbatim or summarized textual representation of spoken dialogue captured during a conversation.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Transcript(abi:Transcript):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:MeetingNote** - A generically dependent continuant that documents key points and decisions from a scheduled discussion.
- **abi:Report** - A generically dependent continuant that communicates structured analysis or findings about a specific topic.
- **abi:Presentation** - A generically dependent continuant that structures arrangements of messages or claims meant to inform, persuade, or explain in a time-bound setting. 