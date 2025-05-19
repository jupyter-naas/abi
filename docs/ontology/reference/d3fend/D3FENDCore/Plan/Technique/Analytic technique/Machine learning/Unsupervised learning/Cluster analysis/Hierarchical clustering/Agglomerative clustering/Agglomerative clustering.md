# Agglomerative clustering

## Overview

### Definition
Agglomerative Clustering is a type of hierarchical clustering method where data points are grouped together based on similarity. Initially, each data point is treated as an individual cluster, and then in successive iterations, the closest clusters are merged until only one large cluster remains or until a specified stopping criterion is met.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#AgglomerativeClustering

### Subclass Of
```mermaid
graph BT
    d3fend.owl#AgglomerativeClustering(Agglomerative<br>clustering):::d3fend-->d3fend.owl#HierarchicalClustering
    d3fend.owl#HierarchicalClustering(Hierarchical<br>clustering):::d3fend-->d3fend.owl#ClusterAnalysis
    d3fend.owl#ClusterAnalysis(Cluster<br>analysis):::d3fend-->d3fend.owl#UnsupervisedLearning
    d3fend.owl#UnsupervisedLearning(Unsupervised<br>learning):::d3fend-->d3fend.owl#MachineLearning
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
- [Unsupervised learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Unsupervised%20learning/Unsupervised%20learning.md)
- [Cluster analysis](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Unsupervised%20learning/Cluster%20analysis/Cluster%20analysis.md)
- [Hierarchical clustering](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Unsupervised%20learning/Cluster%20analysis/Hierarchical%20clustering/Hierarchical%20clustering.md)
- [Agglomerative clustering](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Unsupervised%20learning/Cluster%20analysis/Hierarchical%20clustering/Agglomerative%20clustering/Agglomerative%20clustering.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
