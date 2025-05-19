# Use of umask() with chmod-style argument

## Overview

### Definition
Not defined.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CWE-560

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CWE-560(Use<br>of<br>umask()<br>with<br>chmod-style<br>argument):::d3fend-->d3fend.owl#CWE-687
    d3fend.owl#CWE-687(Function<br>call<br>with<br>incorrectly<br>specified<br>argument<br>value):::d3fend-->d3fend.owl#CWE-628
    d3fend.owl#CWE-628(Function<br>call<br>with<br>incorrectly<br>specified<br>arguments):::d3fend-->d3fend.owl#CWE-573
    d3fend.owl#CWE-573(Improper<br>following<br>of<br>specification<br>by<br>caller):::d3fend-->d3fend.owl#CWE-710
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
- [Improper following of specification by caller](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Improper%20following%20of%20specification%20by%20caller.md)
- [Function call with incorrectly specified arguments](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Function%20call%20with%20incorrectly%20specified%20arguments/Function%20call%20with%20incorrectly%20specified%20arguments.md)
- [Function call with incorrectly specified argument value](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Function%20call%20with%20incorrectly%20specified%20arguments/Function%20call%20with%20incorrectly%20specified%20argument%20value/Function%20call%20with%20incorrectly%20specified%20argument%20value.md)
- [Use of umask() with chmod-style argument](/docs/ontology/reference/model/D3FENDCore/Weakness/Improper%20adherence%20to%20coding%20standards/Improper%20following%20of%20specification%20by%20caller/Function%20call%20with%20incorrectly%20specified%20arguments/Function%20call%20with%20incorrectly%20specified%20argument%20value/Use%20of%20umask%28%29%20with%20chmod-style%20argument/Use%20of%20umask%28%29%20with%20chmod-style%20argument.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-be-weakness-of](http://d3fend.mitre.org/ontologies/d3fend.owl#may-be-weakness-of) |  |  | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |

