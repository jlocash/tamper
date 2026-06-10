from pathlib import Path
from rdflib import Graph
import pyshacl

from tamper.errors import GraphValidationError


def validate_plan_graph(plan_graph: Graph):
    """
    Validates an operation plan graph according to a predefined set of SHACL rules.

    :return: Nothing
    :raises GraphValidationError: when the graph fails SHACL validation
    """
    shacl_graph_path = Path(__file__).parent / "plan-shacl.ttl"
    shacl_graph = Graph()
    shacl_graph.parse(shacl_graph_path, format="turtle")

    conforms, results_graph, results_text = pyshacl.validate(
        plan_graph,
        shacl_graph=shacl_graph,
        inference=None,
    )

    if not conforms:
        raise GraphValidationError(results_graph, results_text)
