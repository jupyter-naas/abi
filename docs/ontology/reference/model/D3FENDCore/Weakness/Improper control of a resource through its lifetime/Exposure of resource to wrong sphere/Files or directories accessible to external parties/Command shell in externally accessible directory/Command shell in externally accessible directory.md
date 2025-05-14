# Command shell in externally accessible directory

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-553

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-553(Command<br>shell<br>in<br>externally<br>accessible<br>directory):::d3fend-->d3fend.owl#CWE-552
    d3fend.owl#CWE-552(Files<br>or<br>directories<br>accessible<br>to<br>external<br>parties):::d3fend-->d3fend.owl#CWE-668
    d3fend.owl#CWE-668(Exposure<br>of<br>resource<br>to<br>wrong<br>sphere):::d3fend-->d3fend.owl#CWE-664
    d3fend.owl#CWE-664(Improper<br>control<br>of<br>a<br>resource<br>through<br>its<br>lifetime):::d3fend-->d3fend.owl#Weakness
    d3fend.owl#Weakness(Weakness):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md)
- [Improper control of a resource through its lifetime](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20control%20of%20a%20resource%20through%20its%20lifetime.md)
- [Exposure of resource to wrong sphere](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Exposure%20of%20resource%20to%20wrong%20sphere.md)
- [Files or directories accessible to external parties](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Files%20or%20directories%20accessible%20to%20external%20parties/Files%20or%20directories%20accessible%20to%20external%20parties.md)
- [Command shell in externally accessible directory](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Exposure%20of%20resource%20to%20wrong%20sphere/Files%20or%20directories%20accessible%20to%20external%20parties/Command%20shell%20in%20externally%20accessible%20directory/Command%20shell%20in%20externally%20accessible%20directory.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

