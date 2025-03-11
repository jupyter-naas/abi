from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.modules.common.integrations.SiteDownloader import SiteDownloader, SiteDownloaderConfiguration
from src import secret, config
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.modules.common.integrations.LocalObjectStoreIntegration import LocalObjectStoreIntegration, LocalObjectStoreConfiguration

from tqdm import tqdm
from queue import Queue, Empty
from threading import Thread
from rdflib import RDF, RDFS
from lib.abi.utils.Graph import ABIGraph as Graph
import string

from lib.abi.utils.OntologyReasoner import OntologyReasoner

ONTOLOGY = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dc11: <http://purl.org/dc/elements/1.1/> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix cco: <https://www.commoncoreontologies.org/> .
@prefix abi: <http://ontology.naas.ai/abi/> .

<http://ontology.naas.ai/abi/OrganizationOntology> a owl:Ontology ;
    owl:imports <https://www.commoncoreontologies.org/AgentOntology> ;
    owl:versionIRI <https://github.com/jupyter-naas/abi/tree/cli/src/ontologies/domain-level/OrganizationOntology.ttl> ;
    dc11:contributor "Jeremy Ravenel" , "Maxime Jublou" , "Florent Ravenel" ;
    dc:description "Domain ontology for organizations."@en ;
    dc:license "" ;
    dc:title "Organization Ontology" .

#################################################################
#    Classes
#################################################################

#--- CCO Agent Ontology ---#

# Organization

cco:ont00001180 a owl:Class ;
    rdfs:subClassOf cco:ont00000300 ;
    rdfs:comment "Members of organizations are either Organizations themselves or individual Persons. Members can bear specific Organization Member Roles that are determined in the organization rules. The organization rules also determine how decisions are made on behalf of the Organization by the organization members."@en ;
    rdfs:label "Organization"@en ;
    skos:definition "A Group of Agents which can be the bearer of roles, has members, and has a set of organization rules."@en ;
    cco:ont00001754 "http://purl.obolibrary.org/obo/OBI_0000245" ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

cco:ont00000443 a owl:Class ;
    rdfs:subClassOf cco:ont00001180 ;
    rdfs:label "Commercial Organization"@en ;
    skos:definition "An Organization that is the bearer of a Commercial Role and whose primary objective is to make a profit from the provision of goods or services."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:Subsidiary a owl:Class ;
    rdfs:subClassOf cco:ont00001180 ;
    rdfs:label "Subsidiary"@en ;
    skos:definition "An Organization that is controlled by another Organization, known as the parent company, and operates as a separate legal entity but under the strategic direction of the parent."@en ;
    skos:example "Company X, a subsidiary of Corporation Y, which manages operations in a specific region."@en ,
                 "Brand Z, a wholly-owned subsidiary of Conglomerate W, focusing on consumer electronics."@en ;
    rdfs:comment "Subsidiaries are Organizations that are controlled by another Organization." .

abi:JointVenture a owl:Class ;
    rdfs:subClassOf cco:ont00001180 ;
    rdfs:label "Joint Venture"@en ;
    skos:definition "An Organization formed by two or more parties, typically corporations, for the purpose of undertaking a specific project or business activity, with shared ownership, risks, and profits."@en ;
    skos:example "Company A and Company B forming a joint venture to develop a new software product."@en ,
                 "Enterprises C and D creating a joint venture to explore new markets in a foreign country."@en ;
    rdfs:comment "Joint ventures are Organizations formed through collaboration between multiple parties." .

abi:PreMergerAndAcquisition a owl:Class ;
    rdfs:subClassOf cco:ont00001180 ;
    rdfs:label "Pre-Merger and Acquisition"@en ;
    skos:definition "An Organization that existed as an independent entity prior to being involved in a merger or acquisition, maintaining its own operations, resources, and strategic goals before consolidation into a single entity."@en ;
    skos:example "Company A and Company B before merging to form Company AB."@en ,
                 "Organization C before being acquired by Corporation D."@en ;
    rdfs:comment "Pre-merger and acquisition organizations are independent entities that later become part of mergers or acquisitions." .

