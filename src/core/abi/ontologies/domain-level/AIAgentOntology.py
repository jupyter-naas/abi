from __future__ import annotations
from typing import Optional, Any, ClassVar
from pydantic import BaseModel, Field
import uuid
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF

# Generated classes from TTL file

# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""
    _namespace: ClassVar[str] = "http://example.org/instance/"
    _uri: str = ""
    
    model_config = {
        'arbitrary_types_allowed': True,
        'extra': 'forbid'
    }
    
    def __init__(self, **kwargs):
        uri = kwargs.pop('_uri', None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"
    
    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace
        
    def rdf(self, subject_uri: str | None = None) -> Graph:
        """Generate RDF triples for this instance"""
        g = Graph()
        
        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)
        
        # Add class type
        if hasattr(self, '_class_uri'):
            g.add((subject, RDF.type, URIRef(self._class_uri)))
        
        # Add properties
        if hasattr(self, '_property_uris'):
            for prop_name, prop_uri in self._property_uris.items():
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, 'rdf'):
                                # Add triples from related object
                                g += item.rdf()
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, 'rdf'):
                        # Add triples from related object
                        g += prop_value.rdf()
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))
        
        return g


class AISystem(RDFEntity):
    """
    AI System
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/AISystem'
    _property_uris: ClassVar[dict] = {'hasAIAgent': 'http://ontology.naas.ai/abi/hasAIAgent', 'hasLoadBalancer': 'http://ontology.naas.ai/abi/hasLoadBalancer', 'hasSubsystem': 'http://ontology.naas.ai/abi/hasSubsystem', 'isSubsystemOf': 'http://ontology.naas.ai/abi/isSubsystemOf'}

    # Object properties
    hasAIAgent: Optional[AIAgent] = Field(default=None)
    hasLoadBalancer: Optional[LoadBalancer] = Field(default=None)
    hasSubsystem: Optional[AISystem] = Field(default=None)
    isSubsystemOf: Optional[AISystem] = Field(default=None)

class AIAgent(RDFEntity):
    """
    AI Agent
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/AIAgent'
    _property_uris: ClassVar[dict] = {'canUtilizeModel': 'http://ontology.naas.ai/abi/canUtilizeModel', 'collaboratesWith': 'http://ontology.naas.ai/abi/collaboratesWith', 'hasCapability': 'http://ontology.naas.ai/abi/hasCapability', 'hasFallbackAgent': 'http://ontology.naas.ai/abi/hasFallbackAgent', 'hasSpecializedRole': 'http://ontology.naas.ai/abi/hasSpecializedRole', 'isAIAgentOf': 'http://ontology.naas.ai/abi/isAIAgentOf'}

    # Object properties
    canUtilizeModel: Optional[AIModelInstance] = Field(default=None)
    collaboratesWith: Optional[AIAgent] = Field(default=None)
    hasCapability: Optional[Any] = Field(default=None)
    hasFallbackAgent: Optional[AIAgent] = Field(default=None)
    hasSpecializedRole: Optional[AgentRole] = Field(default=None)
    isAIAgentOf: Optional[AISystem] = Field(default=None)

class AgentRole(RDFEntity):
    """
    Agent Role
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/AgentRole'
    _property_uris: ClassVar[dict] = {}
    pass

class LoadBalancer(RDFEntity):
    """
    Load Balancer
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/LoadBalancer'
    _property_uris: ClassVar[dict] = {}
    pass

class ModelAccuracy(RDFEntity):
    """
    Model Accuracy
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ModelAccuracy'
    _property_uris: ClassVar[dict] = {}
    pass

class ResponseLatency(RDFEntity):
    """
    Response Latency
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ResponseLatency'
    _property_uris: ClassVar[dict] = {}
    pass

class TokenCapacity(RDFEntity):
    """
    Token Capacity
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TokenCapacity'
    _property_uris: ClassVar[dict] = {}
    pass

class TextGenerationProcess(RDFEntity):
    """
    Text Generation Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TextGenerationProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class ImageAnalysisProcess(RDFEntity):
    """
    Image Analysis Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ImageAnalysisProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class CodeGenerationProcess(RDFEntity):
    """
    Code Generation Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/CodeGenerationProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class ModelTrainingPeriod(RDFEntity):
    """
    Model Training Period
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ModelTrainingPeriod'
    _property_uris: ClassVar[dict] = {}
    pass

class InferenceSession(RDFEntity):
    """
    Inference Session
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/InferenceSession'
    _property_uris: ClassVar[dict] = {}
    pass

class DataCenterLocation(RDFEntity):
    """
    Data Center Location
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/DataCenterLocation'
    _property_uris: ClassVar[dict] = {}
    pass

class CloudRegion(RDFEntity):
    """
    Cloud Region
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/CloudRegion'
    _property_uris: ClassVar[dict] = {}
    pass

class ModelSpecification(RDFEntity):
    """
    Model Specification
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ModelSpecification'
    _property_uris: ClassVar[dict] = {}
    pass

class TrainingDataset(RDFEntity):
    """
    Training Dataset
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TrainingDataset'
    _property_uris: ClassVar[dict] = {}
    pass

class APIResponse(RDFEntity):
    """
    API Response
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/APIResponse'
    _property_uris: ClassVar[dict] = {}
    pass

class CreativeWritingProcess(RDFEntity):
    """
    Creative Writing Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/CreativeWritingProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class TruthSeekingAnalysisProcess(RDFEntity):
    """
    Truth Seeking Analysis Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TruthSeekingAnalysisProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class BusinessProposalCreationProcess(RDFEntity):
    """
    Business Proposal Creation Process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/BusinessProposalCreationProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class AIModelInstance(AISystem, RDFEntity):
    """
    Every AI model instance is a type of AI system.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/AIModelInstance'
    _property_uris: ClassVar[dict] = {'hasAIAgent': 'http://ontology.naas.ai/abi/hasAIAgent', 'hasLoadBalancer': 'http://ontology.naas.ai/abi/hasLoadBalancer', 'hasSubsystem': 'http://ontology.naas.ai/abi/hasSubsystem', 'isSubsystemOf': 'http://ontology.naas.ai/abi/isSubsystemOf'}

    # Object properties
    hasAIAgent: Optional[AIAgent] = Field(default=None)
    hasLoadBalancer: Optional[LoadBalancer] = Field(default=None)
    hasSubsystem: Optional[AISystem] = Field(default=None)
    isSubsystemOf: Optional[AISystem] = Field(default=None)

# Rebuild models to resolve forward references
AISystem.model_rebuild()
AIAgent.model_rebuild()
AgentRole.model_rebuild()
LoadBalancer.model_rebuild()
ModelAccuracy.model_rebuild()
ResponseLatency.model_rebuild()
TokenCapacity.model_rebuild()
TextGenerationProcess.model_rebuild()
ImageAnalysisProcess.model_rebuild()
CodeGenerationProcess.model_rebuild()
ModelTrainingPeriod.model_rebuild()
InferenceSession.model_rebuild()
DataCenterLocation.model_rebuild()
CloudRegion.model_rebuild()
ModelSpecification.model_rebuild()
TrainingDataset.model_rebuild()
APIResponse.model_rebuild()
CreativeWritingProcess.model_rebuild()
TruthSeekingAnalysisProcess.model_rebuild()
BusinessProposalCreationProcess.model_rebuild()
AIModelInstance.model_rebuild()
