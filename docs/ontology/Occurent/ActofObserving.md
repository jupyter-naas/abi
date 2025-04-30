# Act of Observing

## Hierarchy Representation

```mermaid
graph BT
	BFO_0000002(Continuant)-->BFO_0000001(Entity):::BFO
	BFO_0000020(Specifically Dependent<br> Continuant)-->BFO_0000002(Continuant):::BFO
	BFO_0000031(Generically Dependent<br> Continuant):::BFO-->BFO_0000002(Continuant)
	BFO_0000004(Independent<br> Continuant)-->BFO_0000002(Continuant)
	BFO_0000040(Material Entity)-->BFO_0000004(Independent<br> Continuant):::BFO
	BFO_0000141(Immaterial<br> Entity)-->BFO_0000004(Independent<br> Continuant)
	BFO_0000019(Quality)-->BFO_0000020(Specifically Dependent<br> Continuant):::BFO
	BFO_0000017(Realizable<br> Entity):::BFO-->BFO_0000020(Specifically Dependent<br> Continuant)
	BFO_0000145(Relational<br> Quality):::BFO-->BFO_0000019(Quality):::BFO
	BFO_0000023(Role):::BFO-->BFO_0000017(Realizable<br> Entity):::BFO
	BFO_0000016(Disposition):::BFO-->BFO_0000017(Realizable<br> Entity)
	BFO_0000034(Function):::BFO-->BFO_0000016(Disposition)
	BFO_0000029(Site):::BFO-->BFO_0000141(Immaterial<br> Entity):::BFO
	BFO_0000006(Spatial<br> Region):::BFO-->BFO_0000141(Immaterial<br> Entity)
	BFO_0000140(Continuant Fiat<br> Boundary):::BFO-->BFO_0000141(Immaterial<br> Entity)
	BFO_0000147(Fiat<br> Point):::BFO-->BFO_0000140(Continuant Fiat<br> Boundary):::BFO
	BFO_0000146(Fiat<br> Surface):::BFO-->BFO_0000140(Continuant Fiat<br> Boundary)
	BFO_0000142(Fiat<br> Line):::BFO-->BFO_0000140(Continuant Fiat<br> Boundary)
	BFO_0000018(Zero-Dimensional<br> Spatial Region):::BFO-->BFO_0000006(Spatial<br> Region):::BFO
	BFO_0000026(One-Dimensional<br> Spatial Region):::BFO-->BFO_0000006(Spatial<br> Region):::BFO
	BFO_0000009(Two-Dimensional<br> Spatial Region):::BFO-->BFO_0000006(Spatial<br> Region):::BFO
	BFO_0000028(Three-Dimensional<br> Spatial Region):::BFO-->BFO_0000006(Spatial<br> Region):::BFO
	BFO_0000024(Fiat Object Part):::BFO-->BFO_0000040(Material<br> Entity):::BFO
	BFO_0000027(Object<br> Aggregate):::BFO-->BFO_0000040(Material<br> Entity):::BFO
	BFO_0000030(Object):::BFO-->BFO_0000040(Material<br> Entity):::BFO
	BFO_0000003(Occurrent):::BFO-->BFO_0000001(Entity):::BFO
	BFO_0000015(Process):::BFO-->BFO_0000003(Occurrent):::BFO
	BFO_0000035(Process<br> Boundary):::BFO-->BFO_0000003(Occurrent)
	BFO_0000008(Temporal<br> Region):::BFO-->BFO_0000003(Occurrent)
	BFO_0000011(Spatiotemporal<br> Region):::BFO-->BFO_0000003(Occurrent)
	BFO_0000182(History):::BFO-->BFO_0000015(Process):::BFO
	BFO_0000148(Zero-Dimensional<br> Temporal Region):::BFO-->BFO_0000008(Temporal<br> Region):::BFO
	BFO_0000038(One-Dimensional<br> Temporal Region):::BFO-->BFO_0000008(Temporal<br> Region):::BFO
	BFO_0000203(Temporal<br> Instant):::BFO-->BFO_0000148(Zero-Dimensional<br> Temporal Region):::BFO
	BFO_0000202(Temporal<br> Interval):::BFO-->BFO_0000038(One-Dimensional<br> Temporal Region):::BFO

    classDef BFO fill:#97c1fb,color:#060606

    ActofObserving(Act of Observing):::CCO-->BFO_0000015
    
    classDef CCO fill:#F5AD27,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```


## Class & subClassOf

```turtle
abi:ActofObserving a owl:Class ;
    rdfs:subClassOf abi:ont00000300 ;
    rdfs:comment "An act of observing is an act of perceiving, which is an act of observing."@en ;
    rdfs:label "Act of Observing"@en ;
    skos:definition "An act of observing is an act of perceiving, which is an act of observing."@en .
```

## Object Properties & subPropertyOf

```mermaid
graph BT
	BFO_0000002(Continuant):::BFO-->BFO_0000001(Entity):::BFO
	BFO_0000020(Specifically Dependent<br> Continuant):::BFO-->BFO_0000002(Continuant):::BFO
	BFO_0000031(Generically Dependent<br> Continuant):::BFO-->BFO_0000002(Continuant)
	BFO_0000004(Independent<br> Continuant):::BFO-->BFO_0000002(Continuant)
    BFO_0000003(Occurrent):::BFO-->BFO_0000001(Entity):::BFO
	BFO_0000015(Process):::BFO-->BFO_0000003(Occurrent):::BFO

    ActofObserving(Act of Observing):::CCO-->BFO_0000015
    Obs1(Accor has capabilities Diversity and Inclusion Initiatives):::Individual-->|rdf:type|ActofObserving
    Capbility1(Diversity and Inclusion Initiatives):::Individual-->BFO_0000020
    OpenAIAgent(OpenAI Agent):::Individual-->|rdf:type|BFO_0000004
    Obs1-->|has_participant|OpenAIAgent
    Obs1-->|concretizes|Capbility1

    classDef BFO fill:#97c1fb,color:#060606
    classDef CCO fill:#F5AD27,color:#060606
    classDef ABI fill:#48DD82,color:#060606
    classDef Individual fill:#dc99d7,color:#060606
```