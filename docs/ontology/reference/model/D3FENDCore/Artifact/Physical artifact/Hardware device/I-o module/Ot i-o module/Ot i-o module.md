# Ot i/o module

## Overview

### Definition
An OT I/O Module is an industrial-grade interface designed for harsh Operational Technology (OT) environments. It reliably connects sensors and actuators to industrial control systems, ensuring precise, real-time data exchange in applications such as SCADA or ICS. Engineered for ruggedness and consistent performance, it can manage analog, digital, or other specialized signal types while enduring demanding conditions.

### Examples
Rockwell Compact 5000 IO Module

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#OTIOModule

### Subclass Of
```mermaid
graph BT
    d3fend.owl#OTIOModule(Ot<br>i-o<br>module):::d3fend-->d3fend.owl#IOModule
    d3fend.owl#IOModule(I-o<br>module):::d3fend-->d3fend.owl#HardwareDevice
    d3fend.owl#HardwareDevice(Hardware<br>device):::d3fend-->d3fend.owl#PhysicalArtifact
    d3fend.owl#PhysicalArtifact(Physical<br>artifact):::d3fend-->d3fend.owl#Artifact
    d3fend.owl#Artifact(Artifact):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md)
- [Physical artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Physical%20artifact.md)
- [Hardware device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Hardware%20device.md)
- [I-o module](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/I-o%20module/I-o%20module.md)
- [Ot i-o module](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/I-o%20module/Ot%20i-o%20module/Ot%20i-o%20module.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |  |  | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | []() |

