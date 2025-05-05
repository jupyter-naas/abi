# Brilliance frequency

## Overview

### Definition
A Sonic Frequency that is between 6 and 20 kHz.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00001231

### Subclass Of
- https://www.commoncoreontologies.org/ont00000530

### Ontology Reference
- https://www.commoncoreontologies.org/EventOntology

### Hierarchy
```mermaid
graph BT
    ont00001231(Brilliance<br>frequency<br>ont00001231):::ABI-->ont00000530
    ont00000530(Sonic<br>frequency<br>ont00000530):::ABI-->ont00000008
    ont00000008(Sound<br>frequency<br>ont00000008):::ABI-->ont00001047
    ont00001047(Frequency<br>ont00001047):::BFO-->BFO_0000144
    BFO_0000144(Process<br>profile<br>BFO_0000144):::BFO-->BFO_0000003
    BFO_0000003(Occurrent<br>BFO_0000003):::BFO-->BFO_0000001
    BFO_0000001(Entity):::BFO
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef CCO fill:#e4c51e,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Properties
### Data Properties
| Predicate | Domain | Range | Label | Definition | Example |
|-----------|---------|--------|---------|------------|----------|

### Object Properties
| Predicate | Domain | Range | Label | Definition | Example | Inverse Of |
|-----------|---------|--------|---------|------------|----------|------------|
| http://purl.obolibrary.org/obo/BFO_0000062 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | preceded by | b preceded by c =Def b precedes c | The temporal region occupied by the second half of the match is preceded by the temporal region occupied by the first half of the match | ['http://purl.obolibrary.org/obo/BFO_0000063'] |
| http://purl.obolibrary.org/obo/BFO_0000063 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | precedes | (Elucidation) precedes is a relation between occurrents o, o' such that if t is the temporal extent of o & t' is the temporal extent of o' then either the last instant of o is before the first instant of o' or the last instant of o is the first instant of o' & neither o nor o' are temporal instants | The temporal region occupied by Mary's birth precedes the temporal region occupied by Mary's death. | None |
| http://purl.obolibrary.org/obo/BFO_0000108 | ['http://purl.obolibrary.org/obo/BFO_0000001'] | ['http://purl.obolibrary.org/obo/BFO_0000008'] | exists at | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | None |
| http://purl.obolibrary.org/obo/BFO_0000117 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | has occurrent part | b has occurrent part c =Def c occurrent part of b | Mary's life has occurrent part Mary's 5th birthday | ['http://purl.obolibrary.org/obo/BFO_0000132'] |
| http://purl.obolibrary.org/obo/BFO_0000121 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | has temporal part | b has temporal part c =Def c temporal part of b | Your life has temporal part the first year of your life | ['http://purl.obolibrary.org/obo/BFO_0000139'] |
| http://purl.obolibrary.org/obo/BFO_0000132 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | occurrent part of | (Elucidation) occurrent part of is a relation between occurrents b and c when b is part of c | Mary's 5th birthday is an occurrent part of Mary's life; the first set of the tennis match is an occurrent part of the tennis match | None |
| http://purl.obolibrary.org/obo/BFO_0000139 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | temporal part of | b temporal part of c =Def b occurrent part of c & (b and c are temporal regions) or (b and c are spatiotemporal regions & b temporally projects onto an occurrent part of the temporal region that c temporally projects onto) or (b and c are processes or process boundaries & b occupies a temporal region that is an occurrent part of the temporal region that c occupies) | Your heart beating from 4pm to 5pm today is a temporal part of the process of your heart beating; the 4th year of your life is a temporal part of your life, as is the process boundary which separates the 3rd and 4th years of your life; the first quarter of a game of football is a temporal part of the whole game | None |
| https://www.commoncoreontologies.org/ont00001803 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | is cause of | x is_cause_of y iff x and y are instances of Occurrent, and y is a consequence of x. |  | ['https://www.commoncoreontologies.org/ont00001819'] |
| https://www.commoncoreontologies.org/ont00001819 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | caused by | x caused_by y iff x and y are instances of Occurrent, and x is a consequence of y. |  | None |
