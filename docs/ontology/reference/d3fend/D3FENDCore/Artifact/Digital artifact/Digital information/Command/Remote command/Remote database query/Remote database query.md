# Remote database query

## Overview

### Definition
A remote query session enabling a user to make an SQL, SPARQL, or similar query over the network from one host to another.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#RemoteDatabaseQuery

### Subclass Of
```mermaid
graph BT
    d3fend.owl#RemoteDatabaseQuery(Remote<br>database<br>query):::d3fend-->d3fend.owl#RemoteCommand
    d3fend.owl#RemoteCommand(Remote<br>command):::d3fend-->d3fend.owl#Command
    d3fend.owl#Command(Command):::d3fend-->d3fend.owl#DigitalInformation
    d3fend.owl#DigitalInformation(Digital<br>information):::d3fend-->d3fend.owl#DigitalArtifact
    d3fend.owl#DigitalArtifact(Digital<br>artifact):::d3fend-->d3fend.owl#Artifact
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
- [Digital artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20artifact.md)
- [Digital information](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Digital%20information.md)
- [Command](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Command/Command.md)
- [Remote command](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Command/Remote%20command/Remote%20command.md)
- [Remote database query](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Command/Remote%20command/Remote%20database%20query/Remote%20database%20query.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Data Properties
| Ontology | Label | Definition | Example | Domain | Range |
|----------|-------|------------|---------|--------|-------|
| d3fend | [d3fend-artifact-data-property](http://d3fend.mitre.org/ontologies/d3fend.owl#d3fend-artifact-data-property) | x d3fend-artifact-data-property y: The artifact x has the data property y. |  | [Digital Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20artifact.md) | []() |

### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |  |  | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | []() |

