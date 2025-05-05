# Artifact function specification

## Overview

### Definition
A Directive Information Content Entity that prescribes some Artifact Function and which is part of some Artifact Model.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00000118

### Subclass Of
- https://www.commoncoreontologies.org/ont00000965

### Ontology Reference
- https://www.commoncoreontologies.org/ArtifactOntology

### Hierarchy
```mermaid
graph BT
    ont00000118(Artifact<br>function<br>specification<br>ont00000118):::ABI-->ont00000965
    ont00000965(Directive<br>information<br>content<br>entity<br>ont00000965):::ABI-->ont00000958
    ont00000958(Information<br>content<br>entity<br>ont00000958):::BFO-->BFO_0000031
    BFO_0000031(Generically<br>dependent<br>continuant<br>BFO_0000031):::BFO-->BFO_0000002
    BFO_0000002(Continuant<br>BFO_0000002):::BFO-->BFO_0000001
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
| http://purl.obolibrary.org/obo/BFO_0000058 | ['http://purl.obolibrary.org/obo/BFO_0000031'] | [{'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000015']}}] | is concretized by | c is concretized by b =Def b concretizes c |  | ['http://purl.obolibrary.org/obo/BFO_0000059'] |
| http://purl.obolibrary.org/obo/BFO_0000084 | ['http://purl.obolibrary.org/obo/BFO_0000031'] | [{'and': {'and': ['http://purl.obolibrary.org/obo/BFO_0000004']}}] | generically depends on | b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t |  | ['http://purl.obolibrary.org/obo/BFO_0000101'] |
| http://purl.obolibrary.org/obo/BFO_0000108 | ['http://purl.obolibrary.org/obo/BFO_0000001'] | ['http://purl.obolibrary.org/obo/BFO_0000008'] | exists at | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | None |
| http://purl.obolibrary.org/obo/BFO_0000176 | ['http://purl.obolibrary.org/obo/BFO_0000002'] | ['http://purl.obolibrary.org/obo/BFO_0000002'] | continuant part of | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | ['http://purl.obolibrary.org/obo/BFO_0000178'] |
| http://purl.obolibrary.org/obo/BFO_0000178 | ['http://purl.obolibrary.org/obo/BFO_0000002'] | ['http://purl.obolibrary.org/obo/BFO_0000002'] | has continuant part | b has continuant part c =Def c continuant part of b |  | None |
| https://www.commoncoreontologies.org/ont00001808 | ['https://www.commoncoreontologies.org/ont00000958'] | ['http://purl.obolibrary.org/obo/BFO_0000001'] | is about | A primitive relationship between an Information Content Entity and some Entity. |  | None |
| https://www.commoncoreontologies.org/ont00001816 | ['http://purl.obolibrary.org/obo/BFO_0000002'] | ['http://purl.obolibrary.org/obo/BFO_0000015'] | is output of | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | ['https://www.commoncoreontologies.org/ont00001986'] |
| https://www.commoncoreontologies.org/ont00001841 | ['http://purl.obolibrary.org/obo/BFO_0000002'] | ['http://purl.obolibrary.org/obo/BFO_0000015'] | is input of | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | ['https://www.commoncoreontologies.org/ont00001921'] |
| https://www.commoncoreontologies.org/ont00001886 | ['http://purl.obolibrary.org/obo/BFO_0000002'] | ['http://purl.obolibrary.org/obo/BFO_0000015'] | is affected by | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | None |
| https://www.commoncoreontologies.org/ont00001942 | ['https://www.commoncoreontologies.org/ont00000965'] | None | prescribes | x prescribes y iff x is an instance of Information Content Entity and y is an instance of Entity, such that x serves as a rule or guide for y if y an Occurrent, or x serves as a model for y if y is a Continuant. | A blueprint prescribes some artifact or facility by being a model for it. | None |
