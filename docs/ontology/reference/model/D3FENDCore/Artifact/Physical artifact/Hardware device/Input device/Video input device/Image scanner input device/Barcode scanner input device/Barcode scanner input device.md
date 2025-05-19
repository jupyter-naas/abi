# Barcode scanner input device

## Overview

### Definition
A barcode reader (or barcode scanner) is an optical scanner that can read printed barcodes, decode the data contained in the barcode and send the data to a computer. Like a flatbed scanner, it consists of a light source, a lens and a light sensor translating for optical impulses into electrical signals. Additionally, nearly all barcode readers contain decoder circuitry that can analyze the barcode's image data provided by the sensor and sending the barcode's content to the scanner's output port.

### Examples
Not defined.

### Aliases
Barcode Reader

### URI
http://d3fend.mitre.org/ontologies/d3fend.owl#BarcodeScannerInputDevice

### Subclass Of
```mermaid
graph BT
    d3fend.owl#BarcodeScannerInputDevice(Barcode<br>scanner<br>input<br>device):::d3fend-->d3fend.owl#ImageScannerInputDevice
    d3fend.owl#ImageScannerInputDevice(Image<br>scanner<br>input<br>device):::d3fend-->d3fend.owl#VideoInputDevice
    d3fend.owl#VideoInputDevice(Video<br>input<br>device):::d3fend-->d3fend.owl#InputDevice
    d3fend.owl#InputDevice(Input<br>device):::d3fend-->d3fend.owl#HardwareDevice
    d3fend.owl#HardwareDevice(Hardware<br>device):::d3fend-->d3fend.owl#PhysicalArtifact
    d3fend.owl#PhysicalArtifact(Physical<br>artifact):::d3fend-->d3fend.owl#Artifact
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
- [Physical artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Physical%20artifact.md)
- [Hardware device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Hardware%20device.md)
- [Input device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Input%20device/Input%20device.md)
- [Video input device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Input%20device/Video%20input%20device/Video%20input%20device.md)
- [Image scanner input device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Input%20device/Video%20input%20device/Image%20scanner%20input%20device/Image%20scanner%20input%20device.md)
- [Barcode scanner input device](/docs/ontology/reference/model/D3FENDCore/Artifact/Physical%20artifact/Hardware%20device/Input%20device/Video%20input%20device/Image%20scanner%20input%20device/Barcode%20scanner%20input%20device/Barcode%20scanner%20input%20device.md)


### Ontology Reference
- [d3fend](http://d3fend.mitre.org/ontologies/d3fend.owl#)

## Properties
### Object Properties
| Ontology | Label | Definition | Example | Domain | Range | Inverse Of |
|----------|-------|------------|---------|--------|-------|------------|
| d3fend | [may-have-weakness](http://d3fend.mitre.org/ontologies/d3fend.owl#may-have-weakness) |  |  | [Artifact](/docs/ontology/reference/model/D3FENDCore/Artifact/Artifact.md) | [Weakness](/docs/ontology/reference/model/D3FENDCore/Weakness/Weakness.md) | []() |

