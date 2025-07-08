import os
import uuid
from datetime import datetime
import pydash
from rdflib import Graph, URIRef, RDF, OWL, RDFS, Literal, XSD, Namespace
from abi.utils.OntologyYaml import OntologyYaml
from abi.utils.Storage import save_triples, save_yaml, get_triples
from abi.utils.String import string_to_uuid
from src import secret, services
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.core.modules.ontology.mappings import COLORS_NODES
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration
from src.custom.modules.linkedin.utils.LinkedIn import get_date
from typing import Tuple

ABI = Namespace("http://ontology.naas.ai/abi/")
LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin#")
BFO = Namespace("http://purl.obolibrary.org/obo/")

# Configuration
## Integration
naas_api_key = secret.get('NAAS_API_KEY')
if naas_api_key:
    naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
    li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret', {}).get('value')
    JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret', {}).get('value')
if not li_at or not JSESSIONID:
    raise Exception("li_at or JSESSIONID is not set")
configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
linkedin_integration = LinkedInIntegration(configuration)

## Parameters
linkedin_url = "https://www.linkedin.com/in/jeremyravenel/"
data_store_path = "datastore/linkedin/get_profile_view"

# Integration
linkedin_data = linkedin_integration.get_profile_view(linkedin_url)
profile_id = linkedin_integration.get_profile_id(linkedin_url)

# Pipeline
output_dir = os.path.join(data_store_path, profile_id)
data = linkedin_data.get("data", {})
included = linkedin_data.get("included", [])

## Add LinkedIn Profile Page
entity_urn = data.get("entityUrn")
linkedin_id = entity_urn.split(":")[-1]
linkedin_url = f"https://www.linkedin.com/in/{linkedin_id}"
linkedin_public_id = None
linkedin_public_url = None
linkedin_logo = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/LinkedIn_icon.svg/1024px-LinkedIn_icon.svg.png"
if linkedin_id.startswith("ACo"):
    linkedin_public_id = profile_id
    linkedin_public_url = linkedin_url
linkedin_page_uri = ABI[str(string_to_uuid(linkedin_id))]
print(f"==> Create LinkedIn Profile Page: {linkedin_id} ({linkedin_page_uri})")
graph_linkedin_page = Graph()
try:
    graph_linkedin_page = services.triple_store_service.get_subject_graph(linkedin_page_uri)
except Exception:
    graph_linkedin_page.add((linkedin_page_uri, RDF.type, OWL.NamedIndividual))
    graph_linkedin_page.add((linkedin_page_uri, RDF.type, LINKEDIN.LinkedInProfilePage))
    graph_linkedin_page.add((linkedin_page_uri, RDFS.label, Literal(profile_id)))

if len(list(graph_linkedin_page.triples((linkedin_page_uri, RDFS.label, Literal(profile_id))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, RDFS.label, Literal(profile_id)))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.entityUrn, Literal(entity_urn))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.entityUrn, Literal(entity_urn)))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.linkedin_id, Literal(linkedin_id))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.linkedin_id, Literal(linkedin_id)))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.linkedin_url, Literal(linkedin_url))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.linkedin_url, Literal(linkedin_url)))

if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.linkedin_public_id, Literal(linkedin_public_id))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.linkedin_public_id, Literal(linkedin_public_id)))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.linkedin_public_url, Literal(linkedin_public_url))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.linkedin_public_url, Literal(linkedin_public_url)))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, ABI.logo, Literal(linkedin_logo))))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, ABI.logo, Literal(linkedin_logo)))

### Add LinkedIn Profile
profile_urn = data.get("*profile")
lk_profile_id = str(string_to_uuid(profile_urn))
profile_uri = LINKEDIN[lk_profile_id]
profile_data = pydash.filter_(included, lambda x: x.get("entityUrn") == profile_urn)[0]
name = (profile_data.get("firstName", "") + " " + profile_data.get("lastName", "")).strip()
print(f"==> Create LinkedIn Profile: {name} ({profile_uri})")
graph_profile_data = Graph()
try:
    graph_profile_data = services.triple_store_service.get_subject_graph(profile_uri)
except Exception:
    graph_profile_data.add((profile_uri, RDF.type, OWL.NamedIndividual))
    graph_profile_data.add((profile_uri, RDF.type, URIRef("http://ontology.naas.ai/abi/linkedin#LinkedInProfile")))
    graph_profile_data.add((profile_uri, RDFS.label, Literal(name)))

#### Add object properties
if len(list(graph_profile_data.triples((profile_uri, LINKEDIN.isProfileOf, linkedin_page_uri)))) == 0:
    graph_profile_data.add((profile_uri, LINKEDIN.isProfileOf, linkedin_page_uri))
