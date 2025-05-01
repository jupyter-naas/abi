# Policy

## Definition
A policy is a generically dependent continuant that articulates formal guiding principles or rules for decision-making or behavior within a context.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000031(Generically Dependent<br>Continuant):::BFO-->BFO_0000002
    
    ABI_Policy(abi:Policy):::ABI-->BFO_0000031
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Related Classes
- **abi:SOP** - A generically dependent continuant that provides a codified sequence of actions or responsibilities used to standardize recurring procedures.
- **abi:BusinessRule** - A generically dependent continuant that expresses a declarative constraint that governs or influences business behavior.
- **abi:AgreementTerm** - A generically dependent continuant that defines a clause or statement within a contract that specifies duties, restrictions, or conditions.
- **abi:PersonaProfile** - A generically dependent continuant that provides a synthesized information artifact describing the characteristics of a typical or target user.
- **abi:CapabilityModel** - A generically dependent continuant that offers a structured map of functional and enabling capabilities within an enterprise or team. 