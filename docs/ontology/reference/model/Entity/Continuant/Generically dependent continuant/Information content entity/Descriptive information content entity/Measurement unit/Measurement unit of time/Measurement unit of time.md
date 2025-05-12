# Measurement unit of time

## Overview

### Definition
A Measurement Unit that is used as a standard for measurement of temporal regions.

### Examples
- second, minute, hour, day

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00001357

### Subclass Of
- Measurement Unit: https://www.commoncoreontologies.org/ont00000120

### Ontology Reference
- https://www.commoncoreontologies.org/UnitsOfMeasureOntology

### Hierarchy
```mermaid
graph BT
    ont00001357(Measurement<br>unit<br>of<br>time):::ABI-->ont00000120
    ont00000120(Measurement<br>unit):::ABI-->ont00000853
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
| [exists at](https://www.commoncoreontologies.org/ont00001982) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | [temporal region](http://purl.obolibrary.org/obo/BFO_0000008) | []([]) |
| [continuant part of](https://www.commoncoreontologies.org/ont00001982) | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) |
| [has continuant part](https://www.commoncoreontologies.org/ont00001982) | b has continuant part c =Def c continuant part of b |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | []([]) |
| [is output of](https://www.commoncoreontologies.org/ont00001982) | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has output](https://www.commoncoreontologies.org/ont00001986) |
| [is input of](https://www.commoncoreontologies.org/ont00001982) | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has input](https://www.commoncoreontologies.org/ont00001921) |
| [is affected by](https://www.commoncoreontologies.org/ont00001982) | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | []([]) |
| [is concretized by](https://www.commoncoreontologies.org/ont00001982) | c is concretized by b =Def b concretizes c |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000015']}} | [concretizes](http://purl.obolibrary.org/obo/BFO_0000059) |
| [generically depends on](https://www.commoncoreontologies.org/ont00001982) | b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t |  | [generically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000031) | {'and': {'and': ['http://purl.obolibrary.org/obo/BFO_0000004']}} | [is carrier of](http://purl.obolibrary.org/obo/BFO_0000101) |
| [is about](https://www.commoncoreontologies.org/ont00001982) | A primitive relationship between an Information Content Entity and some Entity. |  | [Information Content Entity](https://www.commoncoreontologies.org/ont00000958) | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | []([]) |
| [describes](https://www.commoncoreontologies.org/ont00001982) | x describes y iff x is an instance of Information Content Entity, and y is an instance of Entity, such that x is about the characteristics by which y can be recognized or visualized. | the content of an accident report describes some accident | [Descriptive Information Content Entity](https://www.commoncoreontologies.org/ont00000853) |  | []([]) |
| [is measurement unit of](https://www.commoncoreontologies.org/ont00001982) | x is_measurement_unit_of y iff y is an instance of Information Bearing Entity and x is an instance of Measurement Unit, such that x describes the magnitude of measured physical quantity mentioned in y. |  | [Measurement Unit](https://www.commoncoreontologies.org/ont00000120) | [Information Bearing Entity](https://www.commoncoreontologies.org/ont00000253) | []([]) |
