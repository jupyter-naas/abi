# Presence frequency

## Overview

### Definition
A Sonic Frequency that is between 4 and 6 kHz.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00000222

### Subclass Of
```mermaid
graph BT
    ont00000222(Presence<br>frequency):::cco-->ont00000530
    ont00000530(Sonic<br>frequency):::cco-->ont00000008
    ont00000008(Sound<br>frequency):::cco-->ont00001047
    ont00001047(Frequency):::cco-->BFO_0000144
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
- [Frequency](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Frequency/Frequency.md)
- [Sound frequency](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Frequency/Sound%20frequency/Sound%20frequency.md)
- [Sonic frequency](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Frequency/Sound%20frequency/Sonic%20frequency/Sonic%20frequency.md)
- [Presence frequency](/docs/ontology/reference/model/Entity/Occurrent/Process%20profile/Frequency/Sound%20frequency/Sonic%20frequency/Presence%20frequency/Presence%20frequency.md)


### Ontology Reference
- [cco](https://www.commoncoreontologies.org/): [EventOntology](https://www.commoncoreontologies.org/EventOntology)

## Properties
### Data Properties
| Ontology | Label | Definition | Example | Domain | Range |
|----------|-------|------------|---------|--------|-------|
| abi | [is curated in foundry](http://ontology.naas.ai/abi/is_curated_in_foundry) | Relates a class to the foundry it is curated in. | The class cco:ont00001262 is curated in the foundry 'enterprise_management_foundry' and 'personal_ai_foundry'. | [entity](/docs/ontology/reference/model/Entity/Entity.md) | [string](http://www.w3.org/2001/XMLSchema#string) |

### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| abi | [has backing data source](http://ontology.naas.ai/abi/hasBackingDataSource) | Relates an entity to the data source that provides the underlying data for that entity. This property indicates the origin or source of the data that supports the entity. | A report entity may have a backing data source that provides the raw data used to generate the report. | [entity](/docs/ontology/reference/model/Entity/Entity.md) | [Data Source](/docs/ontology/reference/model/Entity/Continuant/Generically%20dependent%20continuant/Data%20source/Data%20source.md) | []() |
| bfo | [exists at](http://purl.obolibrary.org/obo/BFO_0000108) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](/docs/ontology/reference/model/Entity/Entity.md) | [temporal region](/docs/ontology/reference/model/Entity/Occurrent/Temporal%20region/Temporal%20region.md) | []() |
| bfo | [preceded by](http://purl.obolibrary.org/obo/BFO_0000062) | b preceded by c =Def b precedes c | The temporal region occupied by the second half of the match is preceded by the temporal region occupied by the first half of the match | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [precedes](http://purl.obolibrary.org/obo/BFO_0000063) |
| bfo | [precedes](http://purl.obolibrary.org/obo/BFO_0000063) | (Elucidation) precedes is a relation between occurrents o, o' such that if t is the temporal extent of o & t' is the temporal extent of o' then either the last instant of o is before the first instant of o' or the last instant of o is the first instant of o' & neither o nor o' are temporal instants | The temporal region occupied by Mary's birth precedes the temporal region occupied by Mary's death. | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| bfo | [has occurrent part](http://purl.obolibrary.org/obo/BFO_0000117) | b has occurrent part c =Def c occurrent part of b | Mary's life has occurrent part Mary's 5th birthday | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent part of](http://purl.obolibrary.org/obo/BFO_0000132) |
| bfo | [has temporal part](http://purl.obolibrary.org/obo/BFO_0000121) | b has temporal part c =Def c temporal part of b | Your life has temporal part the first year of your life | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [temporal part of](http://purl.obolibrary.org/obo/BFO_0000139) |
| bfo | [occurrent part of](http://purl.obolibrary.org/obo/BFO_0000132) | (Elucidation) occurrent part of is a relation between occurrents b and c when b is part of c | Mary's 5th birthday is an occurrent part of Mary's life; the first set of the tennis match is an occurrent part of the tennis match | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| bfo | [temporal part of](http://purl.obolibrary.org/obo/BFO_0000139) | b temporal part of c =Def b occurrent part of c & (b and c are temporal regions) or (b and c are spatiotemporal regions & b temporally projects onto an occurrent part of the temporal region that c temporally projects onto) or (b and c are processes or process boundaries & b occupies a temporal region that is an occurrent part of the temporal region that c occupies) | Your heart beating from 4pm to 5pm today is a temporal part of the process of your heart beating; the 4th year of your life is a temporal part of your life, as is the process boundary which separates the 3rd and 4th years of your life; the first quarter of a game of football is a temporal part of the whole game | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |
| cco | [is cause of](https://www.commoncoreontologies.org/ont00001803) | x is_cause_of y iff x and y are instances of Occurrent, and y is a consequence of x. |  | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [caused by](https://www.commoncoreontologies.org/ont00001819) |
| cco | [caused by](https://www.commoncoreontologies.org/ont00001819) | x caused_by y iff x and y are instances of Occurrent, and x is a consequence of y. |  | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | [occurrent](/docs/ontology/reference/model/Entity/Occurrent/Occurrent.md) | []() |

