# Cloud service authorization

## Overview

### Definition
Cloud authorization is the function of specifying access rights to cloud resources.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#CloudServiceAuthorization

### Subclass Of
```mermaid
graph BT
    d3fend.owl#CloudServiceAuthorization(Cloud<br>service<br>authorization):::d3fend-->d3fend.owl#Authorization
    d3fend.owl#Authorization(Authorization):::d3fend-->d3fend.owl#DefensiveAction
    d3fend.owl#DefensiveAction(Defensive<br>action):::d3fend-->d3fend.owl#CyberAction
    d3fend.owl#CyberAction(Cyber<br>action):::d3fend-->d3fend.owl#Action
    d3fend.owl#Action(Action):::d3fend-->d3fend.owl#Event
    d3fend.owl#Event(Event):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Event](/docs/ontology/reference/model/D3FENDCore/Event/Event.md)
- [Action](/docs/ontology/reference/model/D3FENDCore/Event/Action/Action.md)
- [Cyber action](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Cyber%20action.md)
- [Defensive action](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Defensive%20action/Defensive%20action.md)
- [Authorization](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Defensive%20action/Authorization/Authorization.md)
- [Cloud service authorization](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Defensive%20action/Authorization/Cloud%20service%20authorization/Cloud%20service%20authorization.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
