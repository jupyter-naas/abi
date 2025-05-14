# Semi-supervised self-training

## Overview

### Definition
Self-training is the procedure in which a supervised method for classification or regression is modified it to work in a semi-supervised manner, taking advantage of labeled and unlabeled data

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#Semi-supervisedSelf-training

### Subclass Of
```mermaid
graph BT
    d3fend.owl#Semi-supervisedSelf-training(Semi-supervised<br>self-training):::d3fend-->d3fend.owl#Semi-supervisedWrapperMethod
    d3fend.owl#Semi-supervisedWrapperMethod(Semi-supervised<br>wrapper<br>method):::d3fend-->d3fend.owl#Semi-SupervisedLearning
    d3fend.owl#Semi-SupervisedLearning(Semi-supervised<br>learning):::d3fend-->d3fend.owl#MachineLearning
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
- [Semi-supervised learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Semi-supervised%20learning.md)
- [Semi-supervised wrapper method](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Semi-supervised%20wrapper%20method/Semi-supervised%20wrapper%20method.md)
- [Semi-supervised self-training](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Semi-supervised%20wrapper%20method/Semi-supervised%20self-training/Semi-supervised%20self-training.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
