from io import StringIO

import pytest
import requests
from naas_abi_core.utils.onto2py.onto2py import onto2py
from pydantic import ValidationError


def ttl_to_module(ttl_file, module_name):
    # Generate Python code from TTL
    python_code = onto2py(ttl_file)

    with open(module_name + ".py", "w") as f:
        f.write(python_code)

    import importlib.util

    spec = importlib.util.spec_from_file_location(module_name, module_name + ".py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def test_cco_to_py():
    """Test conversion of CCO ontology to Python classes"""
    response = requests.get(
        "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/refs/heads/develop/src/cco-merged/CommonCoreOntologiesMerged.ttl"
    )

    assert response.status_code == 200, f"Failed to fetch TTL file: {response.text}"

    ttl_file = StringIO(response.text)
    module = ttl_to_module(ttl_file, "cco_merged")

    e = module.Ont00000671()
    assert e.rdf().serialize(format="turtle") == e.rdf().serialize(format="turtle")


def test_bfo_to_py():
    """Test conversion of BFO core ontology to Python classes"""
    response = requests.get(
        "https://raw.githubusercontent.com/BFO-ontology/BFO-2020/refs/heads/master/src/owl/bfo-core.ttl"
    )

    assert response.status_code == 200, f"Failed to fetch TTL file: {response.text}"

    ttl_file = StringIO(response.text)

    # Generate Python code from TTL
    python_code = onto2py(ttl_file)

    with open("bfo-core.py", "w") as f:
        f.write(python_code)

    import importlib.util

    spec = importlib.util.spec_from_file_location("bfo_core", "bfo-core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Verify we got some generated code
    assert python_code, "No Python code was generated"
    assert "class" in python_code, "No classes found in generated code"
    assert "BaseModel" in python_code, "Pydantic BaseModel missing"

    print("Generated Python code:")
    print("=" * 50)
    print(python_code)
    print("=" * 50)

    module.BFO_0000001()


def test_simple_ttl():
    """Test with a simple TTL example"""
    simple_ttl = """@prefix ex: <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Define classes
ex:Person rdf:type owl:Class ;
    rdfs:label "Person" ;
    rdfs:comment "A human being" .

ex:Organization rdf:type owl:Class ;
    rdfs:label "Organization" ;
    rdfs:comment "A group or institution" .

# Define properties
ex:hasName rdf:type owl:DatatypeProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:string ;
    rdfs:label "has name" .

ex:hasAge rdf:type owl:DatatypeProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:integer ;
    rdfs:label "has age" .

ex:worksFor rdf:type owl:ObjectProperty ;
    rdfs:domain ex:Person ;
    rdfs:range ex:Organization ;
    rdfs:label "works for" .
"""

    ttl_file = StringIO(simple_ttl)
    python_code = onto2py(ttl_file)

    print("Generated Python code from simple TTL:")
    print("=" * 50)
    print(python_code)
    print("=" * 50)

    # Verify expected content
    assert "class Person(RDFEntity):" in python_code
    assert "class Organization(RDFEntity):" in python_code
    assert "hasName: Optional[str] = Field(default=None)" in python_code
    assert "hasAge: Optional[int] = Field(default=None)" in python_code
    assert "worksFor: Optional[Organization] = Field(default=None)" in python_code


def test_shacl_ttl():
    """Test with a TTL example using SHACL constraints"""
    shacl_ttl = """@prefix ex: <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Define classes
ex:Person rdf:type owl:Class ;
    rdfs:label "Person" ;
    rdfs:comment "A human being" .

ex:Pet rdf:type owl:Class ;
    rdfs:label "Pet" ;
    rdfs:comment "A domesticated animal kept for companionship" .

ex:PetOwner rdf:type owl:Class ;
    rdfs:subClassOf ex:Person ;
    rdfs:label "Pet Owner" ;
    rdfs:comment "A person who owns a pet" .

# Define data properties
ex:hasName rdf:type owl:DatatypeProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:string ;
    rdfs:label "has name" .

ex:hasAge rdf:type owl:DatatypeProperty ;
    rdfs:domain ex:Person ;
    rdfs:range xsd:integer ;
    rdfs:label "has age" .

ex:petName rdf:type owl:DatatypeProperty ;
    rdfs:domain ex:Pet ;
    rdfs:range xsd:string ;
    rdfs:label "pet name" .

# Define object properties
ex:hasPet rdf:type owl:ObjectProperty ;
    rdfs:domain ex:PetOwner ;
    rdfs:range ex:Pet ;
    rdfs:label "has pet" .

# SHACL constraints
ex:PersonShape rdf:type sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:property [
        sh:path ex:hasName ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string
    ] ;
    sh:property [
        sh:path ex:hasAge ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
        sh:maxInclusive 150
    ] .

ex:PetShape rdf:type sh:NodeShape ;
    sh:targetClass ex:Pet ;
    sh:property [
        sh:path ex:petName ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:datatype xsd:string
    ] .

ex:PetOwnerShape rdf:type sh:NodeShape ;
    sh:targetClass ex:PetOwner ;
    sh:property [
        sh:path ex:hasPet ;
        sh:minCount 1 ;
        sh:class ex:Pet
    ] .
"""

    ttl_file = StringIO(shacl_ttl)
    python_code = onto2py(ttl_file)

    print("Generated Python code from SHACL TTL:")
    print("=" * 50)
    print(python_code)
    print("=" * 50)

    # Verify expected content
    assert "class Person(RDFEntity):" in python_code
    assert "class Pet(RDFEntity):" in python_code
    assert "class PetOwner(Person, RDFEntity):" in python_code
    assert "hasName: str = Field(...)" in python_code  # Required property
    assert "hasAge: int = Field(...)" in python_code  # Required property
    assert "petName: str = Field(...)" in python_code  # Required property for Pet
    assert "hasPet: Pet = Field(...)" in python_code  # Required property for PetOwner

    import os
    import tempfile

    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "shacl_ttl.py")

    with open(temp_file, "w") as f:
        f.write(python_code)

    with open("shacl_ttl.py", "w") as f:
        f.write(python_code)

    # Load the generated code
    import importlib.util

    spec = importlib.util.spec_from_file_location("shacl_ttl", temp_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # assert module.Person.hasName is not None, module.Person
    # assert module.Person.hasAge is not None, module.Person
    # assert module.Pet.petName is not None, module.Pet
    # assert module.PetOwner.hasPet is not None, module.PetOwner

    person = module.Person(hasName="John Doe", hasAge=30)
    print(person)
    assert person.hasName == "John Doe"
    assert person.hasAge == 30

    pet = module.Pet(petName="Fluffy")
    print(pet)
    assert pet.petName == "Fluffy"

    pet_owner = module.PetOwner(hasPet=pet, hasName="John Doe", hasAge=30)
    print(pet_owner)
    assert pet_owner.hasPet == pet

    g = pet_owner.rdf()
    for s, p, o in g:
        print(s, p, o)
    print(g.serialize(format="turtle"))
    # Should have 6 triples: 2 type declarations + 4 property assertions
    # PetOwner: type, hasName, hasAge, hasPet
    # Pet: type, petName
    assert len(list(g)) == 6, list(g)

    # Assert this is raising a validation error
    with pytest.raises(ValidationError):
        module.PetOwner(hasName="John Doe", hasAge=30)
