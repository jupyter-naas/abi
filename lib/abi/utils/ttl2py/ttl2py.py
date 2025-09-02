import rdflib
import io
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field
import re

@dataclass
class PropertyInfo:
    """Information about a property (data or object property)"""
    name: str
    property_type: str  # 'data' or 'object'
    range_class: Optional[str] = None
    datatype: Optional[str] = None
    cardinality: Optional[str] = None  # 'single', 'multiple', 'exactly_one', etc.
    required: bool = False

@dataclass 
class ClassInfo:
    """Information about an RDF class"""
    name: str
    uri: str
    parent_classes: List[str]
    properties: List[PropertyInfo]
    description: Optional[str] = None
    property_uris: Dict[str, str] = field(default_factory=dict)  # Maps property name to URI

def ttl2py(ttl_file: str | io.TextIOBase) -> str:
    """
    Convert TTL file to Python classes
    
    Args:
        ttl_file: Path to TTL file or file-like object
        
    Returns:
        Generated Python code as string
    """
    if isinstance(ttl_file, str):
        with open(ttl_file, "r") as f:
            content = f.read()
        g = rdflib.Graph()
        g.parse(data=content, format="turtle")
    else:
        content = ttl_file.read()
        g = rdflib.Graph()
        g.parse(data=content, format="turtle")
    
    # Define common RDF/OWL/SHACL namespaces
    RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    SHACL = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    
    # Extract classes and their information
    classes: Dict[str, ClassInfo] = {}
    
    # Find all OWL classes
    for cls in g.subjects(RDF.type, OWL.Class):
        class_name = extract_class_name(cls)
        if class_name:
            classes[str(cls)] = ClassInfo(
                name=class_name,
                uri=str(cls),
                parent_classes=[],
                properties=[],
                description=get_description(g, cls)
            )
    
    # Find all RDFS classes (if not already OWL classes)
    for cls in g.subjects(RDF.type, RDFS.Class):
        if str(cls) not in classes:
            class_name = extract_class_name(cls)
            if class_name:
                classes[str(cls)] = ClassInfo(
                    name=class_name,
                    uri=str(cls),
                    parent_classes=[],
                    properties=[],
                    description=get_description(g, cls)
                )
    
    # Extract inheritance relationships
    for cls_uri, class_info in classes.items():
        for parent in g.objects(rdflib.URIRef(cls_uri), RDFS.subClassOf):
            if str(parent) in classes:
                parent_name = classes[str(parent)].name
                class_info.parent_classes.append(parent_name)
    
    # Extract properties
    properties: Dict[str, PropertyInfo] = {}
    
    # Object properties
    for prop in g.subjects(RDF.type, OWL.ObjectProperty):
        prop_name = extract_property_name(prop)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type='object',
                range_class=get_property_range(g, prop, classes)
            )
    
    # Data properties
    for prop in g.subjects(RDF.type, OWL.DatatypeProperty):
        prop_name = extract_property_name(prop)
        if prop_name:
            properties[str(prop)] = PropertyInfo(
                name=prop_name,
                property_type='data',
                datatype=get_datatype_range(g, prop)
            )
    
    # Extract SHACL shapes and constraints
    extract_shacl_constraints(g, classes, properties, SHACL)
    
    # Associate properties with classes based on domain
    for prop_uri, prop_info in properties.items():
        for domain in g.objects(rdflib.URIRef(prop_uri), RDFS.domain):
            if str(domain) in classes:
                classes[str(domain)].properties.append(prop_info)
                classes[str(domain)].property_uris[prop_info.name] = prop_uri
    
    # Inherit properties from parent classes
    inherit_parent_properties(classes)
    
    # Generate Python code
    return generate_python_code(classes, properties)

def extract_class_name(uri) -> Optional[str]:
    """Extract a clean class name from a URI"""
    uri_str = str(uri)
    if '#' in uri_str:
        name = uri_str.split('#')[-1]
    elif '/' in uri_str:
        name = uri_str.split('/')[-1]
    else:
        name = uri_str
    
    # Clean up the name to be a valid Python class name
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    if name and name[0].islower():
        name = name[0].upper() + name[1:]
    
    return name if name and name.isidentifier() else None

def extract_property_name(uri) -> Optional[str]:
    """Extract a clean property name from a URI"""
    uri_str = str(uri)
    if '#' in uri_str:
        name = uri_str.split('#')[-1]
    elif '/' in uri_str:
        name = uri_str.split('/')[-1]
    else:
        name = uri_str
    
    # Clean up the name to be a valid Python property name
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    if name and name[0].isupper():
        name = name[0].lower() + name[1:]
    
    return name if name and name.isidentifier() else None

