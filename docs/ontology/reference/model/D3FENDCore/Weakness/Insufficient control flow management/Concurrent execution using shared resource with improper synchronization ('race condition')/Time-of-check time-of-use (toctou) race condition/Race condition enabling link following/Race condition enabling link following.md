# Race condition enabling link following

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-363

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-363(Race<br>condition<br>enabling<br>link<br>following):::d3fend-->d3fend.owl#CWE-367
    d3fend.owl#CWE-367(Time-of-check<br>time-of-use<br>(toctou)<br>race<br>condition):::d3fend-->d3fend.owl#CWE-362
    d3fend.owl#CWE-362(Concurrent<br>execution<br>using<br>shared<br>resource<br>with<br>improper<br>synchronization<br>('race<br>condition')):::d3fend-->d3fend.owl#CWE-691
    d3fend.owl#CWE-691(Insufficient<br>control<br>flow<br>management):::d3fend-->d3fend.owl#Weakness
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
- [Insufficient control flow management](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Insufficient%20control%20flow%20management.md)
- [Concurrent execution using shared resource with improper synchronization ('race condition')](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Concurrent%20execution%20using%20shared%20resource%20with%20improper%20synchronization%20%28%27race%20condition%27%29/Concurrent%20execution%20using%20shared%20resource%20with%20improper%20synchronization%20%28%27race%20condition%27%29.md)
- [Time-of-check time-of-use (toctou) race condition](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Concurrent%20execution%20using%20shared%20resource%20with%20improper%20synchronization%20%28%27race%20condition%27%29/Time-of-check%20time-of-use%20%28toctou%29%20race%20condition/Time-of-check%20time-of-use%20%28toctou%29%20race%20condition.md)
- [Race condition enabling link following](/docs/ontology/reference/model/D3FENDCore/Weakness/Insufficient%20control%20flow%20management/Concurrent%20execution%20using%20shared%20resource%20with%20improper%20synchronization%20%28%27race%20condition%27%29/Time-of-check%20time-of-use%20%28toctou%29%20race%20condition/Race%20condition%20enabling%20link%20following/Race%20condition%20enabling%20link%20following.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

