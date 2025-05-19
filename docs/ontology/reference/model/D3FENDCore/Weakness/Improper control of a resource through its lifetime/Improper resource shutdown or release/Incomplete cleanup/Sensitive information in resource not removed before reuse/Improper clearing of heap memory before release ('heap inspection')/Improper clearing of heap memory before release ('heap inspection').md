# Improper clearing of heap memory before release ('heap inspection')

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-244

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-244(Improper<br>clearing<br>of<br>heap<br>memory<br>before<br>release<br>('heap<br>inspection')):::d3fend-->d3fend.owl#CWE-226
    d3fend.owl#CWE-226(Sensitive<br>information<br>in<br>resource<br>not<br>removed<br>before<br>reuse):::d3fend-->d3fend.owl#CWE-459
    d3fend.owl#CWE-459(Incomplete<br>cleanup):::d3fend-->d3fend.owl#CWE-404
    d3fend.owl#CWE-404(Improper<br>resource<br>shutdown<br>or<br>release):::d3fend-->d3fend.owl#CWE-664
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
- [Improper resource shutdown or release](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20resource%20shutdown%20or%20release/Improper%20resource%20shutdown%20or%20release.md)
- [Incomplete cleanup](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20resource%20shutdown%20or%20release/Incomplete%20cleanup/Incomplete%20cleanup.md)
- [Sensitive information in resource not removed before reuse](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20resource%20shutdown%20or%20release/Incomplete%20cleanup/Sensitive%20information%20in%20resource%20not%20removed%20before%20reuse/Sensitive%20information%20in%20resource%20not%20removed%20before%20reuse.md)
- [Improper clearing of heap memory before release ('heap inspection')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20resource%20shutdown%20or%20release/Incomplete%20cleanup/Sensitive%20information%20in%20resource%20not%20removed%20before%20reuse/Improper%20clearing%20of%20heap%20memory%20before%20release%20%28%27heap%20inspection%27%29/Improper%20clearing%20of%20heap%20memory%20before%20release%20%28%27heap%20inspection%27%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