def get_description(g: rdflib.Graph, resource) -> Optional[str]:
    """Get description/comment for a resource"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    
    for comment in g.objects(resource, RDFS.comment):
        return str(comment)
    
    for label in g.objects(resource, RDFS.label):
        return str(label)
    
    return None

def get_property_range(g: rdflib.Graph, prop, classes: Dict[str, ClassInfo]) -> Optional[str]:
    """Get the range class for an object property"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    
    for range_cls in g.objects(prop, RDFS.range):
        if str(range_cls) in classes:
            return classes[str(range_cls)].name
    
    return None

def get_datatype_range(g: rdflib.Graph, prop) -> Optional[str]:
    """Get the datatype range for a data property"""
    RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
    XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
    
    datatype_mapping = {
        str(XSD.string): 'str',
        str(XSD.integer): 'int',
        str(XSD.int): 'int',
        str(XSD.float): 'float',
        str(XSD.double): 'float',
        str(XSD.boolean): 'bool',
        str(XSD.date): 'datetime.date',
        str(XSD.dateTime): 'datetime.datetime',
    }
    
    for range_type in g.objects(prop, RDFS.range):
        return datatype_mapping.get(str(range_type), 'Any')
    
    return 'Any'

def extract_shacl_constraints(g: rdflib.Graph, classes: Dict[str, ClassInfo], 
                            properties: Dict[str, PropertyInfo], SHACL):
    """Extract SHACL constraints and apply them to properties"""
    
    # Find SHACL shapes
    for shape in g.subjects(rdflib.RDF.type, SHACL.NodeShape):
        # Get target class
        for target_class in g.objects(shape, SHACL.targetClass):
            if str(target_class) in classes:
                # Process property shapes
                for prop_shape in g.objects(shape, SHACL.property):
                    process_property_shape(g, prop_shape, classes[str(target_class)], 
                                         properties, SHACL)

def process_property_shape(g: rdflib.Graph, prop_shape, class_info: ClassInfo, 
                          properties: Dict[str, PropertyInfo], SHACL):
    """Process a SHACL property shape"""
    
    # Get the property path
    for path in g.objects(prop_shape, SHACL.path):
        if str(path) in properties:
            prop_info = properties[str(path)]
            
            # Check cardinality constraints
            for min_count in g.objects(prop_shape, SHACL.minCount):
                if int(str(min_count)) > 0:
                    prop_info.required = True
            
            for max_count in g.objects(prop_shape, SHACL.maxCount):
                if int(str(max_count)) == 1:
                    prop_info.cardinality = 'single'
                else:
                    prop_info.cardinality = 'multiple'

def inherit_parent_properties(classes: Dict[str, ClassInfo]):
    """
    Inherit properties from parent classes to child classes.
    Properties inherited from parents are made optional to represent capability links.
    """
    # Create a mapping from class name to class info for easier lookup
    name_to_class = {class_info.name: class_info for class_info in classes.values()}
    
    def collect_inherited_properties(class_info: ClassInfo, visited: Optional[Set[str]] = None) -> List[PropertyInfo]:
        """Recursively collect properties from parent classes"""
        if visited is None:
            visited = set()
        
        # Avoid infinite recursion in case of circular inheritance
        if class_info.name in visited:
            return []
        
        visited.add(class_info.name)
        inherited_props = []
        
        for parent_name in class_info.parent_classes:
            if parent_name in name_to_class:
                parent_class = name_to_class[parent_name]
                
                # Add direct properties from parent (preserve their required status)
                for prop in parent_class.properties:
                    # Create a copy of the property preserving the original required status
                    inherited_prop = PropertyInfo(
                        name=prop.name,
                        property_type=prop.property_type,
                        range_class=prop.range_class,
                        datatype=prop.datatype,
                        cardinality=prop.cardinality,
                        required=prop.required  # Preserve original required status
                    )
                    inherited_props.append(inherited_prop)
                
                # Recursively collect from grandparents
                inherited_props.extend(collect_inherited_properties(parent_class, visited.copy()))
        
        return inherited_props
    
    # Apply inheritance to each class
    for class_info in classes.values():
        inherited_props = collect_inherited_properties(class_info)
        
        # Add inherited properties that don't already exist
        existing_prop_names = {prop.name for prop in class_info.properties}
        
        for inherited_prop in inherited_props:
            if inherited_prop.name not in existing_prop_names:
                class_info.properties.append(inherited_prop)
                # Find the property URI from the inheritance chain
                def find_property_uri(prop_name: str, current_class: ClassInfo, search_visited: Optional[Set[str]] = None) -> Optional[str]:
                    if search_visited is None:
                        search_visited = set()
                    
                    if current_class.name in search_visited:
                        return None
                    search_visited.add(current_class.name)
                    
                    # Check if current class has the property URI
                    if prop_name in current_class.property_uris:
                        return current_class.property_uris[prop_name]
                    
                    # Search in parent classes
                    for parent_name in current_class.parent_classes:
                        if parent_name in name_to_class:
                            parent_class = name_to_class[parent_name]
                            uri = find_property_uri(prop_name, parent_class, search_visited.copy())
                            if uri:
                                return uri
                    return None
                
                prop_uri = find_property_uri(inherited_prop.name, class_info)
                if prop_uri:
                    class_info.property_uris[inherited_prop.name] = prop_uri

