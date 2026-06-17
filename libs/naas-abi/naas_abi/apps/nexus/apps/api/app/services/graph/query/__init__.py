"""Backend-driven graph query capability (Explore rework, AUDIT §7b).

Pure compiler + safety layer that lowers a ``ViewQuerySpec`` into a single portable
SPARQL query (Jena/Fuseki in prod, Oxigraph in dev). I/O lives in the service layer.
"""
