# Web authentication

## Overview

### Definition
A request-response comprising a user credential presentation to a system and a verification response where the verifying party is a web server.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#WebAuthentication

### Subclass Of
```mermaid
graph BT
    d3fend.owl#WebAuthentication(Web<br>authentication):::d3fend-->d3fend.owl#Authentication
    d3fend.owl#Authentication(Authentication):::d3fend-->d3fend.owl#DefensiveAction
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
- [Authentication](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Defensive%20action/Authentication/Authentication.md)
- [Web authentication](/docs/ontology/reference/model/D3FENDCore/Event/Action/Cyber%20action/Defensive%20action/Authentication/Web%20authentication/Web%20authentication.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