def generate_python_code(classes: Dict[str, ClassInfo], 
                        properties: Dict[str, PropertyInfo]) -> str:
    """Generate Python code from extracted class and property information"""
    
    code_lines = [
        "from __future__ import annotations",
        "from typing import Optional, List, Any, Union, ClassVar",
        "from pydantic import BaseModel, Field",
        "import datetime",
        "import uuid",
        "import rdflib",
        "from rdflib import Graph, URIRef, Literal, Namespace",
        "from rdflib.namespace import RDF, RDFS, OWL, XSD",
        "",
        "# Generated classes from TTL file",
        "",
        "# Base class for all RDF entities",
        "class RDFEntity(BaseModel):",
        "    \"\"\"Base class for all RDF entities with URI and namespace management\"\"\"",
        "    _namespace: ClassVar[str] = \"http://example.org/instance/\"",
        "    ",
        "    model_config = {",
        "        'arbitrary_types_allowed': True,",
        "        'extra': 'forbid'",
        "    }",
        "    ",
        "    def __init__(self, **kwargs):",
        "        super().__init__(**kwargs)",
        "        if not hasattr(self, '_uri'):",
        "            object.__setattr__(self, '_uri', f\"{self._namespace}{uuid.uuid4()}\")",
        "    ",
        "    @classmethod",
        "    def set_namespace(cls, namespace: str):",
        "        \"\"\"Set the namespace for generating URIs\"\"\"",
        "        cls._namespace = namespace",
        "        ",
        "    def rdf(self, subject_uri: str = None) -> Graph:",
        "        \"\"\"Generate RDF triples for this instance\"\"\"",
        "        g = Graph()",
        "        ",
        "        # Use stored URI or provided subject_uri",
        "        if subject_uri is None:",
        "            subject_uri = self._uri",
        "        subject = URIRef(subject_uri)",
        "        ",
        "        # Add class type",
        "        if hasattr(self, '_class_uri'):",
        "            g.add((subject, RDF.type, URIRef(self._class_uri)))",
        "        ",
        "        # Add properties",
        "        if hasattr(self, '_property_uris'):",
        "            for prop_name, prop_uri in self._property_uris.items():",
        "                prop_value = getattr(self, prop_name, None)",
        "                if prop_value is not None:",
        "                    if isinstance(prop_value, list):",
        "                        for item in prop_value:",
        "                            if hasattr(item, 'rdf'):",
        "                                # Add triples from related object",
        "                                g += item.rdf()",
        "                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))",
        "                            else:",
        "                                g.add((subject, URIRef(prop_uri), Literal(item)))",
        "                    elif hasattr(prop_value, 'rdf'):",
        "                        # Add triples from related object",
        "                        g += prop_value.rdf()",
        "                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))",
        "                    else:",
        "                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))",
        "        ",
        "        return g",
        "",
        ""
    ]
    
    # Sort classes to handle inheritance properly
    sorted_classes = topological_sort_classes(classes)
    
    for class_info in sorted_classes:
        code_lines.extend(generate_class_code(class_info))
        code_lines.append("")
    
    # Add model_rebuild() calls for forward references
    code_lines.append("# Rebuild models to resolve forward references")
    for class_info in sorted_classes:
        code_lines.append(f"{class_info.name}.model_rebuild()")
    code_lines.append("")
    
    return "\n".join(code_lines)

