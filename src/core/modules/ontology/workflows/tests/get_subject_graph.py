from abi.utils.SPARQL import get_subject_graph

def test_get_subject_graph(uri: str, depth: int = 1):
    graph = get_subject_graph(uri, depth=depth)
    return graph

if __name__ == "__main__":
    graph = test_get_subject_graph("http://ontology.naas.ai/abi/4d4e6bc4-b396-4d26-b42b-3d257cde1738", depth=2)
    print(graph.serialize(format="turtle"))