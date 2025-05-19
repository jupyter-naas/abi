# Stacking

## Overview

### Definition
Stacking is a method of using the results and predictions from one layer of ML models as inputs to another layer of ML models. Stacking (sometimes called stacked generalization) involves training a model to combine the predictions of several other learning algorithms.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#Stacking

### Subclass Of
```mermaid
graph BT
    d3fend.owl#Stacking(Stacking):::d3fend-->d3fend.owl#EnsembleLearning
    d3fend.owl#EnsembleLearning(Ensemble<br>learning):::d3fend-->d3fend.owl#MachineLearning
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
- [Ensemble learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Ensemble%20learning/Ensemble%20learning.md)
- [Stacking](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Ensemble%20learning/Stacking/Stacking.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
