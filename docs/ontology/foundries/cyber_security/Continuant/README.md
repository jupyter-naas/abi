# Continuant: Cyber Security Foundry

This folder contains ontology classes representing **Continuants** in the context of the **Cyber Security Foundry** of the ABI Ontology.

Continuants are entities that **persist through time** and may carry roles, properties, or states that inform how security is modeled, enforced, or governed within an enterprise.

## Purpose
To model all stable entities involved in cybersecurity management — including agents, assets, access rights, and dependent properties (like trust, roles, or categories).

## Structure
In this folder, we include:

### 1. **Independent Continuants** (`bfo:0000004`)
Entities that do not depend on other entities for their existence.

#### a. **Material Entities** (`bfo:0000040`)
Entities that have physical or instantiated digital presence.
- `abi:SecurityAgent`
- `abi:FirewallDevice`
- `abi:MonitoringService`
- `abi:UserAccount`
- `abi:CredentialVault`

#### b. **Immaterial Entities** (`bfo:0000141`)
Independent continuants that have no material parts at any time.
- `abi:SecurityPerimeter`
- `abi:SecurityDomainBoundary` 
- `abi:AccessControlZone`
- `abi:TrustBoundary`
- `abi:SecuritySite`

### 2. **Specifically Dependent Continuants** (`bfo:0000020`)
Entities that depend on specific bearers for their existence.

#### a. **Roles** (`bfo:0000023`)
- `abi:SecurityOfficerRole`
- `abi:SOCAnalystRole`

#### b. **Qualities** (`bfo:0000019`)
- `abi:CredentialStrength`
- `abi:ThreatLevel`

#### c. **Functions** (`bfo:0000034`)
- `abi:BlockAccessFunction`
- `abi:LogActivityFunction`

#### d. **Dispositions** (`bfo:0000016`)
- `abi:VulnerabilityDisposition`
- `abi:EscalatesOnThreatDisposition`

### 3. **Generically Dependent Continuants** (`bfo:0000031`)
Information artifacts that can be concretized in multiple bearers.
- `abi:SecurityPolicyDocument`
- `abi:AccessLogEntry`
- `abi:ThreatClassificationLabel`

## BFO Hierarchy

```mermaid
graph LR
    BFO_0000002(Continuant)-->BFO_0000001(Entity):::BFO
    BFO_0000020(Specifically Dependent<br> Continuant)-->BFO_0000002(Continuant):::BFO
    BFO_0000031(Generically Dependent<br> Continuant):::BFO-->BFO_0000002(Continuant)
    BFO_0000004(Independent<br> Continuant)-->BFO_0000002(Continuant)
    
    BFO_0000040(Material Entity)-->BFO_0000004(Independent<br> Continuant):::BFO
    BFO_0000141(Immaterial<br> Entity)-->BFO_0000004(Independent<br> Continuant)
    
    abi_SecurityAgent(abi:SecurityAgent):::ABI-->BFO_0000040
    abi_FirewallDevice(abi:FirewallDevice):::ABI-->BFO_0000040
    abi_MonitoringService(abi:MonitoringService):::ABI-->BFO_0000040
    abi_UserAccount(abi:UserAccount):::ABI-->BFO_0000040
    abi_CredentialVault(abi:CredentialVault):::ABI-->BFO_0000040
    
    abi_SecurityPerimeter(abi:SecurityPerimeter):::ABI-->BFO_0000141
    abi_SecurityDomainBoundary(abi:SecurityDomainBoundary):::ABI-->BFO_0000141
    abi_AccessControlZone(abi:AccessControlZone):::ABI-->BFO_0000141
    abi_TrustBoundary(abi:TrustBoundary):::ABI-->BFO_0000141
    abi_SecuritySite(abi:SecuritySite):::ABI-->BFO_0000141
    
    BFO_0000023(Role)-->BFO_0000020
    BFO_0000019(Quality)-->BFO_0000020
    BFO_0000034(Function)-->BFO_0000020
    BFO_0000016(Disposition)-->BFO_0000020
    
    abi_SecurityOfficerRole(abi:SecurityOfficerRole):::ABI-->BFO_0000023
    abi_SOCAnalystRole(abi:SOCAnalystRole):::ABI-->BFO_0000023
    
    abi_CredentialStrength(abi:CredentialStrength):::ABI-->BFO_0000019
    abi_ThreatLevel(abi:ThreatLevel):::ABI-->BFO_0000019
    
    abi_BlockAccessFunction(abi:BlockAccessFunction):::ABI-->BFO_0000034
    abi_LogActivityFunction(abi:LogActivityFunction):::ABI-->BFO_0000034
    
    abi_VulnerabilityDisposition(abi:VulnerabilityDisposition):::ABI-->BFO_0000016
    abi_EscalatesOnThreatDisposition(abi:EscalatesOnThreatDisposition):::ABI-->BFO_0000016
    
    abi_SecurityPolicyDocument(abi:SecurityPolicyDocument):::ABI-->BFO_0000031
    abi_AccessLogEntry(abi:AccessLogEntry):::ABI-->BFO_0000031
    abi_ThreatClassificationLabel(abi:ThreatClassificationLabel):::ABI-->BFO_0000031

    classDef BFO fill:#97c1fb,color:#060606
    classDef ABI fill:#48DD82,color:#060606
```

## Usage
These classes are designed to:
- Represent agents and systems involved in security infrastructure
- Assign evaluative properties (e.g., credential risk, account trust level)
- Track semantic metadata such as audit logs or labels
- Enable linkage to Occurrent processes (e.g., threat detection, credential rotation)


## Alignment
All classes in this folder:
- Are subclasses of `bfo:Continuant`
- Are scoped specifically to the **Cyber Security Foundry**
- Can be imported modularly or reused in ESG, Governance, and Ops domains


For dynamic, time-based processes (e.g. detection, revocation), see the `Occurrent` folder.