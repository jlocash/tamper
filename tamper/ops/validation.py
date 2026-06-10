from rdflib import Graph
from pathlib import Path
import pyshacl

from tamper.errors import GraphValidationError

SHAPES_FILE = Path(__file__).parent / "operation-shapes.ttl"


def validate_operations(graph: Graph):
    shapes_graph = Graph(store="Oxigraph")
    shapes_graph.parse(SHAPES_FILE)

    conforms, results_graph, results_text = pyshacl.validate(
        graph, shacl_graph=shapes_graph, inference=None
    )

    if not conforms:
        raise GraphValidationError(results_graph, results_text)
