"""Working process ontology — Python entities for demo graph generation."""

from __future__ import annotations

import datetime
import os
from typing import Annotated, Any, ClassVar, List, Optional, Union

from pydantic import Field
from rdflib import URIRef

from naas_abi.ontologies.modules.ABIOntology import Organization, Person
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    JobDescription,
    JobPosition,
)
from naas_abi_marketplace.domains.personnel.ontologies.processes.BirthRegistrationProcess import (
    RDFEntity,
    Site,
)


class Working(RDFEntity):
    """Ongoing act of working for an organization."""

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/Working"
    _name: ClassVar[str] = "Working"
    _property_uris: ClassVar[dict] = {
        "bFO_0000057": "http://purl.obolibrary.org/obo/BFO_0000057",
        "bFO_0000066": "http://purl.obolibrary.org/obo/BFO_0000066",
        "bFO_0000199": "http://purl.obolibrary.org/obo/BFO_0000199",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "for_organization": "http://ontology.naas.ai/personnel/forOrganization",
        "has_contract": "http://ontology.naas.ai/personnel/hasContract",
        "is_working_of": "http://ontology.naas.ai/personnel/isWorkingOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "realizes_job_position": "http://ontology.naas.ai/personnel/realizesJobPosition",
    }
    _object_properties: ClassVar[set[str]] = {
        "bFO_0000057",
        "bFO_0000066",
        "bFO_0000199",
        "for_organization",
        "has_contract",
        "is_working_of",
        "realizes_job_position",
    }

    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")
    bFO_0000057: Optional[
        Annotated[List[Union[Person, "Remuneration", URIRef, str]], Field()]
    ] = None
    bFO_0000066: Optional[Annotated[List[Union[Site, URIRef, str]], Field()]] = None
    bFO_0000199: Optional[Annotated[List[Union[URIRef, str]], Field()]] = None
    for_organization: Optional[Annotated[List[Union[Organization, URIRef, str]], Field()]] = None
    has_contract: Optional[
        Annotated[List[Union["EmploymentContract", URIRef, str]], Field()]
    ] = None
    is_working_of: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = None
    realizes_job_position: Optional[
        Annotated[List[Union[JobPosition, URIRef, str]], Field()]
    ] = None


class EmploymentContract(RDFEntity):
    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/EmploymentContract"
    _name: ClassVar[str] = "Employment Contract"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_about_job_description": "http://ontology.naas.ai/personnel/isAboutJobDescription",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_about_job_description"}

    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")
    is_about_job_description: Optional[
        Annotated[List[Union[JobDescription, URIRef, str]], Field()]
    ] = None


class Remuneration(RDFEntity):
    _class_uri: ClassVar[str] = "http://ontology.naas.ai/personnel/Remuneration"
    _name: ClassVar[str] = "Remuneration"
    _property_uris: ClassVar[dict] = {
        "bFO_0000197": "http://purl.obolibrary.org/obo/BFO_0000197",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "remuneration_amount": "http://ontology.naas.ai/personnel/remuneration_amount",
        "remuneration_currency": "http://ontology.naas.ai/personnel/remuneration_currency",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000197"}

    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    remuneration_amount: Optional[Annotated[float, Field()]] = None
    remuneration_currency: Optional[Annotated[str, Field()]] = None
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")
    bFO_0000197: Optional[Annotated[List[Union[Person, URIRef, str]], Field()]] = None


Working.model_rebuild()
EmploymentContract.model_rebuild()
Remuneration.model_rebuild()
