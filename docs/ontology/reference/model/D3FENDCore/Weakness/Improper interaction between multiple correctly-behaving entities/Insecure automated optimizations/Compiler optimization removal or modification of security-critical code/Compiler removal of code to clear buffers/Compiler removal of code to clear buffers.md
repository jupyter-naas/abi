# Compiler removal of code to clear buffers

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-14

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-14(Compiler<br>removal<br>of<br>code<br>to<br>clear<br>buffers):::d3fend-->d3fend.owl#CWE-733
    d3fend.owl#CWE-733(Compiler<br>optimization<br>removal<br>or<br>modification<br>of<br>security-critical<br>code):::d3fend-->d3fend.owl#CWE-1038
    d3fend.owl#CWE-1038(Insecure<br>automated<br>optimizations):::d3fend-->d3fend.owl#CWE-435
    d3fend.owl#CWE-435(Improper<br>interaction<br>between<br>multiple<br>correctly-behaving<br>entities):::d3fend-->d3fend.owl#Weakness
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
- [Improper interaction between multiple correctly-behaving entities](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20interaction%20between%20multiple%20correctly-behaving%20entities/Improper%20interaction%20between%20multiple%20correctly-behaving%20entities.md)
- [Insecure automated optimizations](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20interaction%20between%20multiple%20correctly-behaving%20entities/Insecure%20automated%20optimizations/Insecure%20automated%20optimizations.md)
- [Compiler optimization removal or modification of security-critical code](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20interaction%20between%20multiple%20correctly-behaving%20entities/Insecure%20automated%20optimizations/Compiler%20optimization%20removal%20or%20modification%20of%20security-critical%20code/Compiler%20optimization%20removal%20or%20modification%20of%20security-critical%20code.md)
- [Compiler removal of code to clear buffers](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20interaction%20between%20multiple%20correctly-behaving%20entities/Insecure%20automated%20optimizations/Compiler%20optimization%20removal%20or%20modification%20of%20security-critical%20code/Compiler%20removal%20of%20code%20to%20clear%20buffers/Compiler%20removal%20of%20code%20to%20clear%20buffers.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

