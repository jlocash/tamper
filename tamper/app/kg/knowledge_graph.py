import abc

from rdflib import Graph, URIRef


class KnowledgeGraph(abc.ABC):

    @abc.abstractmethod
    def insert_statements_default(self, statements: Graph):
        pass

    @abc.abstractmethod
    def insert_statements(self, graph_name: URIRef, statements: Graph):
        pass

    @abc.abstractmethod
    def delete_statements_default(self, statements: Graph):
        pass

    @abc.abstractmethod
    def delete_statements(self, graph_name: URIRef, statements: Graph):
        pass

    @abc.abstractmethod
    def query(self, sparql_query: str):
        pass

    @abc.abstractmethod
    def update(self, sparql_update_query: str):
        pass
