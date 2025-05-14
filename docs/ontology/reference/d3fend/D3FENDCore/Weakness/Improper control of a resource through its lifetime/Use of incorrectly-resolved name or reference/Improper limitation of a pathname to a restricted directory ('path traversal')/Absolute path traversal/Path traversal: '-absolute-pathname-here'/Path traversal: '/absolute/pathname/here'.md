# Path traversal: '/absolute/pathname/here'

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-37

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-37(Path<br>traversal:<br>'-absolute-pathname-here'):::d3fend-->d3fend.owl#CWE-36
    d3fend.owl#CWE-36(Absolute<br>path<br>traversal):::d3fend-->d3fend.owl#CWE-22
    d3fend.owl#CWE-22(Improper<br>limitation<br>of<br>a<br>pathname<br>to<br>a<br>restricted<br>directory<br>('path<br>traversal')):::d3fend-->d3fend.owl#CWE-706
    d3fend.owl#CWE-706(Use<br>of<br>incorrectly-resolved<br>name<br>or<br>reference):::d3fend-->d3fend.owl#CWE-664
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
- [Use of incorrectly-resolved name or reference](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Use%20of%20incorrectly-resolved%20name%20or%20reference/Use%20of%20incorrectly-resolved%20name%20or%20reference.md)
- [Improper limitation of a pathname to a restricted directory ('path traversal')](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Use%20of%20incorrectly-resolved%20name%20or%20reference/Improper%20limitation%20of%20a%20pathname%20to%20a%20restricted%20directory%20%28%27path%20traversal%27%29/Improper%20limitation%20of%20a%20pathname%20to%20a%20restricted%20directory%20%28%27path%20traversal%27%29.md)
- [Absolute path traversal](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Use%20of%20incorrectly-resolved%20name%20or%20reference/Improper%20limitation%20of%20a%20pathname%20to%20a%20restricted%20directory%20%28%27path%20traversal%27%29/Absolute%20path%20traversal/Absolute%20path%20traversal.md)
- [Path traversal: '-absolute-pathname-here'](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20control%20of%20a%20resource%20through%20its%20lifetime/Use%20of%20incorrectly-resolved%20name%20or%20reference/Improper%20limitation%20of%20a%20pathname%20to%20a%20restricted%20directory%20%28%27path%20traversal%27%29/Absolute%20path%20traversal/Path%20traversal%3A%20%27-absolute-pathname-here%27/Path%20traversal%3A%20%27-absolute-pathname-here%27.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

