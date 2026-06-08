import abc

from rdflib import Graph, URIRef
from rdflib.graph import _TripleOrQuadPatternType


class GraphNotFoundError(ValueError):
    def __init__(self, identifier: URIRef):
        super().__init__(f"Named graph with identifier {identifier} not found")


class KnowledgeGraph(abc.ABC):
    @abc.abstractmethod
    def insert_statements_default(self, statements: Graph):
        """Inserts statements into the default graph"""
        pass

    @abc.abstractmethod
    def insert_statements(self, graph_name: URIRef, statements: Graph):
        """Inserts statements into a named graph"""
        pass

    @abc.abstractmethod
    def delete_statements_default(self, statements: Graph):
        """Removes the given statements from the default graph"""
        pass

    @abc.abstractmethod
    def delete_statements(self, graph_name: URIRef, statements: Graph):
        """Removes the given statements from a named graph"""
        pass

    @abc.abstractmethod
    def replace_statements_default(self, statements: Graph):
        """
        For each (s, p) pair in the given statements, removes all existing
            triples with that pair from the default graph, and then inserts
            the new statements.
        """
        pass

    @abc.abstractmethod
    def replace_statements(self, identifier: URIRef, statements: Graph):
        """
        For each (s, p) pair in the given statements, removes all existing
            (s, p, ?) triples from the named graph, then inserts the new statements.
        """
        pass

    @abc.abstractmethod
    def query(
        self,
        sparql_query: str,
        default_graph: bool = True,
        named_graphs: list[URIRef] | None = None,
    ):
        """
        Executes a read-only SPARQL query on the graph union of the
        default graph and any provided named graphs.

        By default, only the default graph will be queried.
        """
        pass

    def query_named(self, identifier: URIRef, sparql_query: str):
        """An alias of ``query`` that scopes the given SPARQL query to the given named graph."""
        return self.query(sparql_query, False, [identifier])

    @abc.abstractmethod
    def get_default_graph(self) -> Graph:
        """Retrieves the default graph"""
        pass

    @abc.abstractmethod
    def get_named_graph(self, identifier: URIRef) -> Graph:
        """Retrieves the named graph given by ``identifier``"""
        pass

    @abc.abstractmethod
    def any(self, quad: _TripleOrQuadPatternType) -> bool:
        """Accepts a triple or quad pattern and returns True if any matches are found"""
        pass

    @abc.abstractmethod
    def describe(self, identifier: URIRef) -> Graph:
        """Alias for a DESCRIBE query that executes on the default graph"""
        pass