abi:Competitor a owl:Class ;
    rdfs:subClassOf cco:ont00001180 ;
    rdfs:label "Competitor"@en ;
    skos:definition "An Organization that operates in the same industry or market as another organization and offers similar goods or services, often striving to gain competitive advantage."@en ;
    skos:example "Company A and Company B both producing consumer electronics and competing for market share."@en ,
                 "Restaurant X and Restaurant Y both offering Italian cuisine in the same city."@en ;
    rdfs:comment "Competitors are Organizations that operate in the same industry or market and compete by offering similar goods or services." .

# Members

cco:ont00000647 a owl:Class ;
    owl:equivalentClass [ owl:intersectionOf ( cco:ont00001262
                                            [ a owl:Restriction ;
                                                owl:onProperty bfo:BFO_0000196 ;
                                                owl:someValuesFrom cco:ont00000175
                                            ]
                                            ) ;
                        a owl:Class
                        ] ;
    rdfs:subClassOf cco:ont00001262 ,
                    [ a owl:Restriction ;
                    owl:onProperty cco:ont00001939 ;
                    owl:someValuesFrom cco:ont00001180
                    ] ;
    rdfs:label "Organization Member"@en ;
    skos:definition "A Person who is affiliated with some Organization by being a member of that Organization."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

cco:ont00000175 a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;
    rdfs:label "Organization Member Role"@en ;
    skos:definition "A Role that inheres in an Agent in virtue of the responsibilities that Agent is expected to fulfill as a member of some Organization."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .


abi:ExecutiveCommittee a owl:Class ;
    rdfs:subClassOf cco:ont00000914 ;
    rdfs:label "Executive Committee" ;
    skos:definition "An Executive Committee is a group of individuals who are responsible for the strategic direction and decision-making of an organization." ;
    skos:example "The executive committee of Apple Inc." ;
    rdfs:comment "An Executive Committee is a group of individuals who are responsible for the strategic direction and decision-making of an organization." .

abi:BoardOfDirectors a owl:Class ;
    rdfs:subClassOf cco:ont00000914 ;
    rdfs:label "Board of Directors" ;
    skos:definition "A Board of Directors is a group of individuals who are responsible for the strategic direction and decision-making of an organization." ;
    skos:example "The board of directors of Apple Inc." ;
    rdfs:comment "A Board of Directors is a group of individuals who are responsible for the strategic direction and decision-making of an organization." .

# Capabilities

abi:TechnologicalCapabilities a owl:Class ;
    rdfs:subClassOf cco:ont00000568 ;
    rdfs:label "Technological Capabilities"@en ;
    skos:definition "The technological abilities, systems, and expertise possessed by an organization."@en ;
    skos:example "AI, Cloud Computing, Data Analytics, etc." ;
    rdfs:comment "Technological Capabilities are the technological abilities, systems, and expertise possessed by an organization." .

abi:HumanCapabilities a owl:Class ;
    rdfs:subClassOf cco:ont00000568 ;
    rdfs:label "Human Capabilities"@en ;
    skos:definition "The human skills, knowledge, and expertise possessed by an organization's workforce."@en ;
    skos:example "Software Development, Consulting Services, Marketing Campaigns, etc." ;
    rdfs:comment "Human Capabilities are the skills, knowledge, and expertise possessed by an organization's workforce." .

#--- CCO Events Ontology ---#

abi:ActOfMergersAndAcquisitions a owl:Class ;
    rdfs:subClassOf cco:ont00001327 ;
    rdfs:label "Act of Mergers and Acquisitions"@en ;
    skos:definition "A Social Act involving the combination of two or more organizations into a single entity, or the acquisition of one organization by another, often involving the transfer of assets, liabilities, and organizational control."@en ;
    skos:example "The merger of Company A and Company B to form a new Company AB."@en ,
                 "The acquisition of Company C by Company D, where Company D takes over the assets and operations of Company C."@en ;
    rdfs:comment "Mergers and acquisitions are planned acts that affect organizations, which are social entities. These acts involve agreements and transactions between organizations, making them inherently social activities." .
    
