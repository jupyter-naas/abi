# Improper isolation of shared resources on system-on-a-chip (soc)

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1189

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1189(Improper<br>isolation<br>of<br>shared<br>resources<br>on<br>system-on-a-chip<br>(soc)):::d3fend-->d3fend.owl#CWE-653
    d3fend.owl#CWE-653(Improper<br>isolation<br>or<br>compartmentalization):::d3fend-->d3fend.owl#CWE-693
    d3fend.owl#CWE-693(Protection<br>mechanism<br>failure):::d3fend-->d3fend.owl#Weakness
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
- [Protection mechanism failure](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Protection%20mechanism%20failure.md)
- [Improper isolation or compartmentalization](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Improper%20isolation%20or%20compartmentalization/Improper%20isolation%20or%20compartmentalization.md)
- [Improper isolation of shared resources on system-on-a-chip (soc)](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Improper%20isolation%20or%20compartmentalization/Improper%20isolation%20of%20shared%20resources%20on%20system-on-a-chip%20%28soc%29/Improper%20isolation%20of%20shared%20resources%20on%20system-on-a-chip%20%28soc%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

