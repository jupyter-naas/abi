# ConfidenceScore

## Definition
A confidence score is a generically dependent continuant that provides a scalar measure expressing the strength or certainty of a prediction, classification, or evaluation.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_ConfidenceScore(abi:ConfidenceScore):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:TrustScore** - A generically dependent continuant that represents a numerical or ordinal value estimating the perceived reliability of an entity or claim.
- **abi:SentimentScore** - A generically dependent continuant that characterizes the emotional valence of a statement, message, or document.
- **abi:Forecast** - A generically dependent continuant that provides a data projection estimating future states or outcomes based on historical or modeled inputs. 