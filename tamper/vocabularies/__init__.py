from pathlib import Path

from rdflib import Graph

# regenerate by running the following command from this directory:
# python3 -m rdflib.tools.defined_namespace_creator tamper-core.ttl "https://example.org/tamper/core#" TAMPER
from ._TAMPER import TAMPER

# regenerate by running the following command from this directory:
# python3 -m rdflib.tools.defined_namespace_creator tamper-plan.ttl "https://example.org/tamper/plan#" PLAN
from ._PLAN import PLAN


def load_core_ontology() -> Graph:
    g = Graph(store="Oxigraph")
    g.parse(Path(__file__).parent / "tamper-core.ttl", format="turtle")
    return g


def load_plan_ontology() -> Graph:
    g = Graph(store="Oxigraph")
    g.parse(Path(__file__).parent / "tamper-plan.ttl", format="turtle")
    return g


def load_prov_ontology() -> Graph:
    g = Graph(store="Oxigraph")
    g.parse(Path(__file__).parent / "prov-o.ttl", format="turtle")
    return g


__all__ = [
    "TAMPER",
    "PLAN",
    "load_core_ontology",
    "load_plan_ontology",
    "load_prov_ontology",
]
