from pathlib import Path

from rdflib import Graph

Ontology = Graph()
Ontology.parse(Path(__file__).parent.parent / "tamper-core.ttl", format="turtle")

ProvOntology = Graph()
ProvOntology.parse(Path(__file__).parent.parent / "prov-o.ttl", format="turtle")

PPlanOntology = Graph()
PPlanOntology.parse(Path(__file__).parent.parent / "p-plan.owl", format="xml")