if len(list(graph_linkedin_page.triples((linkedin_page_uri, LINKEDIN.hasProfile, profile_uri)))) == 0:
    graph_linkedin_page.add((linkedin_page_uri, LINKEDIN.hasProfile, profile_uri))

def create_class_and_relations_from_key(key: str) -> Tuple[URIRef, URIRef, URIRef]:
    """Create class and relations for an RDF graph.
    
    Args:
        data (dict): Dictionary containing data properties  
    """
    class_label = (key[0].upper() + key[1:]).rstrip('s')
    relation_label = "has" + class_label
    relation_label_inverse = "is" + class_label + "Of"
    return URIRef(LINKEDIN[class_label]), URIRef(LINKEDIN[relation_label]), URIRef(LINKEDIN[relation_label_inverse])

def add_property_value(graph: Graph, uri: URIRef, key: str, value: any) -> Graph:
    """Recursively add any property value to graph"""
    clean_k = key.replace("*", "").replace("$", "")
    if clean_k in ["paging", "logo", "backgroundImage", "picture"]:
        return graph

    # Handle string values
    if isinstance(value, str) and value is not None:
        if clean_k in ["title", "name", "degreeName"] and len(list(graph.triples((uri, RDFS.label, Literal(value))))) == 0:
            graph.add((uri, RDFS.label, Literal(value)))
        elif len(list(graph.triples((uri, LINKEDIN[clean_k], Literal(value))))) == 0 and not value.startswith("urn:"):
            graph.add((uri, LINKEDIN[clean_k], Literal(value)))
        # elif clean_k.endswith("Urn") and value.startswith("urn:") and not value.startswith("urn:li:fsd_profile"):
        #     print(f"🔍 - Value is a urn: {value}")
        #     element_data = pydash.filter_(included, lambda x: x.get("entityUrn") == value)
        #     if len(element_data) > 0:
        #         graph = add_properties(graph, uri, element_data[0])
        return graph

    # Handle list values
    if isinstance(value, list):
        if all(isinstance(x, str) for x in value):
            for item in value:
                class_label = (clean_k[0].upper() + clean_k[1:]).rstrip('s')
                class_uri, relation_label_uri, relation_label_inverse_uri = create_class_and_relations_from_key(class_label)
                item_uri = LINKEDIN[str(string_to_uuid(item))]
                graph_item = Graph()
                try:
                    graph_item = services.triple_store_service.get_subject_graph(item_uri)
                    if len(list(graph_item.triples((item_uri, relation_label_uri, uri)))) == 0:
                        graph_item.add((item_uri, relation_label_uri, uri))
                    if len(list(graph_item.triples((uri, relation_label_inverse_uri, item_uri)))) == 0:
                        graph_item.add((uri, relation_label_inverse_uri, item_uri))
                except Exception:
                    graph_item.add((item_uri, RDF.type, OWL.NamedIndividual))
                    graph_item.add((item_uri, RDF.type, class_uri))
                    graph_item.add((item_uri, RDFS.label, Literal(item)))
                    graph_item.add((item_uri, relation_label_uri, uri))
                    graph_item.add((uri, relation_label_uri, item_uri))

                graph += graph_item
        else:
            for item in value:
                graph = add_property_value(graph, uri, clean_k, item)
        return graph

    # Handle dict values
    if isinstance(value, dict):
        if key == "timePeriod":
            start_date = get_date(value.get("startDate", {}), "start")
            end_date = get_date(value.get("endDate", {}), "end")
            if start_date is not None:
                date_epoch = int(datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
                date_uri = ABI[str(date_epoch)]
                graph_date = Graph()
                try:
                    graph_date = services.triple_store_service.get_subject_graph(date_uri)
                    print(f"🔍 - Date already exists: {start_date} ({date_uri})")
                except Exception:
                    graph_date.add((date_uri, RDF.type, OWL.NamedIndividual))
                    graph_date.add((date_uri, RDF.type, URIRef(ABI.ISO8601UTCDateTime)))
                    graph_date.add((date_uri, RDFS.label, Literal(start_date, datatype=XSD.dateTime)))
                
                if len(list(graph.triples((uri, BFO.BFO_0000222, date_uri)))) == 0:
                    graph.add((uri, BFO.BFO_0000222, date_uri))
                graph += graph_date

            if end_date is not None:
                date_epoch = int(datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
                date_uri = ABI[str(date_epoch)]
                graph_date = Graph()
                try:
                    graph_date = services.triple_store_service.get_subject_graph(date_uri)
                    print(f"🔍 - Date already exists: {end_date} ({date_uri})")
                except Exception:
                    graph_date.add((date_uri, RDF.type, OWL.NamedIndividual))
                    graph_date.add((date_uri, RDF.type, URIRef(ABI.ISO8601UTCDateTime)))
                    graph_date.add((date_uri, RDFS.label, Literal(end_date, datatype=XSD.dateTime)))
                if len(list(graph_date.triples((date_uri, BFO.BFO_0000222, uri)))) == 0:
                    graph_date.add((date_uri, BFO.BFO_0000224, uri))
                graph += graph_date
            return graph

        if '$type' in value:
            class_label = (clean_k[0].upper() + clean_k[1:]).rstrip('s')
            class_uri, relation_label_uri, relation_label_inverse_uri = create_class_and_relations_from_key(class_label)
            dict_uri = LINKEDIN[str(uuid.uuid4())]
            graph_dict = Graph()
            try:
                graph_dict = services.triple_store_service.get_subject_graph(dict_uri)
            except Exception:
                graph_dict.add((dict_uri, RDF.type, OWL.NamedIndividual))
                graph_dict.add((dict_uri, RDF.type, class_uri))
                graph_dict.add((dict_uri, RDFS.label, Literal(clean_k)))

            if len(list(graph_dict.triples((uri, relation_label_uri, dict_uri)))) == 0:
                graph_dict.add((uri, relation_label_uri, dict_uri))
            if len(list(graph_dict.triples((dict_uri, relation_label_inverse_uri, uri)))) == 0:
                graph_dict.add((dict_uri, relation_label_inverse_uri, uri))

            for k_dict, v_dict in value.items():
                if k_dict != "$type":
                    graph_dict = add_property_value(graph, dict_uri, k_dict, v_dict)
            graph += graph_dict

        if key == "company":
            print(f"🔍 - Company: {value}")
        else:
            for k_dict, v_dict in value.items():
                graph = add_property_value(graph, uri, k_dict, v_dict)
        return graph

    return graph

def add_properties(graph: Graph, uri: URIRef, data: dict) -> Graph:
    """Add data properties to an RDF graph recursively.
    
    Args:
        graph (Graph): The RDF graph to add properties to
        uri (URIRef): The URI of the subject
        data (dict): Dictionary containing data properties
    """


    for k, v in data.items():
        graph = add_property_value(graph, uri, k, v)
    return graph

graph_profile_data = add_properties(graph_profile_data, profile_uri, profile_data)

### Add Views
object_views: list = []
for k, v in data.items():
    if k.startswith("*") and k.endswith("View"):
        clean_k = k.replace("*", "")
        class_label = clean_k[0].upper() + clean_k[1:].replace("View", "").replace(" ", "")
        class_uri, relation_label_uri, relation_label_inverse_uri = create_class_and_relations_from_key(class_label)
        view_data = pydash.filter_(included, lambda x: x.get("entityUrn") == v)[0]
        view_data_elements = view_data.get("*elements", [])
        for view_data_element in view_data_elements:
            print(f"🔍 - View data element: {view_data_element}")
            view_id = str(string_to_uuid(view_data_element))
            view_uri = ABI[view_id]
            graph_view_data = Graph()
            try:
                graph_view_data = services.triple_store_service.get_subject_graph(view_uri)
            except Exception:
                graph_view_data.add((view_uri, RDF.type, OWL.NamedIndividual))
                graph_view_data.add((view_uri, RDF.type, class_uri))
            element_data = pydash.filter_(included, lambda x: x.get("entityUrn") == view_data_element)[0]
            graph_view_data = add_properties(graph_view_data, view_uri, element_data)
            graph_view_data.add((view_uri, relation_label_inverse_uri, profile_uri))
            graph_profile_data.add((profile_uri, relation_label_uri, view_uri))
            graph_profile_data += graph_view_data

# Save triples
graph_insert = Graph()
graph_insert.bind("abi", ABI)
graph_insert.bind("owl", OWL)
graph_insert.bind("rdfs", RDFS)
graph_insert.bind("xsd", XSD)
graph_insert.bind("rdf", RDF)
graph_insert.bind("linkedin", LINKEDIN)
graph_insert.bind("bfo", BFO)
graph_insert += graph_linkedin_page
graph_insert += graph_profile_data

save_triples(
    graph_insert, 
    output_dir, 
    f"{profile_id}.ttl", 
    copy=False
)

# Convert to YAML
yaml_data = OntologyYaml.rdf_to_yaml(
    graph_insert, 
    display_relations_names=True,
    class_colors_mapping=COLORS_NODES,
    yaml_properties=["definition", "example", "description", "download url", "asset url", "summary", "address", "city", "state", "postal code", "geographic area"]
)
save_yaml(
    yaml_data, 
    output_dir, 
    f"{profile_id}.yaml",
    copy=False
)