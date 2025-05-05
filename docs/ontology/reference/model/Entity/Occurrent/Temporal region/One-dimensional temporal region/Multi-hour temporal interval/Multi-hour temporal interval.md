# Multi-hour temporal interval

## Overview

### Definition
A one-dimensional temporal region that is measured in Hours and spans at least one Hour.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00000063

### Subclass Of
- http://purl.obolibrary.org/obo/BFO_0000038

### Ontology Reference
- https://www.commoncoreontologies.org/TimeOntology

### Hierarchy
```mermaid
graph BT
    ont00000063(Multi-hour<br>temporal<br>interval<br>ont00000063):::BFO-->BFO_0000038
    BFO_0000038(One-dimensional<br>temporal<br>region<br>BFO_0000038):::BFO-->BFO_0000008
    BFO_0000008(Temporal<br>region<br>BFO_0000008):::BFO-->BFO_0000003
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
| http://purl.obolibrary.org/obo/BFO_0000222 | ['http://purl.obolibrary.org/obo/BFO_0000008'] | ['http://purl.obolibrary.org/obo/BFO_0000203'] | has first instant | t has first instant t' =Def t' first instant of t | The first hour of a year has first instant midnight on December 31 | None |
| http://purl.obolibrary.org/obo/BFO_0000224 | ['http://purl.obolibrary.org/obo/BFO_0000008'] | ['http://purl.obolibrary.org/obo/BFO_0000203'] | has last instant | t has last instant t' =Def t' last instant of t | The last hour of a year has last instant midnight December 31 | None |
| https://www.commoncoreontologies.org/ont00001779 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000148'] | has inside instant | For Temporal Interval t1 and Temporal Instant t2, t1 has inside instant t2 if and only if there exists Temporal Instants t3 and t4 that are part of t1 and non-identical with t2, such that t3 is before t2 and t4 is after t2. |  | ['https://www.commoncoreontologies.org/ont00001848'] |
| https://www.commoncoreontologies.org/ont00001795 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | has inside interval | A Temporal Interval INT2 has inside interval some Temporal Interval INT1 iff there exist Temporal Instants inst1, inst2, inst3, and inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst3 is before inst1, and inst2 is before inst4. |  | ['https://www.commoncoreontologies.org/ont00001869'] |
| https://www.commoncoreontologies.org/ont00001803 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | is cause of | x is_cause_of y iff x and y are instances of Occurrent, and y is a consequence of x. |  | ['https://www.commoncoreontologies.org/ont00001819'] |
| https://www.commoncoreontologies.org/ont00001814 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval finishes | A Temporal Interval INT1 finishes some Temporal Interval INT2 iff there exists Temporal Instants inst1, inst2, and inst3 such that inst 1 is the starting instant of INT1, inst2 is the ending instant of both INT1 and INT2, inst3 is the starting instant of INT2, and inst3 is before inst1. |  | ['https://www.commoncoreontologies.org/ont00001821'] |
| https://www.commoncoreontologies.org/ont00001819 | ['http://purl.obolibrary.org/obo/BFO_0000003'] | ['http://purl.obolibrary.org/obo/BFO_0000003'] | caused by | x caused_by y iff x and y are instances of Occurrent, and x is a consequence of y. |  | None |
| https://www.commoncoreontologies.org/ont00001821 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval finished by | A Temporal Interval INT2 is finished by some Temporal Interval INT1 iff there exists Temporal Instants inst1, inst2, and inst3 such that inst 1 is the starting instant of INT1, inst2 is the ending instant of both INT1 and INT2, inst3 is the starting instant of INT2, and inst3 is before inst1. |  | None |
| https://www.commoncoreontologies.org/ont00001822 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval equals | A Temporal Interval INT1 is equal to some Temporal Interval INT2 iff there exists Temporal Instants inst1 and inst2 such that inst1 is the starting instant of both INT1 and INT2 and inst2 is the ending instant of both INT1 and INT2. |  | None |
| https://www.commoncoreontologies.org/ont00001825 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval overlaps | A Temporal Interval INT1 overlaps some Temporal Interval INT2 iff there exist Temporal Instants inst1, inst2, inst3, inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst1 is before inst3, inst3 is before inst2, and inst2 is before inst4. |  | ['https://www.commoncoreontologies.org/ont00001870'] |
| https://www.commoncoreontologies.org/ont00001847 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval is after | A TemporalInterval INT2 is after some TemporalInterval INT1 iff there exists TemporalInstants inst2, inst1 such that inst2 is the starting instant of INT2 and inst1 is the ending instant of INT1 and inst2 is after inst1. |  | ['https://www.commoncoreontologies.org/ont00001940'] |
| https://www.commoncoreontologies.org/ont00001862 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval disjoint | A Temporal Interval INT1 is disjoint with a Temporal Interval INT2 iff INT1 is before or meets INT2 OR INT2 is before or meets INT1. In other words, INT1 and INT2 are disjoint iff INT1 and INT2 do not overlap, contain, or equal one another. |  | None |
| https://www.commoncoreontologies.org/ont00001869 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval during | A Temporal Interval INT1 is during some Temporal Interval INT2 iff there exist Temporal Instants inst1, inst2, inst3, and inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst3 is before inst1, and inst2 is before inst4. |  | None |
| https://www.commoncoreontologies.org/ont00001870 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval overlapped by | A Temporal Interval INT2 is overlapped by some Temporal Interval INT1 iff there exist Temporal Instants inst1, inst2, inst3, inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst1 is before inst3, inst3 is before inst2, and inst2 is before inst4. |  | None |
| https://www.commoncoreontologies.org/ont00001874 | ['http://purl.obolibrary.org/obo/BFO_0000008'] | [{'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000015']}}] | is temporal region of | t is temporal region of p iff p occupies temporal region t. |  | None |
| https://www.commoncoreontologies.org/ont00001875 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval started by | A Temporal Interval INT2 is started by some Temporal Interval INT1 iff there exist Temporal Instants inst1, inst2, and inst3 such that inst1 is the starting instant of both INT1 and INT2, inst2 is the ending instant of INT1, inst3 is the ending instant of INT2 and inst2 is before inst3. |  | ['https://www.commoncoreontologies.org/ont00001923'] |
| https://www.commoncoreontologies.org/ont00001896 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval meets | A Temporal Interval INT1 meets some Temporal Interval INT2 iff there exists some Temporal Instant inst1 such that inst1 is the ending instant of INT1 and inst1 is the starting instant of INT2. |  | ['https://www.commoncoreontologies.org/ont00001915'] |
| https://www.commoncoreontologies.org/ont00001915 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval met by | A Temporal Interval INT2 is met by some Temporal Interval INT1 iff there exists some Temporal Instant inst1 such that inst1 is the starting instant of INT2 and inst1 is the ending instant of INT1. |  | None |
| https://www.commoncoreontologies.org/ont00001923 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval starts | A Temporal Interval INT1 starts some Temporal Interval INT2 iff there exist Temporal Instants inst1, inst2, and inst3 such that inst1 is the starting instant of both INT1 and INT2, inst2 is the ending instant of INT1, inst3 is the ending instant of INT2 and inst2 is before inst3. |  | None |
| https://www.commoncoreontologies.org/ont00001924 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval contains | A Temporal Interval INT2 contains some Temporal Interval INT1 iff there exist Temporal Instants inst1, inst2, inst3, and inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst3 is before or identical to inst1, and inst2 is before or identical to inst4, but it is not the case that both inst3 is identical to inst1 and inst2 is identical to inst4. |  | ['https://www.commoncoreontologies.org/ont00001971'] |
| https://www.commoncoreontologies.org/ont00001940 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval is before | A TemporalInterval INT1 is before some TemporalInterval INT2 iff there exists TemporalInstants inst1, inst2 such that inst1 is the ending instant of INT1 and inst2 is the starting instant of INT2 and inst1 is before inst2. |  | None |
| https://www.commoncoreontologies.org/ont00001971 | ['http://purl.obolibrary.org/obo/BFO_0000038'] | ['http://purl.obolibrary.org/obo/BFO_0000038'] | interval contained by | A Temporal Interval INT1 is contained by some Temporal Interval INT2 iff there exist Temporal Instants inst1, inst2, inst3, and inst4 such that inst1 is the starting instant of INT1, inst2 is the ending instant of INT1, inst3 is the starting instant of INT2, inst4 is the ending instant of INT2, inst3 is before or identical to inst1, inst2 is before or identical to inst4, and it is not the case that both inst3 is identical to inst1 and inst2 is identical to inst4. |  | None |
