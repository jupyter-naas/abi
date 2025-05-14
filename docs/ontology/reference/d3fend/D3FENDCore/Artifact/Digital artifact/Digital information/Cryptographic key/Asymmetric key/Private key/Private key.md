# Private key

## Overview

### Definition
A private key can be used to decrypt messages encrypted using the corresponding public key, or used to sign a message that can be authenticated with the corresponding public key.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#PrivateKey

### Subclass Of
```mermaid
graph BT
    d3fend.owl#PrivateKey(Private<br>key):::d3fend-->d3fend.owl#AsymmetricKey
    d3fend.owl#AsymmetricKey(Asymmetric<br>key):::d3fend-->d3fend.owl#CryptographicKey
    d3fend.owl#CryptographicKey(Cryptographic<br>key):::d3fend-->d3fend.owl#DigitalInformation
    d3fend.owl#DigitalInformation(Digital<br>information):::d3fend-->d3fend.owl#DigitalArtifact
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
- [Digital information](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Digital%20information.md)
- [Cryptographic key](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Cryptographic%20key/Cryptographic%20key.md)
- [Asymmetric key](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Cryptographic%20key/Asymmetric%20key/Asymmetric%20key.md)
- [Private key](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20information/Cryptographic%20key/Asymmetric%20key/Private%20key/Private%20key.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Data Properties
| Ontology | Label | Definition | Example | Domain | Range |
|----------|-------|------------|---------|--------|-------|
| d3fend | [d3fend-artifact-data-property](http://d3fend.mitre.org/ontologies/d3fend.owl#d3fend-artifact-data-property) | x d3fend-artifact-data-property y: The artifact x has the data property y. |  | [Digital Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Digital%20artifact/Digital%20artifact.md) | []() |

### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |  |  | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | []() |

