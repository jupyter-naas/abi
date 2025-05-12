# Organization member role

## Overview

### Definition
A Role that inheres in an Agent in virtue of the responsibilities that Agent is expected to fulfill as a member of some Organization.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00000175

### Subclass Of
- role: http://purl.obolibrary.org/obo/BFO_0000023

### Ontology Reference
- https://www.commoncoreontologies.org/AgentOntology

### Hierarchy
```mermaid
graph BT
    ont00000175(Organization<br>member<br>role):::BFO-->BFO_0000023
    BFO_0000023(Role):::BFO-->BFO_0000017
    BFO_0000017(Realizable<br>entity):::BFO-->BFO_0000020
    BFO_0000020(Specifically<br>dependent<br>continuant):::BFO-->BFO_0000002
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
| [exists at](https://www.commoncoreontologies.org/ont00001992) | (Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists | First World War exists at 1914-1916; Mexico exists at January 1, 2000 | [entity](http://purl.obolibrary.org/obo/BFO_0000001) | [temporal region](http://purl.obolibrary.org/obo/BFO_0000008) | []([]) |
| [continuant part of](https://www.commoncoreontologies.org/ont00001992) | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) |
| [has continuant part](https://www.commoncoreontologies.org/ont00001992) | b has continuant part c =Def c continuant part of b |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | []([]) |
| [is output of](https://www.commoncoreontologies.org/ont00001992) | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has output](https://www.commoncoreontologies.org/ont00001986) |
| [is input of](https://www.commoncoreontologies.org/ont00001992) | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [has input](https://www.commoncoreontologies.org/ont00001921) |
| [is affected by](https://www.commoncoreontologies.org/ont00001992) | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | [continuant](http://purl.obolibrary.org/obo/BFO_0000002) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | []([]) |
| [specifically depends on](https://www.commoncoreontologies.org/ont00001992) | (Elucidation) specifically depends on is a relation between a specifically dependent continuant b and specifically dependent continuant or independent continuant that is not a spatial region c such that b and c share no parts in common & b is of a nature such that at all times t it cannot exist unless c exists & b is not a boundary of c | A shape specifically depends on the shaped object; hue, saturation and brightness of a colour sample specifically depends on each other | [specifically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000020) | {'or': {'or': ['http://purl.obolibrary.org/obo/BFO_0000020']}} | []([]) |
| [inheres in](https://www.commoncoreontologies.org/ont00001992) | b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c | A shape inheres in a shaped object; a mass inheres in a material entity | [specifically dependent continuant](http://purl.obolibrary.org/obo/BFO_0000020) | {'and': {'and': ['http://purl.obolibrary.org/obo/BFO_0000004']}} | []([]) |
| [has realization](https://www.commoncoreontologies.org/ont00001992) | b has realization c =Def c realizes b | As for realizes | [realizable entity](http://purl.obolibrary.org/obo/BFO_0000017) | [process](http://purl.obolibrary.org/obo/BFO_0000015) | [realizes](http://purl.obolibrary.org/obo/BFO_0000055) |
| [role of aggregate](https://www.commoncoreontologies.org/ont00001992) | x role_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Role, and x inheres_in_aggregate y. |  | [role](http://purl.obolibrary.org/obo/BFO_0000023) | [object aggregate](http://purl.obolibrary.org/obo/BFO_0000027) | []([]) |
| [is subordinate role to](https://www.commoncoreontologies.org/ont00001992) | For all x,y,t: y is subordinate role to x at t iff: x is an instance of Role at time t, and y is an instance of Role at time t, and there is some z such that x is realized by z and z is an instance of Process which creates, modifies, transfers, or eliminates some u such that u is a Process Regulation at time t, and u is addressed to the bearer of y. |  | [role](http://purl.obolibrary.org/obo/BFO_0000023) | [role](http://purl.obolibrary.org/obo/BFO_0000023) | [has subordinate role](https://www.commoncoreontologies.org/ont00001951) |
| [has subordinate role](https://www.commoncoreontologies.org/ont00001992) | For all x,y,t: x has subordinate role y at t iff: x is an instance of Role at time t, and y is an instance of Role at time t, and there is some z such that x is realized by z and z is an instance of Process which creates, modifies, transfers, or eliminates some u such that u is a Process Regulation at time t, and u is addressed to the bearer of y. |  | [role](http://purl.obolibrary.org/obo/BFO_0000023) | [role](http://purl.obolibrary.org/obo/BFO_0000023) | []([]) |
| [has organizational context](https://www.commoncoreontologies.org/ont00001992) | x has_organizational_context y iff y is an instance of an Organization and x is an instance of a Role and z is an instance of a Person, such that z's affiliation with y is a prerequisite for z bearing x or y ascribes x to the bearer of x. |  | [role](http://purl.obolibrary.org/obo/BFO_0000023) | [Organization](https://www.commoncoreontologies.org/ont00001180) | []([]) |
