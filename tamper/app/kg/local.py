from os import PathLike

from rdflib import URIRef, Graph, Dataset

from owlrl import OWLRL_Semantics

from tamper.namespaces import TAMPER
from tamper.core import Ontology
from .knowledge_graph import KnowledgeGraph
from pathlib import Path


class InconsistencyError(Exception):
    pass


def check_consistency(ctx: Graph | Dataset) -> None:
    if isinstance(ctx, Dataset):
        tmp_graph = Graph()
        for s, p, o, _ in ctx.quads((None, None, None, None)):
            tmp_graph.add((s, p, o))
    else:
        tmp_graph = ctx

    tmp_graph += Ontology
    reasoner = OWLRL_Semantics(tmp_graph, False, False, False)
    reasoner.closure()
    if reasoner.error_messages:
        raise InconsistencyError(reasoner.error_messages)


def _read_dataset(path: PathLike[str]) -> Dataset:
    dataset = Dataset()
    dataset.parse(Path(path), format="trig")
    return dataset


class LocalKnowledgeGraph(KnowledgeGraph):
    def __init__(self, path: PathLike[str], fmt="trig"):
        self.format = fmt
        self.path = Path(path)
        self.dataset = Dataset()
        self._open()

    def _open(self):
        if not self.path.exists():
            return
        dataset = Dataset()
        dataset.parse(self.path, format=self.format)
        self.dataset = dataset

    def commit(self):
        self.dataset.bind("tamper", TAMPER)
        self.dataset.serialize(self.path, format=self.format)

    def rollback(self):
        self._open()

    def insert_statements_default(self, statements: Graph):
        tmp = Dataset()
        tmp += self.dataset
        tmp.default_graph += statements
        check_consistency(tmp)
        self.dataset = tmp

    def insert_statements(self, graph_name: URIRef, statements: Graph):
        tmp = Dataset()
        tmp += self.dataset
        g = tmp.graph(graph_name)
        g += statements
        check_consistency(tmp)
        self.dataset = tmp

    def delete_statements_default(self, statements: Graph):
        self.dataset.default_graph -= statements

    def delete_statements(self, graph_name: URIRef, statements: Graph):
        g = self.dataset.graph(graph_name)
        g -= statements

    def query(self, sparql_query: str):
        return self.dataset.query(sparql_query)

    def update(self, sparql_update_query: str):
        tmp = Dataset()
        tmp += self.dataset
        tmp.update(sparql_update_query)
        check_consistency(tmp)
        self.dataset = tmp
