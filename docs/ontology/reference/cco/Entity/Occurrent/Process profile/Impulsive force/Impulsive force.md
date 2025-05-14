# Impulsive force

## Overview

### Definition
A Process Profile that is the integral of a Force that is applied to a portion of matter over a period of time.

### Examples
Not defined.

### Aliases
- J
- Impulse
- Imp

### URI
https://www.commoncoreontologies.org/ont00000772

### Subclass Of
```mermaid
graph BT
    ont00000772(Impulsive<br>force):::cco-->BFO_0000144
    BFO_0000144(Process<br>profile):::bfo-->BFO_0000003
    BFO_0000003(Occurrent):::bfo-->BFO_0000001
    BFO_0000001(Entity):::bfo
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [Entity](/docs/ontology/reference/model/Entity/Entity.md)
- [Occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md)
- [Process profile](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Process%20profile.md)
- [Impulsive force](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Impulsive%20force/Impulsive%20force.md)


### Ontology Reference
- [cco](https://www.commoncoreontologies.org/): [EventOntology](https://www.commoncoreontologies.org/EventOntology)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| bfo | [exists at](http://purl.obolibrary.org/obo/BFO_0000108) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](/docs/ontology/reference/model/Entity/Entity.md) | [temporal region](/docs/ontology/reference/model/Entity/Occurrent/Temporal%20region/Temporal%20region.md) | []() |
| bfo | [preceded by](http://purl.obolibrary.org/obo/BFO_0000062) | b preceded by c =Def b precedes c | The temporal region occupied by the second half of the match is preceded by the temporal region occupied by the first half of the match | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [precedes](http://purl.obolibrary.org/obo/BFO_0000063) |
| bfo | [precedes](http://purl.obolibrary.org/obo/BFO_0000063) | (Elucidation) precedes is a relation between occurrents o, o' such that if t is the temporal extent of o & t' is the temporal extent of o' then either the last instant of o is before the first instant of o' or the last instant of o is the first instant of o' & neither o nor o' are temporal instants | The temporal region occupied by Mary's birth precedes the temporal region occupied by Mary's death. | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| bfo | [has occurrent part](http://purl.obolibrary.org/obo/BFO_0000117) | b has occurrent part c =Def c occurrent part of b | Mary's life has occurrent part Mary's 5th birthday | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent part of](http://purl.obolibrary.org/obo/BFO_0000132) |
| bfo | [has temporal part](http://purl.obolibrary.org/obo/BFO_0000121) | b has temporal part c =Def c temporal part of b | Your life has temporal part the first year of your life | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [temporal part of](http://purl.obolibrary.org/obo/BFO_0000139) |
| bfo | [occurrent part of](http://purl.obolibrary.org/obo/BFO_0000132) | (Elucidation) occurrent part of is a relation between occurrents b and c when b is part of c | Mary's 5th birthday is an occurrent part of Mary's life; the first set of the tennis match is an occurrent part of the tennis match | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| bfo | [temporal part of](http://purl.obolibrary.org/obo/BFO_0000139) | b temporal part of c =Def b occurrent part of c & (b and c are temporal regions) or (b and c are spatiotemporal regions & b temporally projects onto an occurrent part of the temporal region that c temporally projects onto) or (b and c are processes or process boundaries & b occupies a temporal region that is an occurrent part of the temporal region that c occupies) | Your heart beating from 4pm to 5pm today is a temporal part of the process of your heart beating; the 4th year of your life is a temporal part of your life, as is the process boundary which separates the 3rd and 4th years of your life; the first quarter of a game of football is a temporal part of the whole game | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| cco | [is cause of](https://www.commoncoreontologies.org/ont00001803) | x is_cause_of y iff x and y are instances of Occurrent, and y is a consequence of x. |  | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [caused by](https://www.commoncoreontologies.org/ont00001819) |
| cco | [caused by](https://www.commoncoreontologies.org/ont00001819) | x caused_by y iff x and y are instances of Occurrent, and x is a consequence of y. |  | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |

