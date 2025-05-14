# Improper neutralization of directives in dynamically evaluated code ('eval injection')

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-95

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-95(Improper<br>neutralization<br>of<br>directives<br>in<br>dynamically<br>evaluated<br>code<br>('eval<br>injection')):::d3fend-->d3fend.owl#CWE-94
    d3fend.owl#CWE-94(Improper<br>control<br>of<br>generation<br>of<br>code<br>('code<br>injection')):::d3fend-->d3fend.owl#CWE-913
    d3fend.owl#CWE-913(Improper<br>control<br>of<br>dynamically-managed<br>code<br>resources):::d3fend-->d3fend.owl#CWE-664
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
- [Improper control of dynamically-managed code resources](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20control%20of%20dynamically-managed%20code%20resources/Improper%20control%20of%20dynamically-managed%20code%20resources.md)
- [Improper control of generation of code ('code injection')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20control%20of%20dynamically-managed%20code%20resources/Improper%20control%20of%20generation%20of%20code%20%28%27code%20injection%27%29/Improper%20control%20of%20generation%20of%20code%20%28%27code%20injection%27%29.md)
- [Improper neutralization of directives in dynamically evaluated code ('eval injection')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Improper%20control%20of%20dynamically-managed%20code%20resources/Improper%20control%20of%20generation%20of%20code%20%28%27code%20injection%27%29/Improper%20neutralization%20of%20directives%20in%20dynamically%20evaluated%20code%20%28%27eval%20injection%27%29/Improper%20neutralization%20of%20directives%20in%20dynamically%20evaluated%20code%20%28%27eval%20injection%27%29.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

