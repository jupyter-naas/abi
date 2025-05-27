from src import secret
from src.core.modules.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.custom.modules.linkedin.integrations.LinkedInIntegration import LinkedInIntegration, LinkedInIntegrationConfiguration
import pydash
from abi.utils.Storage import save_json, save_triples, save_yaml
import os
from rdflib import Graph, URIRef, RDF, OWL, RDFS, Literal, XSD, Namespace
from src.core.modules.ontology.workflows.SearchIndividualWorkflow import (
    SearchIndividualWorkflowConfiguration,
)
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipelineConfiguration,
    AddIndividualPipeline,
)
from src import services
import hashlib
import uuid
from src.core.modules.ontology.mappings import COLORS_NODES
from abi.utils.OntologyYaml import OntologyYaml
from datetime import datetime
import calendar

ABI = Namespace("http://ontology.naas.ai/abi/")
LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin#")
BFO = Namespace("http://purl.obolibrary.org/obo/")

def string_to_uuid(input_string):
    # Create a SHA-256 hash object
    hash_object = hashlib.sha256(input_string.encode())
    
    # Get the hexadecimal representation of the hash
    hex_hash = hash_object.hexdigest()
    
    # Use the first 32 characters of the hex hash to create a UUID
    uuid_obj = uuid.UUID(hex_hash[:32])
    
    return uuid_obj

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

## Pipeline
search_individual_workflow_configuration = SearchIndividualWorkflowConfiguration(
    services.triple_store_service,
)
add_individual_pipeline_configuration = AddIndividualPipelineConfiguration(
    services.triple_store_service,
    search_individual_workflow_configuration
)
add_individual_pipeline = AddIndividualPipeline(add_individual_pipeline_configuration)

# Parameters
linkedin_url = "https://www.linkedin.com/in/jeremyravenel/"
data_store_path = "datastore/linkedin/get_profile_view"

# Integration
linkedin_data = linkedin_integration.get_profile_view(linkedin_url)
profile_id = linkedin_integration.get_profile_id(linkedin_url)
output_dir = os.path.join(data_store_path, profile_id)
data = linkedin_data.get("data", {})
included = linkedin_data.get("included", [])

## Add LinkedIn Profile Page
### Data properties
entity_urn = data.get("entityUrn")
linkedin_id = entity_urn.split(":")[-1]
linkedin_url = f"https://www.linkedin.com/in/{linkedin_id}"
linkedin_public_id = ""
linkedin_public_url = ""
if linkedin_id.startswith("ACo"):
    linkedin_public_id = profile_id
    linkedin_public_url = linkedin_url
page_uri = ABI[str(string_to_uuid(linkedin_id))]
print(f"Page URI: {page_uri}")

### Add profile data
profile_urn = data.get("*profile")
lk_profile_id = str(string_to_uuid(profile_urn))
profile_uri = ABI[lk_profile_id]
profile_data = pydash.filter_(included, lambda x: x.get("entityUrn") == profile_urn)[0]
save_json(dict(sorted(profile_data.items())), output_dir, f"{profile_id}_Profile_{lk_profile_id}.json", copy=False)
name = profile_data.get("firstName", "") + " " + profile_data.get("lastName", "")
print(f"Profile URI: {profile_uri}")
graph_profile_data = Graph()
try:
    graph_profile_data = services.triple_store_service.get_subject_graph(profile_uri)
except Exception:
    graph_profile_data.add((profile_uri, RDF.type, OWL.NamedIndividual))
    graph_profile_data.add((profile_uri, RDF.type, URIRef("http://ontology.naas.ai/abi/linkedin#LinkedInProfile")))
    graph_profile_data.add((profile_uri, RDFS.label, Literal(name)))

#### Add properties
is_profile_of_exists = False
for s, p, o in graph_profile_data:
    if str(s) == str(ABI.isProfileOf) and str(p) == str(page_uri):
        is_profile_of_exists = True
        break
