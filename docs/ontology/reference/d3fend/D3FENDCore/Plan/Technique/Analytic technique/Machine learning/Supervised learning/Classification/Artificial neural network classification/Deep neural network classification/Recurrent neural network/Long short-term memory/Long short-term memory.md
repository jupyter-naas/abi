# Long short-term memory

## Overview

### Definition
Unlike standard feedforward neural networks, LSTM has feedback connections. Such a recurrent neural network (RNN) can process not only single data points (such as images), but also entire sequences of data (such as speech or video). This characteristic makes LSTM networks ideal for processing and predicting data

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#LongShort-termMemory

### Subclass Of
```mermaid
graph BT
    d3fend.owl#LongShort-termMemory(Long<br>short-term<br>memory):::d3fend-->d3fend.owl#RecurrentNeuralNetwork
    d3fend.owl#RecurrentNeuralNetwork(Recurrent<br>neural<br>network):::d3fend-->d3fend.owl#DeepNeuralNetClassification
    d3fend.owl#DeepNeuralNetClassification(Deep<br>neural<br>network<br>classification):::d3fend-->d3fend.owl#ArtificialNeuralNetClassification
    d3fend.owl#ArtificialNeuralNetClassification(Artificial<br>neural<br>network<br>classification):::d3fend-->d3fend.owl#Classification
    d3fend.owl#Classification(Classification):::d3fend-->d3fend.owl#SupervisedLearning
    d3fend.owl#SupervisedLearning(Supervised<br>learning):::d3fend-->d3fend.owl#MachineLearning
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
- [Supervised learning](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Supervised%20learning.md)
- [Classification](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Classification/Classification.md)
- [Artificial neural network classification](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Classification/Artificial%20neural%20network%20classification/Artificial%20neural%20network%20classification.md)
- [Deep neural network classification](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Classification/Artificial%20neural%20network%20classification/Deep%20neural%20network%20classification/Deep%20neural%20network%20classification.md)
- [Recurrent neural network](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Classification/Artificial%20neural%20network%20classification/Deep%20neural%20network%20classification/Recurrent%20neural%20network/Recurrent%20neural%20network.md)
- [Long short-term memory](/docs/ontology/reference/model/D3FENDCore/Plan/Technique/Analytic%20technique/Machine%20learning/Supervised%20learning/Classification/Artificial%20neural%20network%20classification/Deep%20neural%20network%20classification/Recurrent%20neural%20network/Long%20short-term%20memory/Long%20short-term%20memory.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