abi:ActOfJointVenture a owl:Class ;
    rdfs:subClassOf cco:ont00000433 ;
    rdfs:label "Act of Joint Venture"@en ;
    skos:definition "An Act of Association wherein two or more organizations come together to undertake a specific project or business activity, sharing resources, risks, and rewards, while maintaining their distinct legal identities."@en ;
    skos:example "Company E and Company F forming a joint venture to develop a new technology product."@en ,
                 "Organization G and Organization H entering a joint venture to explore natural resources in a specific region."@en ;
    rdfs:comment "A joint venture represents a collaborative business arrangement where organizations pool their resources for a specific purpose while remaining separate entities." .

#--- CCO Facility Ontology ---#

abi:GlobalHeadquarters a owl:Class ;
    rdfs:subClassOf cco:ont00001102 ; # Commercial Facility
    rdfs:label "Global Headquarters"@en ;
    skos:definition "A Facility that serves as the central office for an organization on a global scale, providing strategic direction and administrative functions across all regions where the organization operates."@en ;
    skos:example "The global headquarters of a multinational corporation located in New York City."@en ;
    rdfs:comment "A Facility that serves as the central office for an organization on a global scale, providing strategic direction and administrative functions across all regions where the organization operates." .

abi:RegionalHeadquarters a owl:Class ;
    rdfs:subClassOf cco:ont00001102 ; # Commercial Facility
    rdfs:label "Regional Headquarters"@en ;
    skos:definition "A Facility that serves as the central office for an organization within a specific region, overseeing operations and providing strategic direction and administrative functions for that region."@en ;
    skos:example "The regional headquarters of a company overseeing operations in Europe, based in Berlin."@en ;
    rdfs:comment "A Facility that serves as the central office for an organization within a specific region, overseeing operations and providing strategic direction and administrative functions for that region." .

cco:ont00000468 rdf:type owl:Class ;
    rdfs:subClassOf cco:ont00001102 ;
    rdfs:label "Office Building"@en ;
    skos:definition "A Commercial Facility that is designed as an environment for conducting commercial, professional, or bureaucratic work."@en ;
    cco:ont00001754 "https://en.wikipedia.org/w/index.php?title=Office&oldid=1063508719"^^xsd:anyURI ;
    cco:ont00001760 "https://www.commoncoreontologies.org/FacilityOntology"^^xsd:anyURI .

cco:ont00000262 rdf:type owl:Class ;
    rdfs:subClassOf cco:ont00001102 ;
    rdfs:label "Shop"@en ;
    skos:definition "A Commercial Facility designed to sell small lots of goods to consumers."@en ;
    cco:ont00001754 "https://en.wikipedia.org/w/index.php?title=Retail&oldid=1061431295"^^xsd:anyURI ;
    cco:ont00001760 "https://www.commoncoreontologies.org/FacilityOntology"^^xsd:anyURI .

cco:ont00000782 rdf:type owl:Class ;
    rdfs:subClassOf cco:ont00000192 ;
    rdfs:label "Factory"@en ;
    skos:definition "A Facility that is designed for manufacturing or refining material products."@en ;
    cco:ont00001754 "https://en.wikipedia.org/w/index.php?title=Factory&oldid=1064125324"^^xsd:anyURI ;
    cco:ont00001760 "https://www.commoncoreontologies.org/FacilityOntology"^^xsd:anyURI .

#--- CCO Information Content Ontology ---#

abi:StrategicAlliance a owl:Class ;
    rdfs:subClassOf cco:ont00000853 ;
    rdfs:label "Strategic Alliance"@en ;
    skos:definition "An Information Content Entity that describes an agreement between two or more organizations to pursue a set of agreed-upon objectives while remaining independent entities."@en ;
    skos:example "A memorandum of understanding (MOU) between a technology company and a software provider"@en ,
                 "A strategic collaboration agreement in the automotive sector"@en ;
    rdfs:comment "Strategic alliances are typically formalized through documents and agreements, making them apt to be represented as Descriptive Information Content Entities." .

