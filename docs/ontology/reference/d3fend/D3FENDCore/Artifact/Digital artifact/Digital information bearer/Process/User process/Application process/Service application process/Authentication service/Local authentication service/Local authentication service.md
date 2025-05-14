# Local authentication service

## Overview

### Definition
A local authentication service running on a host can authenticate a user logged into just that local host computer.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#LocalAuthenticationService

### Subclass Of
```mermaid
graph BT
    d3fend.owl#LocalAuthenticationService(Local<br>authentication<br>service):::d3fend-->d3fend.owl#AuthenticationService
    d3fend.owl#AuthenticationService(Authentication<br>service):::d3fend-->d3fend.owl#ServiceApplicationProcess
    d3fend.owl#ServiceApplicationProcess(Service<br>application<br>process):::d3fend-->d3fend.owl#ApplicationProcess
    d3fend.owl#ApplicationProcess(Application<br>process):::d3fend-->d3fend.owl#UserProcess
    d3fend.owl#UserProcess(User<br>process):::d3fend-->d3fend.owl#Process
    d3fend.owl#Process(Process):::d3fend-->d3fend.owl#DigitalInformationBearer
    d3fend.owl#DigitalInformationBearer(Digital<br>information<br>bearer):::d3fend-->d3fend.owl#DigitalArtifact
    d3fend.owl#DigitalArtifact(Digital<br>artifact):::d3fend-->d3fend.owl#Artifact
    d3fend.owl#Artifact(Artifact):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md)
- [Digital artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20artifact.md)
- [Digital information bearer](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Digital%20information%20bearer.md)
- [Process](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/Process.md)
- [User process](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/User%20process/User%20process.md)
- [Application process](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/User%20process/Application%20process/Application%20process.md)
- [Service application process](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/User%20process/Application%20process/Service%20application%20process/Service%20application%20process.md)
- [Authentication service](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/User%20process/Application%20process/Service%20application%20process/Authentication%20service/Authentication%20service.md)
- [Local authentication service](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/User%20process/Application%20process/Service%20application%20process/Authentication%20service/Local%20authentication%20service/Local%20authentication%20service.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Data Properties
| Ontology | Label | Definition | Example | Domain | Range |
|----------|-------|------------|---------|--------|-------|
| d3fend | [d3fend-artifact-data-property](http://d3fend.mitre.org/ontologies/d3fend.owl#d3fend-artifact-data-property) | x d3fend-artifact-data-property y: The artifact x has the data property y. |  | [Digital Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20artifact.md) | []() |
| d3fend | [process-security-context](http://d3fend.mitre.org/ontologies/d3fend.owl#process-security-context) | x process-security-context y: The process x has the process security context data y. |  | [Process](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information%20bearer/Process/Process.md) | []() |

### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |  |  | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | []() |

