# Forecast

## Definition
A forecast is a generically dependent continuant that provides a data projection estimating future states or outcomes based on historical or modeled inputs.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Forecast(abi:Forecast):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:ConfidenceScore** - A generically dependent continuant that provides a scalar measure expressing the strength or certainty of a prediction, classification, or evaluation.
- **abi:KPIValue** - A generically dependent continuant that provides a measured outcome that quantifies performance against a defined business objective.
- **abi:EngagementMetric** - A generically dependent continuant that provides a quantifiable measure reflecting the degree of interaction between users and content or campaigns. 