abi:Partnership a owl:Class ;
    rdfs:subClassOf cco:ont00000853 ;
    rdfs:label "Partnership"@en ;
    skos:definition "An Information Content Entity that details a formal agreement between two or more parties to manage and operate a business and share its profits and losses."@en ;
    skos:example "The partnership agreement document for a law firm, a business plan outlining the roles of partners in a medical practice."@en ;
    rdfs:comment "A partnership is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity." .

abi:KPI a owl:Class ;
    rdfs:subClassOf cco:ont00001163 ;
    rdfs:label "Key Performance Indicator"@en ;
    skos:definition "A Key Performance Indicator (KPI) is a measurable value that demonstrates how effectively an organization is achieving key business objectives."@en ;
    skos:example "Revenue, Customer Satisfaction, Employee Retention, etc."@en ;
    rdfs:comment "A Key Performance Indicator (KPI) is a measurable value that demonstrates how effectively an organization is achieving key business objectives." .

abi:MarketSegment a owl:Class ;
    rdfs:subClassOf cco:ont00000958 ;
    rdfs:label "Market Segment"@en ;
    skos:definition "A Market Segment is an Information Content Entity that represents a specific segment of the market."@en ;
    skos:example "Technology, Finance, Healthcare, etc."@en ;
    rdfs:comment "Market Segments are used to categorize the market of an organization." .

abi:OrganizationSize a owl:Class ;
    rdfs:subClassOf cco:ont00000958 ;
    rdfs:label "Organization Size"@en ;
    skos:definition "An Organization Size is an Information Content Entity that represents a range of staff size within an organization." ;
    skos:example "Micro Enterprise, Small Enterprise, SMEs, Large Enterprise." ;
    rdfs:comment "Organization Sizes are used to categorize the size of an organization." .

abi:BusinessDomain a owl:Class ;
    rdfs:subClassOf cco:ont00000958 ;
    rdfs:label "Business Domain" ;
    skos:definition "A Business Domain is an Information Content Entity that represents a specific area of expertise or activity within an organization, characterized by distinct processes, goals, and practices." ;
    skos:example "Marketing, Sales, Engineering, etc." ;
    rdfs:comment "Business Domains are specialized areas within an organization that focus on specific business functions or activities." .

abi:Industry a owl:Class ;
    rdfs:subClassOf cco:ont00000958 ;
    rdfs:label "Industry" ;
    skos:definition "An Industry is an Information Content Entity that represents a broad category of businesses or organizations that produce similar products or services within a market." ;
    skos:example "Technology, Finance, Healthcare, etc." ;
    rdfs:comment "Industries encompass the collective market activities and economic sector of companies producing similar goods or services." .

#--- BFO ---#

abi:Positioning a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000023 ;
    rdfs:label "Positioning"@en ;
    skos:definition "The strategic position and differentiation of an organization in its market."@en ;
    skos:example "Leader, Cost-effective, High-quality, etc."@en ;
    rdfs:comment "Positioning is the strategic position and differentiation of an organization in its market." .

#################################################################
#    Object Properties
#################################################################

abi:hasKPI a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000101 ; # is carrier of
    rdfs:domain cco:ont00001180 ;
    rdfs:range abi:KPI ;
    rdfs:label "has indicator"@en ;
    skos:definition "Relates an Organization to its key performance indicators."@en .

abi:hasLegalName a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000101 ; # is carrier of
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00001331 ;
    rdfs:label "has legal name"@en ;
    skos:definition "Relates an Organization to its legal name, which is a formally registered designation of the organization."@en .

cco:ont00001794 a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001977 ;
    owl:inverseOf cco:ont00001815 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00001180 ;
    rdfs:label "has subsidiary"@en ;
    skos:definition "An Organization o1 has_subsidiary Organization o2 iff o1 controls o2 by having the capacity to determine the outcome of decisions about o2's financial and operating policies."@en ;
    cco:ont00001754 "http://www.austlii.edu.au/legis/cth/consol_act/ca2001172/s50aa.html" ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

