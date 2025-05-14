# Struts: duplicate validation forms

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-102

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-102(Struts:<br>duplicate<br>validation<br>forms):::d3fend-->d3fend.owl#CWE-694
    d3fend.owl#CWE-694(Use<br>of<br>multiple<br>resources<br>with<br>duplicate<br>identifier):::d3fend-->d3fend.owl#CWE-99
    d3fend.owl#CWE-99(Improper<br>control<br>of<br>resource<br>identifiers<br>('resource<br>injection')):::d3fend-->d3fend.owl#CWE-74
    d3fend.owl#CWE-74(Improper<br>neutralization<br>of<br>special<br>elements<br>in<br>output<br>used<br>by<br>a<br>downstream<br>component<br>('injection')):::d3fend-->d3fend.owl#CWE-707
    d3fend.owl#CWE-707(Improper<br>neutralization):::d3fend-->d3fend.owl#Weakness
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
- [Improper neutralization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization.md)
- [Improper neutralization of special elements in output used by a downstream component ('injection')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements%20in%20output%20used%20by%20a%20downstream%20component%20%28%27injection%27%29/Improper%20neutralization%20of%20special%20elements%20in%20output%20used%20by%20a%20downstream%20component%20%28%27injection%27%29.md)
- [Improper control of resource identifiers ('resource injection')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements%20in%20output%20used%20by%20a%20downstream%20component%20%28%27injection%27%29/Improper%20control%20of%20resource%20identifiers%20%28%27resource%20injection%27%29/Improper%20control%20of%20resource%20identifiers%20%28%27resource%20injection%27%29.md)
- [Use of multiple resources with duplicate identifier](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements%20in%20output%20used%20by%20a%20downstream%20component%20%28%27injection%27%29/Improper%20control%20of%20resource%20identifiers%20%28%27resource%20injection%27%29/Use%20of%20multiple%20resources%20with%20duplicate%20identifier/Use%20of%20multiple%20resources%20with%20duplicate%20identifier.md)
- [Struts: duplicate validation forms](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20neutralization/Improper%20neutralization%20of%20special%20elements%20in%20output%20used%20by%20a%20downstream%20component%20%28%27injection%27%29/Improper%20control%20of%20resource%20identifiers%20%28%27resource%20injection%27%29/Use%20of%20multiple%20resources%20with%20duplicate%20identifier/Struts%3A%20duplicate%20validation%20forms/Struts%3A%20duplicate%20validation%20forms.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

