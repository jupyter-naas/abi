# Skill

## Overview

### Definition
An Agent Capability that inheres in a Person to the extent of that Person's capacity to realize it in Intentional Acts of a certain type.

### Examples
Not defined.

### Aliases
Not defined.

### URI
https://www.commoncoreontologies.org/ont00000089

### Subclass Of
```mermaid
graph BT
    ont00000089(Skill):::cco-->ont00001379
    ont00001379(Agent<br>capability):::cco-->BFO_0000017
    BFO_0000017(Realizable<br>entity):::bfo-->BFO_0000020
    BFO_0000020(Specifically<br>dependent<br>continuant):::bfo-->BFO_0000002
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
- [Specifically dependent continuant](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Specifically%20dependent%20continuant.md)
- [Realizable entity](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Realizable%20entity.md)
- [Agent capability](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Agent%20capability/Agent%20capability.md)
- [Skill](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Agent%20capability/Skill/Skill.md)


### Ontology Reference
- [cco](https://www.commoncoreontologies.org/): [AgentOntology](https://www.commoncoreontologies.org/AgentOntology)

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
| bfo | [specifically depends on](http://purl.obolibrary.org/obo/BFO_0000195) | (Elucidation) specifically depends on is a relation between a specifically dependent continuant b and specifically dependent continuant or independent continuant that is not a spatial region c such that b and c share no parts in common & b is of a nature such that at all times t it cannot exist unless c exists & b is not a boundary of c | A shape specifically depends on the shaped object; hue, saturation and brightness of a colour sample specifically depends on each other | [specifically dependent continuant](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Specifically%20dependent%20continuant.md) | [{'or': ['http://purl.obolibrary.org/obo/BFO_0000020', {'and': ['http://purl.obolibrary.org/obo/BFO_0000004', {'not': ['http://purl.obolibrary.org/obo/BFO_0000006']}]}]}](/docs/ontology/reference/model/%7B%27or%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/BFO_0000020%27%2C%20%7B%27and%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/BFO_0000004%27%2C%20%7B%27not%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/BFO_0000006%27%5D%7D%5D%7D%5D%7D/%7B%27or%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/bfo_0000020%27%2C%20%7B%27and%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/bfo_0000004%27%2C%20%7B%27not%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/bfo_0000006%27%5D%7D%5D%7D%5D%7D.md) | []() |
| bfo | [inheres in](http://purl.obolibrary.org/obo/BFO_0000197) | b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c | A shape inheres in a shaped object; a mass inheres in a material entity | [specifically dependent continuant](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Specifically%20dependent%20continuant.md) | [{'and': ['http://purl.obolibrary.org/obo/BFO_0000004', {'not': ['http://purl.obolibrary.org/obo/BFO_0000006']}]}](/docs/ontology/reference/model/%7B%27and%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/BFO_0000004%27%2C%20%7B%27not%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/BFO_0000006%27%5D%7D%5D%7D/%7B%27and%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/bfo_0000004%27%2C%20%7B%27not%27%3A%20%5B%27http%3A//purl.obolibrary.org/obo/bfo_0000006%27%5D%7D%5D%7D.md) | []() |
| bfo | [has realization](http://purl.obolibrary.org/obo/BFO_0000054) | b has realization c =Def c realizes b | As for realizes | [realizable entity](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Realizable%20entity.md) | [process](/docs/ontology/reference/model/Entity/Occurrent/Process/Process.md) | [realizes](http://purl.obolibrary.org/obo/BFO_0000055) |
| cco | [capability of aggregate](https://www.commoncoreontologies.org/ont00001880) | x capability_of_aggregate y iff y is an instance of Object Aggregate and x is an instance of Agent Capability, such that x inheres in aggregate y. |  | [Agent Capability](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Agent%20capability/Agent%20capability.md) | [Group of Agents](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Object%20aggregate/Group%20of%20agents/Group%20of%20agents.md) | [aggregate has capability](https://www.commoncoreontologies.org/ont00001898) |
| cco | [capability of](https://www.commoncoreontologies.org/ont00001889) | x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y. |  | [Agent Capability](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Agent%20capability/Agent%20capability.md) | [Agent](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Agent/Agent.md) | [has capability](https://www.commoncoreontologies.org/ont00001954) |
| abi | [is skill of](http://ontology.naas.ai/abi/isSkillOf) | A relation between a professional skill and the person who possesses it. | Playing the piano is a skill of John. | [Skill](/docs/ontology/reference/model/Entity/Continuant/Specifically%20dependent%20continuant/Realizable%20entity/Agent%20capability/Skill/Skill.md) | [Person](/docs/ontology/reference/model/Entity/Continuant/Independent%20continuant/Material%20entity/Object/Organism/Animal/Person/Person.md) | []() |

