# DatabaseInstance

## Definition
A database instance is a material entity that is a container that stores structured information used by ABI components.

## Hierarchy in BFO
```mermaid
graph BT
    BFO_0000001(Entity):::BFO
    BFO_0000002(Continuant):::BFO-->BFO_0000001
    BFO_0000004(Independent<br>Continuant):::BFO-->BFO_0000002
    BFO_0000040(Material<br>Entity):::BFO-->BFO_0000004
    
    ABI_DatabaseInstance(abi:DatabaseInstance):::ABI-->BFO_0000040
    
    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Ontological Schema (TBox)
```turtle
abi:DatabaseInstance a owl:Class ;
  rdfs:subClassOf bfo:0000040 ;
  rdfs:label "Database Instance" ;
  skos:definition "A material container that stores structured information used by ABI components." .

abi:has_database_type a owl:DatatypeProperty ;
  rdfs:domain abi:DatabaseInstance ;
  rdfs:range xsd:string ;
  rdfs:label "has database type" .

abi:hosted_on a owl:ObjectProperty ;
  rdfs:domain abi:DatabaseInstance ;
  rdfs:range abi:ComputeContainer ;
  rdfs:label "hosted on" .

abi:stores_data_for a owl:ObjectProperty ;
  rdfs:domain abi:DatabaseInstance ;
  rdfs:range abi:DigitalAsset ;
  rdfs:label "stores data for" .

abi:has_connection_string a owl:DatatypeProperty ;
  rdfs:domain abi:DatabaseInstance ;
  rdfs:range xsd:string ;
  rdfs:label "has connection string" .
```

## Ontological Instance (ABox)
```turtle
ex:CustomerDatabase a abi:DatabaseInstance ;
  rdfs:label "Customer Database" ;
  abi:has_database_type "PostgreSQL" ;
  abi:hosted_on ex:DatabaseServer1 ;
  abi:stores_data_for ex:CustomerRecords, ex:TransactionData ;
  abi:has_connection_string "postgresql://user:password@hostname:5432/customers" .

ex:AnalyticsDatabase a abi:DatabaseInstance ;
  rdfs:label "Analytics Database" ;
  abi:has_database_type "ClickHouse" ;
  abi:hosted_on ex:AnalyticsCluster ;
  abi:stores_data_for ex:EventLogs, ex:UserInteractions ;
  abi:has_connection_string "clickhouse://user:password@hostname:9000/analytics" .
```

## Related Classes
- **abi:ComputeContainer** - A material entity that is a software-deployed, bounded material system that runs a defined set of tasks, often mapped to an ABI workflow or service.
- **abi:ObjectStorageFolder** - A material entity that is a physical or virtual folder within a file system that holds time-versioned or semantically grouped resources.
- **abi:DigitalAsset** - A material entity that is a file-based or database-stored resource that represents content, knowledge, or configuration, and can be versioned, deployed, or referenced. 