cco:ont00001815 a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001939 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00001180 ;
    rdfs:label "is subsidiary of"@en ;
    skos:definition "An Organization o2 is_subsidiary_of Organization o1 iff o1 controls o2 by having the capacity to determine the outcome of decisions about o2's financial and operating policies. "@en ;
    cco:ont00001754 "http://www.austlii.edu.au/legis/cth/consol_act/ca2001172/s50aa.html)" ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:hasJointVenture a owl:ObjectProperty ;  
    rdfs:subPropertyOf cco:ont00001977 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range abi:JointVenture ;
    rdfs:label "has joint venture"@en ;
    skos:definition "An Organization o1 has_joint_venture Organization o2 iff o1 and o2 are instances of an Organization and o2 is an instance of a Joint Venture, such that o1 and o2 are partners in the joint venture."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:hasMergerAndAcquisition a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001977 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range abi:MergerAndAcquisition ;
    rdfs:label "has merger and acquisition"@en ;
    skos:definition "An Organization o1 has_merger_and_acquisition Organization o2 iff o1 and o2 are instances of an Organization and o2 is an instance of a Merger And Acquisition, such that o1 and o2 are partners in the merger and acquisition."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:hasOrganizationMember a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001977 ; # has affiliate
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00000647 ;
    rdfs:label "has organization member"@en ;
    skos:definition "An Organization o1 has_organization_member Person p1 iff p1 is an instance of an Organization Member and o1 is an instance of an Organization, such that p1 is a member of o1."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:isOrganizationMemberOf a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001939 ; # is affiliated with
    rdfs:domain cco:ont00000647 ;
    rdfs:range cco:ont00001180 ;
    rdfs:label "is organization member of"@en ;
    skos:definition "A Person p1 is_organization_member_of Organization o1 iff p1 is an instance of an Organization Member and o1 is an instance of an Organization, such that p1 is a member of o1."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:hasOrganizationMemberRole a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001992 ; # has organizational context
    rdfs:domain cco:ont00000647 ;
    rdfs:range cco:ont00000175 ;
    rdfs:label "has organization member role"@en ;
    skos:definition "An Organization Member o1 has_organization_member_role Role r1 iff o1 is an instance of an Organization Member and r1 is an instance of an Organization Member Role, such that o1 bears r1."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

abi:isOrganizationMemberRoleOf a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:ont00001846 ; # is organizational context of
    rdfs:domain cco:ont00000175 ;
    rdfs:range cco:ont00000647 ;
    rdfs:label "is organization member role of"@en ;
    skos:definition "A Role r1 is_organization_member_role_of Organization o1 iff r1 is an instance of an Organization Member Role and o1 is an instance of an Organization, such that r1 is a role of o1."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI .

cco:ont00001954 a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000196 ;
    rdfs:domain cco:ont00001017 ;
    rdfs:range cco:ont00001379 ;
    rdfs:label "has capability"@en ;
    skos:definition "x has_capability y iff x is an instance of Agent and y is an instance of Agent Capability, such that x bearer of y."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI ;
    skos:example "The organization has the capability to develop software."@en .

cco:ont00001889 a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000197 ;
    owl:inverseOf cco:ont00001954 ;
    rdfs:domain cco:ont00001379 ;
    rdfs:range cco:ont00001017 ;
    rdfs:label "capability of"@en ;
    skos:definition "x capability_of y iff y is an instance of Agent and x is an instance of Agent Capability, such that x inheres in y."@en ;
    cco:ont00001760 "https://www.commoncoreontologies.org/AgentOntology"^^xsd:anyURI ;
    skos:example "Developing software (TechnologicalCapabilities) is a capability of the organization."@en .

abi:enablesOffering a owl:ObjectProperty ;
    rdfs:domain cco:ont00000568 ; # Organization Capabilities
    rdfs:range abi:Offering ;
    rdfs:label "enables_offering"@en ;
    skos:definition "Relates capabilities to the offerings they enable or support."@en .

abi:isEnabledBy a owl:ObjectProperty ;
    rdfs:domain abi:Offering ;
    rdfs:range cco:ont00000568 ; # Organization Capabilities
    owl:inverseOf abi:enablesOffering ;
    rdfs:label "is_enabled_by"@en ;
    skos:definition "Relates offerings back to the capabilities that enable them."@en .

abi:hasPositioning a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000218 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range abi:Positioning ;
    rdfs:label "has_positioning"@en ;
    skos:definition "Relates an organization to its market positioning."@en ;
    skos:example "The company has a positioning in the market."@en .

