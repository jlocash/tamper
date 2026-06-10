from rdflib import Graph


class GraphValidationError(Exception):
    def __init__(self, results_graph: Graph, results_message: str):
        super().__init__(results_message)
        self.results_graph = results_graph
