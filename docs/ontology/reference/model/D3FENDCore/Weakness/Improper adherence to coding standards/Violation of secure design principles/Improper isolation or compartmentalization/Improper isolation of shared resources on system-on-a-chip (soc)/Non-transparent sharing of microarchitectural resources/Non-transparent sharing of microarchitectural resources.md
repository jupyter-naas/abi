# Non-transparent sharing of microarchitectural resources

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-1303

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-1303(Non-transparent<br>sharing<br>of<br>microarchitectural<br>resources):::d3fend-->d3fend.owl#CWE-1189
    d3fend.owl#CWE-1189(Improper<br>isolation<br>of<br>shared<br>resources<br>on<br>system-on-a-chip<br>(soc)):::d3fend-->d3fend.owl#CWE-653
    d3fend.owl#CWE-653(Improper<br>isolation<br>or<br>compartmentalization):::d3fend-->d3fend.owl#CWE-657
    d3fend.owl#CWE-657(Violation<br>of<br>secure<br>design<br>principles):::d3fend-->d3fend.owl#CWE-710
    d3fend.owl#CWE-710(Improper<br>adherence<br>to<br>coding<br>standards):::d3fend-->d3fend.owl#Weakness
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
- [Improper adherence to coding standards](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20adherence%20to%20coding%20standards.md)
- [Violation of secure design principles](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Violation%20of%20secure%20design%20principles.md)
- [Improper isolation or compartmentalization](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Improper%20isolation%20or%20compartmentalization/Improper%20isolation%20or%20compartmentalization.md)
- [Improper isolation of shared resources on system-on-a-chip (soc)](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Improper%20isolation%20or%20compartmentalization/Improper%20isolation%20of%20shared%20resources%20on%20system-on-a-chip%20%28soc%29/Improper%20isolation%20of%20shared%20resources%20on%20system-on-a-chip%20%28soc%29.md)
- [Non-transparent sharing of microarchitectural resources](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Violation%20of%20secure%20design%20principles/Improper%20isolation%20or%20compartmentalization/Improper%20isolation%20of%20shared%20resources%20on%20system-on-a-chip%20%28soc%29/Non-transparent%20sharing%20of%20microarchitectural%20resources/Non-transparent%20sharing%20of%20microarchitectural%20resources.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

