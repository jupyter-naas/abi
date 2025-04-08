from src import services

triple_store = services.triple_store_service

subject = "http://ontology.naas.ai/abi/d33e3abd-bd53-4c7f-b36b-daf9e9175049"
graph = triple_store.get_subject_graph(subject)

# Print each triple in a readable format
for s, p, o in graph:
    print(f"Subject: {s}")
    print(f"Predicate: {p}")
    print(f"Object: {o}")
    print("-" * 80)  # Separator between triples