def topological_sort_classes(classes: Dict[str, ClassInfo]) -> List[ClassInfo]:
    """Sort classes so that dependencies come before classes that use them"""
    
    # More aggressive topological sort that prioritizes inheritance dependencies
    # and handles circular dependencies better
    sorted_classes = []
    visited = set()
    
    def get_inheritance_depth(class_info: ClassInfo, depth=0, visited_in_chain=None):
        """Calculate inheritance depth, handling cycles"""
        if visited_in_chain is None:
            visited_in_chain = set()
        
        if class_info.name in visited_in_chain:
            return depth  # Cycle detected, return current depth
        
        if not class_info.parent_classes:
            return depth
        
        visited_in_chain.add(class_info.name)
        max_parent_depth = depth
        
        for parent_name in class_info.parent_classes:
            for parent_class in classes.values():
                if parent_class.name == parent_name:
                    parent_depth = get_inheritance_depth(parent_class, depth + 1, visited_in_chain.copy())
                    max_parent_depth = max(max_parent_depth, parent_depth)
                    break
        
        return max_parent_depth
    
    # Sort by inheritance depth first (deepest inheritance last)
    classes_by_depth = [(get_inheritance_depth(class_info), class_info) for class_info in classes.values()]
    classes_by_depth.sort(key=lambda x: x[0])
    
    # Then do standard topological sort within each depth level
    def visit(class_info: ClassInfo, temp_visited=None):
        if temp_visited is None:
            temp_visited = set()
            
        if class_info.name in visited:
            return
        if class_info.name in temp_visited:
            # Circular dependency - add the class anyway to avoid infinite loops
            if class_info not in sorted_classes:
                sorted_classes.append(class_info)
                visited.add(class_info.name)
            return
        
        temp_visited.add(class_info.name)
        
        # Visit parent classes first (inheritance dependencies)
        for parent_name in class_info.parent_classes:
            for parent_class in classes.values():
                if parent_class.name == parent_name:
                    visit(parent_class, temp_visited.copy())
                    break
        
        visited.add(class_info.name)
        sorted_classes.append(class_info)
    
    # Process classes in order of inheritance depth
    for depth, class_info in classes_by_depth:
        visit(class_info)
    
    return sorted_classes

def generate_class_code(class_info: ClassInfo) -> List[str]:
    """Generate Python code for a single class"""
    
    lines = []
    
    # Add class docstring if description exists
    if class_info.description:
        lines.append('"""')
        lines.append(f'{class_info.description}')
        lines.append('"""')
    
    # Class definition with inheritance
    if class_info.parent_classes:
        parents = ", ".join(class_info.parent_classes)
        lines.append(f"class {class_info.name}({parents}, RDFEntity):")
    else:
        lines.append(f"class {class_info.name}(RDFEntity):")
    
    # Add class-specific metadata
    lines.append(f"    _class_uri: ClassVar[str] = '{class_info.uri}'")
    
    # Add property URI mapping
    if class_info.property_uris:
        prop_uris_dict = ", ".join([f"'{prop_name}': '{prop_uri}'" for prop_name, prop_uri in class_info.property_uris.items()])
        lines.append(f"    _property_uris: ClassVar[dict] = {{{prop_uris_dict}}}")
    else:
        lines.append("    _property_uris: ClassVar[dict] = {}")
    
    # Add properties
    if class_info.properties:
        for prop in class_info.properties:
            lines.append(f"    {generate_property_code(prop)}")
    else:
        lines.append("    pass")
    

    
    return lines

def generate_property_code(prop: PropertyInfo) -> str:
    """Generate code for a single property"""
    
    # Determine type annotation and Pydantic Field
    if prop.property_type == 'object' and prop.range_class:
        if prop.cardinality == 'multiple':
            type_annotation = f"List[{prop.range_class}]"
            default_value = "Field(default_factory=list)"
        else:
            type_annotation = f"Optional[{prop.range_class}]" if not prop.required else prop.range_class
            default_value = "Field(default=None)" if not prop.required else "Field(...)"
    elif prop.property_type == 'data' and prop.datatype:
        if prop.cardinality == 'multiple':
            type_annotation = f"List[{prop.datatype}]"
            default_value = "Field(default_factory=list)"
        else:
            type_annotation = f"Optional[{prop.datatype}]" if not prop.required else prop.datatype
            default_value = "Field(default=None)" if not prop.required else "Field(...)"
    else:
        type_annotation = "Optional[Any]"
        default_value = "Field(default=None)"
    
    return f"{prop.name}: {type_annotation} = {default_value}"