# Semi-supervised generative model learning

## Overview

### Definition
A Semi Supervised Machine Learning model which assume that the distributions take some particular form p(x|y,theta) parameterized by the vector. If these assumptions are incorrect, the unlabeled data may actually decrease the accuracy of the solution relative to what would have been obtained from labeled data alone. However, if the assumptions are correct, then the unlabeled data necessarily improves performance.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#Semi-supervisedGenerativeModelLearning

### Subclass Of
```mermaid
graph BT
    d3fend.owl#Semi-supervisedGenerativeModelLearning(Semi-supervised<br>generative<br>model<br>learning):::d3fend-->d3fend.owl#IntrinsicallySemi-supervisedLearning
    d3fend.owl#IntrinsicallySemi-supervisedLearning(Intrinsically<br>semi-supervised<br>learning):::d3fend-->d3fend.owl#Semi-SupervisedLearning
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
- [Intrinsically semi-supervised learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Intrinsically%20semi-supervised%20learning/Intrinsically%20semi-supervised%20learning.md)
- [Semi-supervised generative model learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Semi-supervised%20learning/Intrinsically%20semi-supervised%20learning/Semi-supervised%20generative%20model%20learning/Semi-supervised%20generative%20model%20learning.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
