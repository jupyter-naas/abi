# Negative Disposition

`abi:NegativeDisposition` is a subclass of [`bfo:Disposition`](http://purl.obolibrary.org/obo/BFO_0000016) that represents dispositions of security-related entities that are inherently detrimental to security posture or increase vulnerability risk.

## Definition

A **Negative Disposition** is a disposition that describes an entity's inherent tendency to manifest behaviors, properties, or reactions that weaken security controls, increase attack surface, or otherwise compromise security objectives when triggered under specific conditions.

## Examples in Cyber Security

### Vulnerability-Related Negative Dispositions
- **`abi:ExploitabilityDisposition`** - The disposition of a vulnerability to be leveraged by attackers
- **`abi:BufferOverflowVulnerabilityDisposition`** - The disposition of a system to allow memory corruption through improper boundary checks
- **`abi:SQLInjectionSusceptibilityDisposition`** - The disposition of an application to allow malicious SQL commands through improper input sanitization
- **`abi:PrivilegeEscalationDisposition`** - The disposition of a system to permit elevation of privileges through design flaws

### System Weakness Negative Dispositions
- **`abi:MisconfigurationSusceptibilityDisposition`** - The disposition of a system to remain operational with suboptimal security settings
- **`abi:DefaultCredentialPersistenceDisposition`** - The disposition of a system to maintain factory/default credentials
- **`abi:InsecureDataStorageDisposition`** - The disposition to store sensitive information without adequate protection
- **`abi:UnpatchabilityDisposition`** - The disposition of legacy systems to resist security updates

### ATT&CK-Related Negative Dispositions
- **`abi:InitialCompromiseSusceptibilityDisposition`** - The disposition to be vulnerable to initial access techniques
  - Maps to ATT&CK Tactic: Initial Access (TA0001)
- **`abi:CredentialTheftVulnerabilityDisposition`** - The disposition of credential stores to be compromised
  - Maps to ATT&CK Technique: Credential Access (TA0006)
- **`abi:LateralMovementFacilitationDisposition`** - The disposition of network architectures to enable unauthorized traversal
  - Maps to ATT&CK Tactic: Lateral Movement (TA0008)
- **`abi:EvasionSusceptibilityDisposition`** - The disposition of security controls to be circumvented
  - Maps to ATT&CK Tactic: Defense Evasion (TA0005)

### D3FEND-Related Negative Dispositions
- **`abi:DetectionBypassabilityDisposition`** - The disposition of security monitoring to be evaded
  - Countered by D3FEND techniques in the "Detect" category
- **`abi:FalsePositiveGenerationDisposition`** - The disposition of detection systems to incorrectly flag benign activity
  - Relates to D3FEND's detection confidence and signal filtering
- **`abi:CredentialCompromisabilityDisposition`** - The disposition of authentication systems to be undermined
  - Countered by D3FEND technique: Credential Compromise Scope (D3-CCS)
- **`abi:NetworkTrafficInterceptabilityDisposition`** - The disposition of network communications to be captured
  - Countered by D3FEND technique: Message Authentication (D3-MA)

### Enterprise Management Negative Dispositions
- **`abi:SecuritySkillDecayDisposition`** - The disposition of security staff skills to deteriorate without continual training
  - Results in decreased capability to defend against threats
- **`abi:ComplianceViolationDisposition`** - The disposition of organizational practices to drift from compliance requirements
  - Creates regulatory exposure and potentially violates security standards
- **`abi:IneffectiveOversightDisposition`** - The disposition of security governance to weaken without proper management attention
  - Leads to gaps in security controls and accountability
- **`abi:ResourceConstraintDisposition`** - The disposition of security operations to be undermined by insufficient resources
  - Prevents effective implementation of security measures
- **`abi:UnwantedCapabilityExposureDisposition`** - The disposition of systems to expose unnecessary functionality
  - Increases attack surface unnecessarily
- **`abi:OrganizationalSiloDisposition`** - The disposition of security teams to operate in isolation from other business units
  - Prevents effective security integration across the enterprise
- **`abi:SecurityDebtAccumulationDisposition`** - The disposition of organizations to defer security investments
  - Similar to technical debt, but specific to security controls
- **`abi:KnowledgeFragmentationDisposition`** - The disposition of security knowledge to remain isolated and undocumented
  - Creates dependencies on key personnel and limits institutional knowledge

## Ontological Relationships

### Parent Class
- [`bfo:Disposition`](http://purl.obolibrary.org/obo/BFO_0000016) - A disposition is a realizable entity that exists because of certain features of the physical makeup of the independent continuant that is its bearer.

### Sibling Classes
- `abi:NeutralDisposition` - Dispositions that are neither intrinsically positive nor negative
- `abi:PositiveDisposition` - Dispositions that are beneficial for security posture

### Bearer Types
Negative dispositions can be borne by various cyber security entities, including:
- Software applications
- Network components
- System configurations
- Security controls
- User interfaces
- Authentication mechanisms
- Legacy systems
- Security teams
- Organizational structures
- Governance processes
- Resource allocation systems

## Implementation Notes

When modeling negative dispositions, consider:

1. **Severity**: The potential impact if the disposition is realized
2. **Likelihood**: The probability of the disposition being triggered
3. **Exploitability**: How easily the disposition can be leveraged by attackers
4. **Mitigability**: Whether and how the disposition can be neutralized
5. **Detectability**: Whether manifestations of the disposition can be observed
6. **Organizational Impact**: How the disposition affects enterprise operations and objectives
7. **Remediation Complexity**: The organizational effort required to address the disposition

## Usage in Risk Assessment

Negative dispositions provide a framework for understanding:

- System vulnerabilities and their root causes
- Attack vectors and their enablers
- Security control gaps and their origins
- Defense evasion opportunities
- Systemic security weaknesses
- Organizational security deficiencies
- Security management inefficiencies
- Governance and compliance risks

These dispositions are crucial components in comprehensive risk assessments, vulnerability management programs, and threat modeling exercises. They represent the inherent "weak points" that require additional controls, architectural changes, or organizational improvements to mitigate. 