# Cartesian coordinate system

## Overview

### Definition
A Spatial Reference System that identifies each point in a spatial region of n-dimensions using an ordered n-tuple of numerical coordinates that are the signed (i.e. positive or negative) distances measured in the same unit of length from the zero point where the fixed perpendicular Coordinate System Axes meet.

### Examples
Not defined.

### Aliases
- Rectangular Coordinate System

### URI
https://www.commoncoreontologies.org/ont00001351

### Subclass Of
- Spatial Reference System: https://www.commoncoreontologies.org/ont00000275

### Ontology Reference
- https://www.commoncoreontologies.org/InformationEntityOntology

### Hierarchy
```mermaid
graph BT
    ont00001351(Cartesian<br>coordinate<br>system):::ABI-->ont00000275
    ont00000275(Spatial<br>reference<br>system):::ABI-->ont00000398
    ont00000398(Reference<br>system):::ABI-->ont00000853
    ont00000853(Descriptive<br>information<br>content<br>entity):::ABI-->ont00000958
    ont00000958(Information<br>content<br>entity):::BFO-->BFO_0000031
    BFO_0000031(Generically<br>dependent<br>continuant):::BFO-->BFO_0000002
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000001(Entity):::BFO
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef CCO fill:#e4c51e,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Properties
### Data Properties
### Object Properties
| Label | Definition | Example | Domain | Range | Inverse Of |
|-------|------------|---------|--------|-------|------------|
| [exists at](https://www.commoncoreontologies.org/ont00001997) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | [temporal region](http://purl.obolibrary.org/obo/BFO_0000008) | []([]) |
| [continuant part of](https://www.commoncoreontologies.org/ont00001997) | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) |
| [has continuant part](https://www.commoncoreontologies.org/ont00001997) | b has continuant part c =Def c continuant part of b |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | []([]) |
| [is output of](https://www.commoncoreontologies.org/ont00001997) | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has output](https://www.commoncoreontologies.org/ont00001986) |
| [is input of](https://www.commoncoreontologies.org/ont00001997) | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has input](https://www.commoncoreontologies.org/ont00001921) |
| [is affected by](https://www.commoncoreontologies.org/ont00001997) | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | []([]) |
| [is concretized by](https://www.commoncoreontologies.org/ont00001997) | c is concretized by b =Def b concretizes c |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000015']}} | [concretizes](http://purl.obolibrary.org/obo/BFO_0000059) |
| [generically depends on](https://www.commoncoreontologies.org/ont00001997) | b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'and': {'and': ['http://purl.obolibrary.org/obo/BFO_0000004']}} | [is carrier of](http://purl.obolibrary.org/obo/BFO_0000101) |
| [is about](https://www.commoncoreontologies.org/ont00001997) | A primitive relationship between an Information Content Entity and some Entity. |  | [Information Content Entity](https://www.commoncoreontologies.org/ont00000958) | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | []([]) |
| [describes](https://www.commoncoreontologies.org/ont00001997) | x describes y iff x is an instance of Information Content Entity, and y is an instance of Entity, such that x is about the characteristics by which y can be recognized or visualized. | the content of an accident report describes some accident | [Descriptive Information Content Entity](https://www.commoncoreontologies.org/ont00000853) |  | []([]) |
| [is reference system of](https://www.commoncoreontologies.org/ont00001997) | x is_reference_system_of y iff y is an instance of Information Bearing Entity and x is an instance of Reference System, such that x describes the set of standards mentioned in y. |  | [Reference System](https://www.commoncoreontologies.org/ont00000398) | [Information Bearing Entity](https://www.commoncoreontologies.org/ont00000253) | []([]) |