abi:isPositioningOf a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000127 ;
    rdfs:domain abi:Positioning ;
    rdfs:range cco:ont00001180 ;
    owl:inverseOf abi:hasPositioning ;
    rdfs:label "is_positioning_of"@en ;
    skos:definition "Relates positioning back to its organization."@en ;
    skos:example "The positioning is of the company."@en .

abi:hasCompetitor a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000115 ;
    rdfs:domain cco:ont00001180 ; # Organization
    rdfs:range abi:Competitor ;
    rdfs:label "has competitor"@en ;
    skos:definition "Relates an organization to its competitors."@en ;
    skos:example "The company has a competitor."@en .

abi:isCompetitorOf a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000129 ;
    rdfs:domain abi:Competitor ;
    rdfs:range cco:ont00001180 ; # Organization
    owl:inverseOf abi:hasCompetitor ;
    rdfs:label "is_competitor_of"@en ;
    skos:definition "Relates competitors back to their organization."@en ;
    skos:example "The competitor is of the company."@en .

abi:hasOperationalArea a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000056 ;
    rdfs:domain cco:ont00001180 ; # Organization
    rdfs:range cco:ont00000487 ; # Operational Area subclass of Geospatial Location
    rdfs:label "has operational area" ;
    skos:definition "Relates an Organization to an Operational Area where it conducts specific activities or operations." ;
    rdfs:comment "The property 'hasOperationalArea' relates an Organization to an Operational Area where it conducts specific activities or operations." .

abi:hasOrganizationSize a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000115 ;
    rdfs:domain cco:ont00001180 ; # Organization
    rdfs:range abi:OrganizationSize ;
    rdfs:label "has organization size"@en ;
    skos:definition "A relation between an organization and its organization size."@en ;
    rdfs:comment "This property captures the relationship between an organization and the size of its staff, which is crucial for understanding the organizational structure and capacity." .

abi:hasBusinessDomain a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000129 ;
    rdfs:domain cco:ont00001180 ; # Organization
    rdfs:range abi:BusinessDomain ;
    rdfs:label "has business domain" ;
    skos:definition "Relates an Organization to the Business Domain it operates in, indicating the specific areas of expertise or activity within the organization." ;
    rdfs:comment "This property links an organization to its internal areas of specialization and activity." .

abi:operatesInIndustry a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000115 ;
    rdfs:domain cco:ont00001180 ; # Changed from ont00000647 to ont00001180 (Organization)
    rdfs:range abi:Industry ;
    rdfs:label "operates in industry" ;
    skos:definition "Relates an Organization to the Industry in which it operates, indicating the broader market category of its products or services." ;
    rdfs:comment "This property connects an organization to the wider economic sector it belongs to, based on its market activities." .

abi:hasFacility a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000218 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00000192 ;
    rdfs:label "has facility" ;
    skos:definition "Relates an Organization to its Facility." ;
    rdfs:comment "This property connects an organization to its facilities." .

abi:hasMarketSegment a owl:ObjectProperty ;
    rdfs:subPropertyOf bfo:BFO_0000218 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range abi:MarketSegment ;
    rdfs:label "has market segment" ;
    skos:definition "Relates an Organization to its Market Segment." ;
    rdfs:comment "This property connects an organization to its market segment, indicating the segment of the market it operates in." .

abi:hasPartnership a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:BFO_0000056 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00000958 ;
    rdfs:label "has_partnership"@en ;
    skos:definition "Relates an organization to its partnerships with other organizations."@en .

abi:hasStrategicAlliance a owl:ObjectProperty ;
    rdfs:subPropertyOf cco:BFO_0000056 ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range cco:ont00000958 ;
    rdfs:label "has_strategic_alliance"@en ;
    skos:definition "Relates an organization to its strategic alliances with other organizations."@en .

#################################################################
#    Data Properties
#################################################################

abi:logo a owl:DatatypeProperty ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range xsd:string ;
    rdfs:label "logo" ;
    skos:definition "The URL of the logo of the organization." ;
    skos:example "https://www.naas.ai/logo.png" .

