# Semi-supervised pre-training

## Overview

### Definition
Pre-training methods are aimed to guide the parameters of a network towards interesting regions in model space using unlabeled data, before fine-tuning the parameters with the labeled data

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#Semi-supervisedPre-training

### Subclass Of
```mermaid
graph BT
    d3fend.owl#Semi-supervisedPre-training(Semi-supervised<br>pre-training):::d3fend-->d3fend.owl#UnsupervisedPreprocessing
    d3fend.owl#UnsupervisedPreprocessing(Unsupervised<br>preprocessing):::d3fend-->d3fend.owl#Semi-SupervisedLearning
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
- [Unsupervised preprocessing](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Unsupervised%20preprocessing/Unsupervised%20preprocessing.md)
- [Semi-supervised pre-training](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Unsupervised%20preprocessing/Semi-supervised%20pre-training/Semi-supervised%20pre-training.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
