# File system sensor

## Overview

### Definition
Collects files and file metadata on an endpoint.

### Examples
Not defined.

### Aliases
Not defined.

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#FileSystemSensor

### Subclass Of
```mermaid
graph BT
    d3fend.owl#FileSystemSensor(File<br>system<br>sensor):::d3fend-->d3fend.owl#EndpointSensor
    d3fend.owl#EndpointSensor(Endpoint<br>sensor):::d3fend-->d3fend.owl#CyberSensor
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
- [Endpoint sensor](/docs/ontology/reference/model/D3FENDCore/Sensor/Cyber%20sensor/Endpoint%20sensor/Endpoint%20sensor.md)
- [File system sensor](/docs/ontology/reference/model/D3FENDCore/Sensor/Cyber%20sensor/Endpoint%20sensor/File%20system%20sensor/File%20system%20sensor.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
