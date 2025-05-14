# Improper restriction of rendered ui layers or frames

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1021

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1021(Improper<br>restriction<br>of<br>rendered<br>ui<br>layers<br>or<br>frames):::d3fend-->d3fend.owl#CWE-441
    d3fend.owl#CWE-441(Unintended<br>proxy<br>or<br>intermediary<br>('confused<br>deputy')):::d3fend-->d3fend.owl#CWE-610
    d3fend.owl#CWE-610(Externally<br>controlled<br>reference<br>to<br>a<br>resource<br>in<br>another<br>sphere):::d3fend-->d3fend.owl#CWE-664
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
- [Externally controlled reference to a resource in another sphere](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Externally%20controlled%20reference%20to%20a%20resource%20in%20another%20sphere/Externally%20controlled%20reference%20to%20a%20resource%20in%20another%20sphere.md)
- [Unintended proxy or intermediary ('confused deputy')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Externally%20controlled%20reference%20to%20a%20resource%20in%20another%20sphere/Unintended%20proxy%20or%20intermediary%20%28%27confused%20deputy%27%29/Unintended%20proxy%20or%20intermediary%20%28%27confused%20deputy%27%29.md)
- [Improper restriction of rendered ui layers or frames](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Externally%20controlled%20reference%20to%20a%20resource%20in%20another%20sphere/Unintended%20proxy%20or%20intermediary%20%28%27confused%20deputy%27%29/Improper%20restriction%20of%20rendered%20ui%20layers%20or%20frames/Improper%20restriction%20of%20rendered%20ui%20layers%20or%20frames.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

