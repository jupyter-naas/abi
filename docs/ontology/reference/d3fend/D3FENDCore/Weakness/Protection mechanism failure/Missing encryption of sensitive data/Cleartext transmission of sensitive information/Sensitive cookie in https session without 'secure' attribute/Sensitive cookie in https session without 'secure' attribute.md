# Sensitive cookie in https session without 'secure' attribute

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-614

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-614(Sensitive<br>cookie<br>in<br>https<br>session<br>without<br>'secure'<br>attribute):::d3fend-->d3fend.owl#CWE-319
    d3fend.owl#CWE-319(Cleartext<br>transmission<br>of<br>sensitive<br>information):::d3fend-->d3fend.owl#CWE-311
    d3fend.owl#CWE-311(Missing<br>encryption<br>of<br>sensitive<br>data):::d3fend-->d3fend.owl#CWE-693
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
- [Missing encryption of sensitive data](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Missing%20encryption%20of%20sensitive%20data/Missing%20encryption%20of%20sensitive%20data.md)
- [Cleartext transmission of sensitive information](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Missing%20encryption%20of%20sensitive%20data/Cleartext%20transmission%20of%20sensitive%20information/Cleartext%20transmission%20of%20sensitive%20information.md)
- [Sensitive cookie in https session without 'secure' attribute](/docs/ontology/reference/model/D3FENDCore/Weakness/Protection%20mechanism%20failure/Missing%20encryption%20of%20sensitive%20data/Cleartext%20transmission%20of%20sensitive%20information/Sensitive%20cookie%20in%20https%20session%20without%20%27secure%27%20attribute/Sensitive%20cookie%20in%20https%20session%20without%20%27secure%27%20attribute.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

