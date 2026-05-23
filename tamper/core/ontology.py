from pathlib import Path

from rdflib import Graph

Ontology = Graph()
Ontology.parse(Path(__file__).parent.parent / "tamper-core.ttl", format="turtle")
