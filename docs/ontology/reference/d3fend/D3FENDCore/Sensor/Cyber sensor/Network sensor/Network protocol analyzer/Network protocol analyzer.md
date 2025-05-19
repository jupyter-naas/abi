# Network protocol analyzer

## Overview

### Definition
Monitors and parses network protocols to extract values from various network protocol layers.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#NetworkProtocolAnalyzer

### Subclass Of
```mermaid
graph BT
    d3fend.owl#NetworkProtocolAnalyzer(Network<br>protocol<br>analyzer):::d3fend-->d3fend.owl#NetworkSensor
    d3fend.owl#NetworkSensor(Network<br>sensor):::d3fend-->d3fend.owl#CyberSensor
    d3fend.owl#CyberSensor(Cyber<br>sensor):::d3fend-->d3fend.owl#Sensor
    d3fend.owl#Sensor(Sensor):::d3fend-->d3fend.owl#D3FENDCore
    d3fend.owl#D3FENDCore(D3FENDCore):::d3fend
    
    classDef bfo fill:#97c1fb,color:#060606
    classDef cco fill:#e4c51e,color:#060606
    classDef abi fill:#48DD82,color:#060606
    classDef attack fill:#FF0000,color:#060606
    classDef d3fend fill:#FF0000,color:#060606
```

- [D3FENDCore](/docs/ontology/reference/model/D3FENDCore/D3FENDCore.md)
- [Sensor](/docs/ontology/reference/model/D3FENDCore/Sensor/Sensor.md)
- [Cyber sensor](/docs/ontology/reference/model/D3FENDCore/Sensor/Cyber%20sensor/Cyber%20sensor.md)
- [Network sensor](/docs/ontology/reference/model/D3FENDCore/Sensor/Cyber%20sensor/Network%20sensor/Network%20sensor.md)
- [Network protocol analyzer](/docs/ontology/reference/model/D3FENDCore/Sensor/Cyber%20sensor/Network%20sensor/Network%20protocol%20analyzer/Network%20protocol%20analyzer.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
