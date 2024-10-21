from abi.utils import remove_accents, remove_emojis, get_last_day_of_month
from rdflib import Namespace, URIRef, Literal, Graph
from rdflib.namespace import RDF, RDFS, OWL, DC, XSD, SKOS
from urllib.parse import quote

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
TIME = Namespace("http://www.w3.org/2006/time#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

class RDFGraph:
    
    @staticmethod
    def to_camel_case_with_spaces(input_str):
        """
        Convert a string with spaces to camelCase.

        :param input_str: The input string with spaces.
        :return: The string converted to camelCase.
        """
        components = input_str.split(' ')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    @staticmethod
    def get_file_format(file_path):
        file_format = "turtle"
        if file_path.endswith("owl"):
            file_format = "xml"
        elif file_path.endswith("ttl"):
            file_format = "turtle"
        return file_format
    
    @staticmethod
    def parse(file_path=None, g=None):
        if g is None:
            g = Graph()
        if file_path and isinstance(file_path, str):
            file_path = [file_path]
        if file_path:
            for f in file_path:
                g += g.parse(f, format=RDFGraph.get_file_format(f)) 
        return g
    
    def __init__(self, file_path=None, g=None):
        self.g = RDFGraph.parse(file_path, g)
        self.g.bind("bfo", BFO)
        self.g.bind("skos", SKOS)
        self.g.bind("abi", ABI)
        self.prefix = ABI
        
    def concat(self, file_path=None, g=None):
        self.g += RDFGraph.parse(file_path, g)
        return self.g
        
    def get(self):
        return self.g
            
    def save(self, file_path):
        return self.g.serialize(destination=file_path, format=RDFGraph.get_file_format(file_path))
    
    def add(self, s, p, o):
        self.g.add((s, p, o))
        return self.g
    
    # Add OWL Class to Graph
    def add_class(
        self,
        uid,
        label,
        parent,
        definition=None,
        example=None,
        lang="en",
    ):
        # Init
        uri = URIRef(ABI[uid])

        # Add class to ontology
        if (uri, RDF.type, OWL.Class) not in self.g:
            self.g.add((uri, RDF.type, OWL.Class))
            self.g.add((uri, RDFS.label, Literal(label, lang=lang)))
            self.g.add((uri, RDFS.subClassOf, URIRef(str(parent))))
            if definition:
                self.g.add((uri, SKOS.definition, Literal(definition, lang=lang)))
            if example:
                self.g.add((uri, SKOS.example, Literal(example, lang=lang)))
            print(f"✅ Class '{label}' successfully added to ontology ({str(uri)})")
        else:
            print(f"Class '{label}' already exists in ontology ({str(uri)})")
        return uri
    
    # Add OWL ObjectProperty to Graph
    def add_property(
        self,
        uid,
        label,
        parent,
        definition=None,
        example=None,
        domain=None,
        range_=None,
        lang="en",
    ):
        # Init
        uri = URIRef(ABI[uid])

        # Add Object Property to ontology
        if (uri, RDF.type, OWL.ObjectProperty) not in self.g:
            self.g.add((uri, RDF.type, OWL.ObjectProperty))
            self.g.add((uri, RDFS.label, Literal(label, lang=lang)))
            self.g.add((uri, RDFS.subPropertyOf, URIRef(parent)))
            self.g.add((uri, RDFS.domain, URIRef(domain)))
            self.g.add((uri, RDFS.range, URIRef(range_)))
            if definition:
                self.g.add((uri, SKOS.definition, Literal(definition, lang=lang)))
            if example:
                self.g.add((uri, SKOS.example, Literal(example, lang=lang)))
            print(f"✅ Object Property '{label}' successfully added to ontology ({str(uri)})")
        else:
            print(f"Object Property '{label}' already exists in ontology ({str(uri)})")
        return uri
    
    
    # Add OWL NamedIndividual to Graph
    def add_individual(
        self,
        uid,
        label,
        parent,
        lang="en",
        **metadata
    ):
        # Init
        uri = URIRef(quote(f"{str(parent)}#{uid}", safe=":/#"))

        # Add NamedIndividual to ontology
        if (uri, RDF.type, parent) not in self.g:
            self.g.add((uri, RDF.type, OWL.NamedIndividual))
            self.g.add((uri, RDF.type, URIRef(parent)))
            # Label
            if type(label) == str:
                self.g.add((uri, RDFS.label, Literal(label, lang=lang)))
            elif type(label) in [int, float]:
                self.g.add((uri, RDFS.label, Literal(label, datatype=XSD.integer)))
            else:
                self.g.add((uri, RDFS.label, Literal(label, datatype=XSD.dateTime)))
            for x in metadata:
                value = metadata.get(x)
                if type(value) == str:
                    self.g.add((uri, ABI[x], Literal(value, lang=lang)))
                elif type(value) in [int, float]:
                    self.g.add((uri, ABI[x], Literal(value, datatype=XSD.integer)))
                else:
                    self.g.add((uri, ABI[x], Literal(value, datatype=XSD.dateTime)))
            print(f"✅ '{label}' successfully added to ontology ({str(uri)})")
        return uri
    
    # Add OWL NamedIndividual Time Instant to Graph
    def add_time_instant(
        self,
        date_obj,
        parent=ABI.DateTimeOffset
    ):
        # Init
        datetime_format = "%Y-%m-%dT%H:%M:%S%z"
        uid = str(int(date_obj.timestamp()))
        uri = URIRef(f"{str(XSD)}{uid}")

        # Add NamedIndividual#Date to ontology
        if (uri, RDF.type, parent) not in self.g:
            self.g.add((uri, RDF.type, OWL.NamedIndividual))
            self.g.add((uri, RDF.type, URIRef(parent)))
            self.g.add((uri, RDFS.label, Literal(date_obj.strftime(datetime_format), datatype=XSD.dateTime)))
        return uri
    
    # Add OWL NamedIndividual Process to Graph
    def add_process(
        self,
        uid,
        label,
        parent,
        lang="en",
        participants=[],
        participants_oprop=BFO.BFO_0000056,
        realizes=[],
        realizes_oprop=BFO.BFO_0000054,
        occurs_in=[],
        occurs_in_oprop=BFO.BFO_0000066,
        concretizes=[],
        concretizes_oprop=BFO.BFO_0000058,
        temporal_region=None,
        temporal_region_oprop=BFO.BFO_0000199
    ):
        # Init
        uri = self.add_individual(uid, label, parent)

        # Add NamedIndividual#Date to ontology
        if (uri, RDF.type, parent) not in self.g:
            self.g.add((uri, RDF.type, OWL.NamedIndividual))
            self.g.add((uri, RDF.type, URIRef(parent)))
            self.g.add((uri, RDFS.label, Literal(date_obj.strftime(datetime_format), datatype=XSD.dateTime)))
            
        # Add participants
        for participant in participants:
            self.g.add((participant, participants_oprop, uri))
            
        # Add realizable entities
        for realize in realizes:
            self.g.add((realize, realizes_oprop, uri))
            
        # Add occurs_in
        for oi in occurs_in:
            self.g.add((uri, occurs_in_oprop, oi))
        
        # Add concretizes
        for concretize in concretizes:
            self.g.add((uri, concretizes_oprop, concretize))
            
        # Add occupies_temporal_region
        if temporal_region:
            self.g.add((uri, temporal_region_oprop, temporal_region))
        return uri