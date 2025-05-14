# Symmetric feature-based transfer learning

## Overview

### Definition
Homogeneous symmetric transformation takes both the source feature space Xs and target feature space Xt and learns feature transformations as to project each onto a common subspace Xc for adaptation purposes. This derived subspace becomes a domain-invariant feature subspace to associate cross-domain data, and in effect, reduces marginal distribution differences.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#SymmetricFeature-basedTransferLearning

### Subclass Of
```mermaid
graph BT
    d3fend.owl#SymmetricFeature-basedTransferLearning(Symmetric<br>feature-based<br>transfer<br>learning):::d3fend-->d3fend.owl#HomogenousTransferLearning
    d3fend.owl#HomogenousTransferLearning(Homogenous<br>transfer<br>learning):::d3fend-->d3fend.owl#TransferLearning
    d3fend.owl#TransferLearning(Transfer<br>learning):::d3fend-->d3fend.owl#MachineLearning
    d3fend.owl#MachineLearning(Machine<br>learning):::d3fend-->d3fend.owl#AnalyticTechnique
    d3fend.owl#AnalyticTechnique(Analytic<br>technique):::d3fend-->d3fend.owl#Technique
    d3fend.owl#Technique(Technique):::d3fend-->d3fend.owl#Plan
    d3fend.owl#Plan(Plan):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Plan](/docs/ontology/reference/model/D3FENDCore/Plan/Plan.md)
- [Technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Technique.md)
- [Analytic technique](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Analytic%20technique.md)
- [Machine learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Machine%20learning.md)
- [Transfer learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Transfer%20learning/Transfer%20learning.md)
- [Homogenous transfer learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Transfer%20learning/Homogenous%20transfer%20learning/Homogenous%20transfer%20learning.md)
- [Symmetric feature-based transfer learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Transfer%20learning/Homogenous%20transfer%20learning/Symmetric%20feature-based%20transfer%20learning/Symmetric%20feature-based%20transfer%20learning.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
