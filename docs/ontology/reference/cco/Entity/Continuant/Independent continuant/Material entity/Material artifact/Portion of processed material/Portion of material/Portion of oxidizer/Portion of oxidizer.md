# Portion of oxidizer

## Overview

### Definition
A Portion of Material that is disposed to steal electrons from other substances (i.e. to oxidize other substances) as a participant in a reduction-oxidation process.

### Examples
oxygen, hydrogen peroxide, chlorine, sulfiric acid, potassium nitrate

### Aliases
- Portion of Oxidizing Agent
- Portion of Oxidant

### URI
https://www.commoncoreontologies.org/ont00000897

### Subclass Of
```mermaid
graph BT
    ont00000897(Portion<br>of<br>oxidizer):::cco-->ont00000457
    ont00000457(Portion<br>of<br>material):::cco-->ont00001084
    ont00001084(Portion<br>of<br>processed<br>material):::cco-->ont00000995
    ont00000995(Material<br>artifact):::cco-->BFO_0000040
    BFO_0000040(Material<br>entity):::bfo-->BFO_0000004
    BFO_0000004(Independent<br>continuant):::bfo-->BFO_0000002
    BFO_0000002(Continuant):::bfo-->BFO_0000001
    BFO_0000001(Entity):::bfo
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [Entity](/docs/ontology/reference/model/Entity/Entity.md)
- [Continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md)
- [Independent continuant](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Independent%20continuant.md)
- [Material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md)
- [Material artifact](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20artifact/Material%20artifact.md)
- [Portion of processed material](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20artifact/Portion%20of%20processed%20material/Portion%20of%20processed%20material.md)
- [Portion of material](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20artifact/Portion%20of%20processed%20material/Portion%20of%20material/Portion%20of%20material.md)
- [Portion of oxidizer](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20artifact/Portion%20of%20processed%20material/Portion%20of%20material/Portion%20of%20oxidizer/Portion%20of%20oxidizer.md)


### Ontology Reference
- [cco](https://www.commoncoreontologies.org/): [ArtifactOntology](https://www.commoncoreontologies.org/ArtifactOntology)

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
| bfo | [continuant part of](http://purl.obolibrary.org/obo/BFO_0000176) | b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t | Milk teeth continuant part of human; surgically removed tumour continuant part of organism | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) |
| bfo | [has continuant part](http://purl.obolibrary.org/obo/BFO_0000178) | b has continuant part c =Def c continuant part of b |  | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | []() |
| cco | [is output of](https://www.commoncoreontologies.org/ont00001816) | x is_output_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the end of y is a necessary condition for the completion of y. |  | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | [has output](https://www.commoncoreontologies.org/ont00001986) |
| cco | [is input of](https://www.commoncoreontologies.org/ont00001841) | x is_input_of y iff x is an instance of Continuant and y is an instance of Process, such that the presence of x at the beginning of y is a necessary condition for the start of y. |  | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | [has input](https://www.commoncoreontologies.org/ont00001921) |
| cco | [is affected by](https://www.commoncoreontologies.org/ont00001886) | x is_affected_by y iff x is an instance of Continuant and y is an instance of Process, and y influences x in some manner, most often by producing a change in x. |  | [continuant](/docs/ontology/reference/model/Entity/Continuant/Continuant.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | []() |
| cco | [is successor of](https://www.commoncoreontologies.org/ont00001775) | A continuant c2 is a successor of some continuant c1 iff there is some process p1 and c1 is an input to p1 and c2 is an output of p1. Inverse of is predecessor.  |  | [independent continuant](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Independent%20continuant.md) | [independent continuant](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Independent%20continuant.md) | [is predecessor of](https://www.commoncoreontologies.org/ont00001928) |
| cco | [is predecessor of](https://www.commoncoreontologies.org/ont00001928) | A continuant c1 is a predecessor of some continuant c2 iff there is some process p1 and c1 is an input to p1 and c2 is an output of p1. |  | [independent continuant](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Independent%20continuant.md) | [independent continuant](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Independent%20continuant.md) | []() |
| bfo | [has member part](http://purl.obolibrary.org/obo/BFO_0000115) | b has member part c =Def c member part of b |  | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [member part of](http://purl.obolibrary.org/obo/BFO_0000129) |
| bfo | [material basis of](http://purl.obolibrary.org/obo/BFO_0000127) | b material basis of c =Def c has material basis b |  | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [disposition](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Disposition/Disposition.md) | [has material basis](http://purl.obolibrary.org/obo/BFO_0000218) |
| bfo | [member part of](http://purl.obolibrary.org/obo/BFO_0000129) | b member part of c =Def b is an object & c is a material entity & there is some time t such that b continuant part of c at t & there is a mutually exhaustive and pairwise disjoint partition of c into objects x1, ..., xn (for some n ≠ 1) with b = xi (for some 1 <= i <= n) |  | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | []() |
| bfo | [has history](http://purl.obolibrary.org/obo/BFO_0000185) | b has history c =Def c history of b | This organism has history this life | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [history](/docs/ontology/reference/model/Entity/Occurrent/Process/History/History.md) | []() |
| cco | [accessory in](https://www.commoncoreontologies.org/ont00001852) | y is_accessory_in x iff x is an instance of Process and y is an instance of Agent, such that y assists another agent in the commission of x, and y was not located at the location of x when x occurred, and y was not an agent_in x. |  | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | [has accessory](https://www.commoncoreontologies.org/ont00001949) |
| cco | [accomplice in](https://www.commoncoreontologies.org/ont00001895) | An agent a1 is accomplice_in some Processual Entity p1 iff a1 assists in the commission of p1, is located at the location of p1, but is not agent_in p1. |  | [material entity](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Material%20entity.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | []() |

