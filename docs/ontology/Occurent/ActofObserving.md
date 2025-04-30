# Act of Observing


## Aristotelian Definitions of `abi:Actof...` Classes

Each `Actof` is defined as a subclass of `bfo:0000015` (Process), using an Aristotelian genus–differentia structure: 
> *An X is a process that Y.*


### abi:ActofObserving
- **Definition**: An act of observing is a process that involves perceiving, detecting, or identifying entities, patterns, or phenomena.
- **Genus**: bfo:0000015 (Process)
- **Differentia**: that is directed toward acquiring information or knowledge about reality.


## Extended Ontology: ABI-Aligned `Actof...` Processes

### 🛰 Open Source Intelligence

- **abi:ActofScraping**: A process that extracts data from web-based or digital content sources using automated agents.
- **abi:ActofCrawling**: A process that systematically navigates digital networks to index or discover content.
- **abi:ActofEnrichment**: A process that augments data by linking it to external classifications, ontologies, or tags.
- **abi:ActofTagging**: A process that assigns semantic labels to entities, documents, or data points.
- **abi:ActofSignalDetection**: A process that identifies relevant or anomalous signals within a noisy information environment.
- **abi:ActofObservation**: A process that captures and records a change or feature of reality.


### 🧠 Content Creation

- **abi:ActofIdeation**: A process that generates conceptual representations or potential communication artifacts.
- **abi:ActofDrafting**: A process that initiates the formal creation of content in raw or outline form.
- **abi:ActofGeneration**: A process that produces a complete piece of content, possibly using machine learning models.
- **abi:ActofReviewing**: A process that evaluates, edits, or approves content through human judgment.
- **abi:ActofPublishing**: A process that distributes a content item to a specific communication channel.
- **abi:ActofRecycling**: A process that reuses or transforms existing content into a new format or context.


### 📣 Growth Marketing

- **abi:ActofCampaignPlanning**: A process that defines objectives, channels, and audiences for a marketing campaign.
- **abi:ActofLaunching**: A process that initiates the release of planned communication or promotion.
- **abi:ActofTrackingEngagement**: A process that monitors interactions with distributed media.
- **abi:ActofScoringEngagement**: A process that evaluates the quality or relevance of interactions.
- **abi:ActofAttribution**: A process that links downstream actions (e.g., conversions) to upstream touchpoints.


### 🤝 Sales Conversion

- **abi:ActofProspecting**: A process that identifies and qualifies new sales leads or opportunities.
- **abi:ActofOutreach**: A process that initiates contact with potential clients or stakeholders.
- **abi:ActofMeeting**: A process that facilitates live or asynchronous interaction between buyer and seller.
- **abi:ActofDealCreation**: A process that defines the parameters of a business transaction.
- **abi:ActofNegotiation**: A process that iteratively adjusts deal terms through offer and response.
- **abi:ActofClosing**: A process that finalizes a transaction through agreement or signature.


### ⚙ Operational Efficiency

- **abi:ActofTaskAssignment**: A process that designates responsibility for a specific task to an agent.
- **abi:ActofWorkflowExecution**: A process that performs a set of interrelated operational tasks.
- **abi:ActofAssetManagement**: A process that organizes, stores, and updates internal resources.
- **abi:ActofKnowledgeCapture**: A process that records expert input, feedback, or decision context.
- **abi:ActofReporting**: A process that generates formal representations of operational status.


### 💰 Finance & Cash Flow

- **abi:ActofContractCreation**: A process that establishes formal legal agreements.
- **abi:ActofBilling**: A process that issues financial demands based on contract terms.
- **abi:ActofAccountsReceivableTracking**: A process that monitors expected incoming payments.
- **abi:ActofAccountsPayableTracking**: A process that monitors obligations to external parties.
- **abi:ActofCashReconciliation**: A process that validates the alignment between expected and actual cash movements.
- **abi:ActofCashForecasting**: A process that estimates future cash positions.
- **abi:ActofRevenueRecognition**: A process that matches realized value to accounting periods.


### 🧩 Cross-Domain

- **abi:ActofValidation**: A process that verifies the correctness, reliability, or applicability of an observation or action.
- **abi:ActofScoring**: A process that assigns a numerical or qualitative assessment to an entity.
- **abi:ActofDecisionMaking**: A process that selects one or more courses of action based on observations.
- **abi:ActofAnnotation**: A process that adds contextual metadata to a resource.
- **abi:ActofExplanation**: A process that generates a justification or rationale for an action, classification, or observation.


> Each `Actof...` is a subclass of `bfo:0000015 (Process)` and can be directly tied to observations, agents, roles, and outcomes in the ABI ontology.

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