if not is_profile_of_exists:
    graph_profile_data.add((profile_uri, ABI.isProfileOf, page_uri))

def get_last_day_of_month(year, month):
    # Check if the month is valid
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12")

    # Use calendar.monthrange to get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    return last_day

def get_date(data, date_type):
    date_iso = None
    date_format_iso = "%Y-%m-%dT%H:%M:%S.%fZ"
    m = "01"
    d = "01"
    H = "00"
    M = "00"
    S = "00"
    if date_type == "end":
        m = "12"
        d = "31"
        H = "23"
        M = "59"
        S = "59"
    if data:
        year = data.get("year")
        month = data.get("month")
        day = data.get("day")
        if year and not month and not day:
            date_iso = datetime.strptime(
                f"{year}-{m}-{d}T{H}:{M}:{S}.000Z", date_format_iso
            )
        elif year and month and not day:
            date_iso = datetime.strptime(
                f"{year}-{month}-{get_last_day_of_month(year, month)}T{H}:{M}:{S}.000Z",
                date_format_iso,
            )
        elif year and month and day:
            date_iso = datetime.strptime(
                f"{year}-{month}-{day}T{H}:{M}:{S}.000Z", date_format_iso
            )
    return date_iso.strftime(date_format_iso)

def add_properties(graph: Graph, uri: URIRef, data: dict) -> Graph:
    """Add data properties to an RDF graph.
    
    Args:
        graph (Graph): The RDF graph to add properties to
        uri (URIRef): The URI of the subject
        data (dict): Dictionary containing data properties
    """
    for k, v in data.items():
        # Clean key
        clean_k = k.replace("*", "").replace("$", "")

        # Add RDFS label
        if clean_k in ["title", "name", "degreeName"] and len(list(graph.triples((uri, RDFS.label, Literal(v))))) == 0:
            graph.add((uri, RDFS.label, Literal(v)))
            continue

        # Add value = str as data properties
        check_triples = graph.triples((uri, LINKEDIN[clean_k], Literal(v)))
        if isinstance(v, str) and v is not None and len(list(check_triples)) == 0:
            graph.add((uri, LINKEDIN[clean_k], Literal(v)))
            continue

        # Add List[str] as object properties: List
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            for item in v:
                class_label = (clean_k[0].upper() + clean_k[1:]).rstrip('s')
                relation_label = "has" + class_label
                relation_label_inverse = "is" + class_label + "Of"
                item_uri = ABI[str(string_to_uuid(item))]
                graph_item = Graph()
                try:
                    graph_item = services.triple_store_service.get_subject_graph(item_uri)
                except Exception:
                    graph_item.add((item_uri, RDF.type, OWL.NamedIndividual))
                    graph_item.add((item_uri, RDF.type, LINKEDIN[class_label]))

                check_relation = graph.triples((uri, LINKEDIN[relation_label], item_uri))
                if len(list(check_relation)) == 0:
                    graph.add((uri, LINKEDIN[relation_label], item_uri))
                check_relation_inverse = graph.triples((item_uri, LINKEDIN[relation_label_inverse], uri))
                if len(list(check_relation_inverse)) == 0:
                    graph.add((item_uri, LINKEDIN[relation_label_inverse], uri))
                graph += graph_item
            continue

        # Add Dict[str, str] as object properties: Dict
        if isinstance(v, dict) and all(isinstance(x, (str, int)) for x in v.values()) and '$type' in v.keys():
            class_label = (clean_k[0].upper() + clean_k[1:]).rstrip('s')
            relation_label = "has" + class_label
            relation_label_inverse = "is" + class_label + "Of"
            dict_uri = ABI[str(uuid.uuid4())]
            graph_dict = Graph()
            try:
                graph_dict = services.triple_store_service.get_subject_graph(dict_uri)
            except Exception:
                graph_dict.add((dict_uri, RDF.type, OWL.NamedIndividual))
                graph_dict.add((dict_uri, RDF.type, LINKEDIN[class_label]))
                graph_dict.add((dict_uri, RDFS.label, Literal(clean_k)))
                # Add class
                graph_dict.add((LINKEDIN[class_label], RDF.type, OWL.Class))
                graph_dict.add((LINKEDIN[class_label], RDFS.label, Literal(class_label)))
                graph_dict.add((LINKEDIN[relation_label], RDF.type, OWL.DatatypeProperty))
                graph_dict.add((LINKEDIN[relation_label], RDFS.label, Literal(relation_label)))
                graph_dict.add((LINKEDIN[relation_label_inverse], RDF.type, OWL.ObjectProperty))
                graph_dict.add((LINKEDIN[relation_label_inverse], RDFS.label, Literal(relation_label_inverse)))

            check_relation = graph.triples((uri, LINKEDIN[relation_label], dict_uri))
            if len(list(check_relation)) == 0:
                graph.add((uri, LINKEDIN[relation_label], dict_uri))
            check_relation_inverse = graph.triples((dict_uri, LINKEDIN[relation_label_inverse], uri))
            if len(list(check_relation_inverse)) == 0:
                graph.add((dict_uri, LINKEDIN[relation_label_inverse], uri))

            for k_dict, v_dict in v.items():
                if k_dict != "$type":
                    check_triples = graph.triples((dict_uri, LINKEDIN[k_dict], Literal(v_dict)))
                    if len(list(check_triples)) == 0:
                        graph.add((dict_uri, LINKEDIN[k_dict], Literal(v_dict)))
            graph += graph_dict
            continue

        # Add TimePeriod as object properties: TimePeriod
        if k == "timePeriod" and isinstance(v, dict):
            start_date = v.get("startDate", {})
            end_date = v.get("endDate", {})
            if start_date:
                date_label = get_date(start_date, "start")
                date_epoch = int(datetime.strptime(date_label, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
                date_uri = ABI[str(date_epoch)]
                graph_date = Graph()
                try:
                    graph_date = services.triple_store_service.get_subject_graph(date_uri)
                    print(f"🔍 - Date already exists: {date_label} ({date_uri})")
                except Exception:
                    graph_date.add((date_uri, RDF.type, OWL.NamedIndividual))
                    graph_date.add((date_uri, RDF.type, URIRef(ABI.ISO8601UTCDateTime)))
                    graph_date.add((date_uri, RDFS.label, Literal(date_label, datatype=XSD.dateTime)))
                
                check_relation = graph.triples((uri, BFO.BFO_0000222, date_uri))
                if len(list(check_relation)) == 0:
                    graph.add((uri, BFO.BFO_0000222, date_uri))
                graph += graph_date
            if end_date:
                date_label = get_date(end_date, "end")
                date_epoch = int(datetime.strptime(date_label, "%Y-%m-%dT%H:%M:%S.%fZ").timestamp() * 1000)
                date_uri = ABI[str(date_epoch)]
                graph_date = Graph()
                try:
                    graph_date = services.triple_store_service.get_subject_graph(date_uri)
                    print(f"🔍 - Date already exists: {date_label} ({date_uri})")
                except Exception:
                    graph_date.add((date_uri, RDF.type, OWL.NamedIndividual))
                    graph_date.add((date_uri, RDF.type, URIRef(ABI.ISO8601UTCDateTime)))
                    graph_date.add((date_uri, RDFS.label, Literal(date_label, datatype=XSD.dateTime)))
                check_relation_inverse = graph.triples((date_uri, BFO.BFO_0000222, uri))
                if len(list(check_relation_inverse)) == 0:
                    graph_date.add((date_uri, BFO.BFO_0000224, uri))
                graph += graph_date
            continue
    return graph

graph_profile_data = add_properties(graph_profile_data, profile_uri, profile_data)

### Add Views
object_views: list = []
for k, v in data.items():
    if k.startswith("*") and k.endswith("View"):
        clean_k = k.replace("*", "")
        class_label = clean_k[0].upper() + clean_k[1:].replace("View", "").replace(" ", "")
        relation_label = "has" + class_label
        relation_label_inverse = "is" + class_label + "Of"
        view_data = pydash.filter_(included, lambda x: x.get("entityUrn") == v)[0]
        view_data_elements = view_data.get("*elements", [])
        for view_data_element in view_data_elements:
            view_id = str(string_to_uuid(view_data_element))
            view_uri = ABI[view_id]
            graph_view_data = Graph()
            try:
                graph_view_data = services.triple_store_service.get_subject_graph(view_uri)
            except Exception:
                graph_view_data.add((view_uri, RDF.type, OWL.NamedIndividual))
                graph_view_data.add((view_uri, RDF.type, LINKEDIN[class_label]))

            element_data = pydash.filter_(included, lambda x: x.get("entityUrn") == view_data_element)[0]
            save_json(dict(sorted(element_data.items())), output_dir, f"{profile_id}_{class_label}_{view_id}.json", copy=False)
            graph_view_data = add_properties(graph_view_data, view_uri, element_data)

            graph_view_data.add((view_uri, LINKEDIN[relation_label_inverse], profile_uri))
            graph_profile_data.add((profile_uri, LINKEDIN[relation_label], view_uri))
            graph_profile_data += graph_view_data

### Add Triples to LinkedIn Profile Page
graph_linkedin_page = Graph()
try:
    graph_linkedin_page = services.triple_store_service.get_subject_graph(page_uri)
except Exception:
    graph_linkedin_page.add((page_uri, RDF.type, OWL.NamedIndividual))
    graph_linkedin_page.add((page_uri, RDF.type, LINKEDIN.LinkedInProfilePage))

entity_urn_exists = False
linkedin_page_label_exists = False
linkedin_id_exists = False
linkedin_url_exists = False
linkedin_public_id_exists = False
linkedin_public_url_exists = False
linkedin_profile_exists = False

for s, p, o in graph_linkedin_page:
    if str(s) == str(RDFS.label) and str(p) == str(profile_id):
        linkedin_page_label_exists = True
    if str(s) == str(LINKEDIN.entityUrn) and str(p) == str(entity_urn):
        entity_urn_exists = True
    if str(s) == str(LINKEDIN.linkedin_id) and str(p) == str(linkedin_id):
        linkedin_id_exists = True
    if str(s) == str(LINKEDIN.linkedin_url) and str(p) == str(linkedin_url):
        linkedin_url_exists = True
    if str(s) == str(LINKEDIN.linkedin_public_id) and str(p) == str(linkedin_public_id):
        linkedin_public_id_exists = True
    if str(s) == str(LINKEDIN.linkedin_public_url) and str(p) == str(linkedin_public_url):
        linkedin_public_url_exists = True
    if str(s) == str(LINKEDIN.hasProfile) and str(p) == str(profile_uri):
        linkedin_profile_exists = True

if not linkedin_page_label_exists:
    graph_linkedin_page.add((page_uri, RDFS.label, Literal(profile_id)))
if not entity_urn_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.entityUrn, Literal(entity_urn)))
if not linkedin_id_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.linkedin_id, Literal(linkedin_id)))
if not linkedin_url_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.linkedin_url, Literal(linkedin_url)))
if not linkedin_public_id_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.linkedin_public_id, Literal(linkedin_public_id)))
if not linkedin_public_url_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.linkedin_public_url, Literal(linkedin_public_url)))
if not linkedin_profile_exists:
    graph_linkedin_page.add((page_uri, LINKEDIN.hasProfile, profile_uri))

# Save triples
graph_insert = Graph()
graph_insert.bind("abi", ABI)
graph_insert.bind("owl", OWL)
graph_insert.bind("rdfs", RDFS)
graph_insert.bind("xsd", XSD)
graph_insert.bind("rdf", RDF)
graph_insert.bind("linkedin", LINKEDIN)
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