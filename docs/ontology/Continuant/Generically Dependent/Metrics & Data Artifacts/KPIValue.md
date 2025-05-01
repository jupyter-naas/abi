# KPIValue

## Definition
A KPI value is a generically dependent continuant that provides a measured outcome that quantifies performance against a defined business objective.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_KPIValue(abi:KPIValue):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:EngagementMetric** - A generically dependent continuant that provides a quantifiable measure reflecting the degree of interaction between users and content or campaigns.
- **abi:Forecast** - A generically dependent continuant that provides a data projection estimating future states or outcomes based on historical or modeled inputs.
- **abi:TrustScore** - A generically dependent continuant that represents a numerical or ordinal value estimating the perceived reliability of an entity or claim. 