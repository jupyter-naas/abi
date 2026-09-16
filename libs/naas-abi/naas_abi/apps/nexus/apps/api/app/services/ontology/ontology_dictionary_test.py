"""Dictionary projection tests; fixture graphs represent the permitted catalog."""
import importlib.util
from pathlib import Path
import unittest

from rdflib import Graph

spec = importlib.util.spec_from_file_location('dictionary_projection', Path(__file__).with_name('ontology_dictionary.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build_workspace_dictionary = module.build_workspace_dictionary

PREFIX = '''@prefix ex: <https://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
'''
def source(name, content):
    return ({'path': name + '.ttl', 'name': name, 'moduleName': name}, Graph().parse(data=PREFIX + content, format='turtle'))

class DictionaryTests(unittest.TestCase):
    def test_merge_keeps_sources_and_conflicting_definitions(self):
        items = build_workspace_dictionary([
            source('one', 'ex:A a owl:Class; rdfs:label "Same"; skos:definition "First" .'),
            source('two', 'ex:A a owl:Class; skos:definition "Second" . ex:B a owl:Class; rdfs:label "Same" .'),
        ])
        self.assertEqual(len(items), 2)
        a = next(item for item in items if item['id'].endswith('/A'))
        self.assertEqual(len(a['sources']), 2)
        self.assertEqual({d['value'] for d in a['definitions']}, {'First', 'Second'})

    def test_all_term_types_and_cross_file_parents(self):
        items = build_workspace_dictionary([
            source('one', 'ex:Child a owl:Class; rdfs:subClassOf ex:Parent, ex:Other . ex:p a owl:ObjectProperty . ex:d a owl:DatatypeProperty .'),
            source('two', 'ex:Parent a owl:Class; rdfs:label "Parent" . ex:n a owl:NamedIndividual . ex:a a owl:AnnotationProperty .'),
        ])
        self.assertEqual({item['type'] for item in items}, {'entity', 'relationship', 'attribute', 'individual', 'annotation'})
        child = next(item for item in items if item['id'].endswith('/Child'))
        self.assertEqual(len(child['parents']), 2)
        self.assertTrue(any(parent['id'] == 'https://example.org/Parent' and parent['name'] == 'Parent' for parent in child['parents']))

    def test_imports_do_not_expand_catalog_and_blank_nodes_are_not_terms(self):
        visible = source('allowed', 'ex:Ontology a owl:Ontology; owl:imports <file:///must-not-open.ttl> . ex:A a owl:Class . [] a owl:Class .')
        hidden = source('hidden', 'ex:Secret a owl:Class .')
        items = build_workspace_dictionary([visible])
        self.assertEqual([item['id'] for item in items], ['https://example.org/A'])
        self.assertNotIn(hidden[0], items[0]['sources'])

    def test_metadata_comes_from_the_selected_term(self):
        items = build_workspace_dictionary([source('metadata', '''
            @prefix dct: <http://purl.org/dc/terms/> .
            @prefix dcat: <http://www.w3.org/ns/dcat#> .
            ex:Parent a owl:Class; skos:example "Parent example" .
            ex:A a owl:Class; rdfs:subClassOf ex:Parent;
                skos:altLabel "Alias", "Another alias";
                skos:example "Own example";
                dct:contributor "Team"; dcat:contactPoint ex:Contact .
            ex:Contact rdfs:label "Support" .
        ''')])
        item = next(item for item in items if item['id'].endswith('/A'))
        self.assertEqual(item['aliases'], ['Alias', 'Another alias'])
        self.assertEqual(item['examples'], ['Own example'])
        self.assertEqual(item['contributors'], ['Team'])
        self.assertEqual(item['contacts'], ['Support'])

    def test_connections_keep_restrictions_and_exact_provenance(self):
        items = build_workspace_dictionary([
            source('one', '''
                ex:Process a owl:Class; rdfs:subClassOf ex:Parent,
                    [a owl:Restriction; owl:onProperty ex:uses; owl:someValuesFrom ex:Record] .
                ex:uses a owl:ObjectProperty; rdfs:label "uses"; rdfs:domain ex:Process .
                ex:Record a owl:Class .
                ex:Run a owl:NamedIndividual; ex:uses ex:Document .
                ex:Document a owl:NamedIndividual .
            '''),
            source('two', 'ex:Process a owl:Class . ex:Record a owl:Class .'),
        ])
        process = next(item for item in items if item['id'].endswith('/Process'))
        self.assertEqual(process['relations'][0]['kind'], 'restriction')
        self.assertEqual(process['relations'][0]['constraint'], 'some')
        self.assertEqual(process['relations'][0]['sources'][0]['path'], 'one.ttl')
        self.assertEqual(len(process['relations'][0]['sources']), 1)
        self.assertEqual([s['path'] for s in process['parents'][0]['sources']], ['one.ttl'])
        run = next(item for item in items if item['id'].endswith('/Run'))
        self.assertEqual(run['relations'][0]['kind'], 'assertion')

    def test_union_restrictions_are_not_presented_as_unconditional(self):
        items = build_workspace_dictionary([source('union', '''
            ex:A a owl:Class; rdfs:subClassOf [owl:unionOf (
                ex:B [a owl:Restriction; owl:onProperty ex:p; owl:someValuesFrom ex:C]
            )] .
        ''')])
        self.assertEqual(items[0]['relations'], [])

    def test_individuals_link_to_their_declared_classes(self):
        items = build_workspace_dictionary([source('units', '''
            ex:Unit a owl:Class .
            ex:Meter a owl:NamedIndividual, ex:Unit .
        ''')])
        meter = next(item for item in items if item['id'].endswith('/Meter'))
        self.assertEqual([p['id'] for p in meter['parents']], ['https://example.org/Unit'])
        self.assertEqual(meter['parents'][0]['sources'][0]['path'], 'units.ttl')

    def test_named_equivalent_classes_keep_source_and_do_not_follow_imports(self):
        items = build_workspace_dictionary([source('allowed', '''
            ex:Alias a owl:Class;
                owl:equivalentClass <http://purl.obolibrary.org/obo/BFO_0000015>,
                    [a owl:Class; owl:unionOf (ex:A ex:B)] .
        ''')])
        alias = next(item for item in items if item['id'].endswith('/Alias'))
        self.assertEqual(len(alias['equivalents']), 1)
        self.assertEqual(alias['equivalents'][0]['id'], 'http://purl.obolibrary.org/obo/BFO_0000015')
        self.assertEqual([s['path'] for s in alias['equivalents'][0]['sources']], ['allowed.ttl'])
        self.assertEqual(len(items), 1)

    def test_system_navigation_metadata_is_explicit_and_does_not_load_hidden_groups(self):
        allowed = source('allowed', '''
            @prefix abi: <http://ontology.naas.ai/abi/> .
            ex:Root a owl:Class; abi:systemViewKind "system" .
            ex:Group a owl:Class; abi:systemViewKind "subsystem"; abi:systemViewParent ex:Root .
            ex:P a owl:Class; rdfs:subClassOf ex:Group .
            ex:Annotation a owl:AnnotationProperty; abi:systemViewKind "system" .
        ''')
        items = {item['id']: item for item in build_workspace_dictionary([allowed])}
        self.assertEqual(items['https://example.org/Root']['systemViewKind'], 'system')
        self.assertEqual(items['https://example.org/Group']['systemViewParents'][0]['id'], 'https://example.org/Root')
        self.assertEqual(items['https://example.org/Group']['systemViewParents'][0]['sources'][0]['path'], 'allowed.ttl')
        self.assertIsNone(items['https://example.org/Annotation']['systemViewKind'])
        self.assertIsNone(items['https://example.org/P']['systemViewKind'])
        self.assertEqual(len(items), 4)

    def test_empty_catalog_is_empty(self):
        self.assertEqual(build_workspace_dictionary([]), [])

if __name__ == '__main__':
    unittest.main()