abi:explanation a owl:DatatypeProperty ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range xsd:string ;
    rdfs:label "explanation" ;
    rdfs:definition "The explanation of the analysis." .

abi:source_url a owl:DatatypeProperty ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range xsd:string ;
    rdfs:label "source_url" ;
    skos:definition "The URL of the source of the analysis." .

abi:source a owl:DatatypeProperty ;
    rdfs:domain cco:ont00001180 ;
    rdfs:range xsd:string ;
    rdfs:label "source" ;
    skos:definition "The source of the analysis." .
"""

SYSTEM_PROMPT =f"""You are an expert in extracting information from websites.


You must extract knowledge from provided text and create the proper ontology owl:NamedIndividual base on the following ontology. You must be very exhaustive.

ONLY CREATE NEW CLASSES IF IT IS NOT POSSIBLE TO CREATE A owl:NamedIndividual.

YOU MUST ONLY OUTPUT THE TURTLE RESULT, YOUR OUTPUT WILL BE DIRECTLT STORED AS TTL. IT MUST BE VALID TURTLE.
DO NOT PUT THE RESULT IN A CODE BLOCK, JUST OUTPUT THE RESULT.

Ontology:

{ONTOLOGY}
"""

@dataclass
class ExtractWebsiteWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ExtractWebsiteWorkflow.
    
    Attributes:
        site_downloader_config (SiteDownloaderConfiguration): Configuration for the site downloader integration
    """
    site_downloader_config: SiteDownloaderConfiguration

class ExtractWebsiteWorkflowParameters(WorkflowParameters):
    """Parameters for ExtractWebsiteWorkflow execution.
    
    Attributes:
        url (str): The URL to extract content from
        extract_sitemap (bool): Whether to extract the sitemap (optional)
    """
    url: str = Field(..., description="The URL to extract content from")

