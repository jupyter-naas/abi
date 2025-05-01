# TrustScore

## Definition
A trust score is a generically dependent continuant that represents a numerical or ordinal value estimating the perceived reliability of an entity or claim.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_TrustScore(abi:TrustScore):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:EngagementMetric** - A generically dependent continuant that reflects the degree of interaction between users and content or campaigns.
- **abi:ConfidenceScore** - A generically dependent continuant that expresses the strength or certainty of a prediction, classification, or evaluation.
- **abi:SentimentScore** - A generically dependent continuant that characterizes the emotional valence of a statement, message, or document. 