class ExtractWebsiteWorkflow(Workflow):
    """Workflow for extracting content from websites."""
    
    __configuration: ExtractWebsiteWorkflowConfiguration
    
    def __init__(self, configuration: ExtractWebsiteWorkflowConfiguration):
        self.__configuration = configuration
        self.__site_downloader = SiteDownloader(self.__configuration.site_downloader_config)
        
        self.__object_store = LocalObjectStoreIntegration(LocalObjectStoreConfiguration(base_path="data/opendata/extract_website"))
        
        # Prepare an Openai ChatCompletion
        self.__chat_completion = ChatOpenAI(
            model="gpt-4o-2024-08-06", 
            temperature=0.3, 
            api_key=secret.get('OPENAI_API_KEY')
        )
        

    def __sanitize_url(self, url: str) -> str:
        return url.replace("https://", "").replace("http://", "").replace("www.", "").replace('/', '__')

    def __get_sitemap(self, url: str) -> dict:
        sitemap_key = f"{self.__sanitize_url(url)}_sitemap.json"
        
        # Get cached version of sitemap
        try:
            sitemap = self.__object_store.get_object(sitemap_key)
            sitemap = json.loads(sitemap)
        except Exception as e:
            sitemap = self.__site_downloader.load_sitemap(url)
            self.__object_store.save_object(sitemap_key, json.dumps(sitemap))
        
        return sitemap

    def __worker(self, queue: Queue, thread_id: int):
        """Worker method to process pages from the queue.
        
        Args:
            queue: Queue containing jobs to process
            thread_id: ID of the worker thread
            results: Shared list to store results
        """
        while True:
            try:
                # Get job with timeout to prevent hanging
                job = queue.get(timeout=1)
                print(queue.qsize())
            except Empty:
                # No more jobs, exit thread
                print(f"No more jobs, exiting thread {thread_id}")
                break

            try:
                page_url, page_key, ttl_key = job

                try:
                    page_content = self.__object_store.get_object(page_key).decode('utf-8')
                except Exception:
                    page_content = self.__site_downloader.download_url(page_url)
                    page_content = self.__site_downloader.extract_text_from_html(page_content)
                    self.__object_store.save_object(page_key, page_content)

                try:
                    ttl_content = self.__object_store.get_object(ttl_key)
                except Exception:
                    response = self.__chat_completion.invoke([
                        SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=page_content)
                    ])
                    ttl_content = response.content.replace('```turtle', '').replace('```', '')
                    self.__object_store.save_object(ttl_key, ttl_content)

                # logger.info(f"Thread {thread_id}: Processed {page_url}")

            except Exception as e:
                logger.error(f"Thread {thread_id}: Error processing {page_url}: {str(e)}")
            finally:
                queue.task_done()

    def __compute_ttl(self, num_threads: int, job_queue: Queue):
        # Create shared results list and start worker threads
        threads: List[Thread] = []

        for i in range(num_threads):
            thread = Thread(target=self.__worker, args=(job_queue, i))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            

    def run(self, parameters: ExtractWebsiteWorkflowParameters) -> Dict:
        """Extracts content from a website using multiple threads.
        
        Args:
            parameters: Parameters containing URL and extraction options
            
        Returns:
            Dict: Extracted content and metadata
        """
        result = {}
        sitemap = self.__get_sitemap(parameters.url)

        # Create job queue
        job_queue = Queue()


        ttl_files = []
        # Add jobs to queue
        for page_url in sitemap:
            page_key = f"{self.__sanitize_url(parameters.url)}/page_{self.__sanitize_url(page_url)}.html"
            ttl_key = f"{page_key}.ttl"
            ttl_files.append(ttl_key)
            job_queue.put((page_url, page_key, ttl_key))

        self.__compute_ttl(10, job_queue)


        # Merge all TTL files into a single graph
        merged_graph = Graph()
        
        # First parse the ontology to establish the base prefixes
        ontology_graph = Graph()
        ontology_graph.parse(data=ONTOLOGY, format="turtle")
        
        
        for ttl_file in ttl_files:
            ttl_content = self.__object_store.get_object(ttl_file).decode('utf-8')
            if ttl_content:
                try:
                    # Parse TTL content into temporary graph
                    temp_graph = Graph()
                    temp_graph.parse(data=f"{ONTOLOGY}\n{ttl_content}", format="turtle")
                    
                    # Merge into main graph
                    merged_graph += temp_graph
                except Exception as e:
                    logger.error(f"Error parsing TTL file {ttl_file}: {str(e)}")

        # Bind other ontology namespaces to the merged graph
        for prefix, namespace in ontology_graph.namespaces():
            merged_graph.bind(prefix, namespace)
        
        # Convert merged graph to turtle format
        result["merged_ttl"] = merged_graph.serialize(format="turtle", namespace_manager=merged_graph.namespace_manager)
        
        self.__object_store.save_object(f"{self.__sanitize_url(parameters.url)}.ttl", result["merged_ttl"])

        return result

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="extract_website_content",
            description="Extract text content and optionally sitemap from a website",
            func=lambda **kwargs: self.run(ExtractWebsiteWorkflowParameters(**kwargs)),
            args_schema=ExtractWebsiteWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/extract_website")
        def extract_website(parameters: ExtractWebsiteWorkflowParameters):
            return self.run(parameters)

def main():
    # Initialize configurations
    config = ExtractWebsiteWorkflowConfiguration(
        site_downloader_config=SiteDownloaderConfiguration()
    )
    
    # Initialize workflow
    workflow = ExtractWebsiteWorkflow(config)
    
    # Run workflow with example parameters
    result = workflow.run(ExtractWebsiteWorkflowParameters(
        url="https://beneteau-group.com"
    ))
    
    deduped_ttl, graph = OntologyReasoner().dedup_ttl(result["merged_ttl"])
    # Save deduped ttl to file
    with open("deduped.ttl", "w") as f:
        f.write(deduped_ttl)
        
    from abi.utils.OntologyYaml import OntologyYaml
    yaml_graph_dict = OntologyYaml.rdf_to_yaml(graph, ontology_schemas=["/app/src/core/ontologies/ConsolidatedOntology.ttl"])
    
    import yaml
    with open("deduped.yaml", "w") as f:
        yaml.dump(yaml_graph_dict, f, sort_keys=False)
    
    
if __name__ == "__main__":
    main()
