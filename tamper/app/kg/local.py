from contextlib import contextmanager
from os import PathLike

from oxrdflib import OxigraphStore
from rdflib import URIRef, Graph, Dataset, XSD

import owlrl.DatatypeHandling
from owlrl import OWLRL_Semantics
from rdflib.graph import _TripleOrQuadPatternType

from tamper.vocabularies import TAMPER, load_core_ontology
from .knowledge_graph import GraphNotFoundError, KnowledgeGraph
from pathlib import Path


# AltXSDToPYTHON is owlrl's source table; use_Alt_lexical_conversions() copies it
# into rdflib's _toPythonMapping, which is what the reasoner actually dispatches on.
owlrl.DatatypeHandling.AltXSDToPYTHON[XSD.double] = float
owlrl.DatatypeHandling.AltXSDToPYTHON[XSD.float] = float


class InconsistencyError(Exception):
    pass


def check_consistency(ctx: Graph | Dataset) -> None:
    if isinstance(ctx, Dataset):
        tmp_graph = Graph()
        for s, p, o, _ in ctx.quads((None, None, None, None)):
            tmp_graph.add((s, p, o))
    else:
        tmp_graph = ctx

    tmp_graph += load_core_ontology()
    reasoner = OWLRL_Semantics(tmp_graph, False, False, False)
    reasoner.closure()
    if reasoner.error_messages:
        raise InconsistencyError(reasoner.error_messages)


class LocalKnowledgeGraph(KnowledgeGraph):
    """
    Implementation of KnowledgeGraph using a local file
    NOT thread safe
    """

    def __init__(self, path: PathLike[str]):
        self.path = Path(path)
        self.dataset = None
        self._open()

    def _open(self):
        store = OxigraphStore()
        self.dataset = Dataset(store=store)
        if not self.path.exists():
            return
        self.dataset.parse(self.path, format="ox-trig")

    def commit(self):
        # throws if graph contains semantic inconsistencies
        check_consistency(self.dataset)
        self.dataset.bind("tamper", TAMPER)
        self.dataset.commit()
        self.dataset.serialize(self.path, format="ox-trig")

    def rollback(self):
        self._open()

    @contextmanager
    def commit_or_rollback(self):
        try:
            yield None
            self.commit()
        except Exception:
            self.rollback()
            raise

    def insert_statements_default(self, statements: Graph):
        self.dataset.default_graph += statements

    def insert_statements(self, graph_name: URIRef, statements: Graph):
        g = self.dataset.graph(graph_name)
        g += statements

    def delete_statements_default(self, statements: Graph):
        self.dataset.default_graph -= statements

    def delete_statements(self, graph_name: URIRef, statements: Graph):
        g = self.dataset.graph(graph_name)
        g -= statements

    def replace_statements_default(self, statements: Graph):
        for s, p in statements.subject_predicates():
            self.dataset.default_graph.remove((s, p, None))
        self.dataset.default_graph += statements

    def replace_statements(self, identifier: URIRef, statements: Graph):
        g = self.dataset.graph(identifier)
        for s, p in statements.subject_predicates():
            g.remove((s, p, None))
        g += statements

    def query(
        self,
        sparql_query: str,
        default_graph: bool = True,
        named_graphs: list[URIRef] | None = None,
    ):
        ctx = Graph()
        if default_graph:
            ctx += self.dataset.default_graph
        if named_graphs:
            for named_graph in named_graphs:
                ctx += self.dataset.graph(named_graph)
        return ctx.query(sparql_query)

    def get_default_graph(self) -> Graph:
        copy = Graph(store="Oxigraph")
        copy += self.dataset.default_graph
        return copy

    def get_named_graph(self, identifier: URIRef) -> Graph:
        copy = Graph(identifier=identifier)
        copy += self.dataset.graph(identifier)
        if len(copy) == 0:
            raise GraphNotFoundError(identifier)
        return copy

    def any(self, quad: _TripleOrQuadPatternType) -> bool:
        return any(self.dataset.quads(quad))

    def describe(self, identifier: URIRef, graph_name: URIRef | None = None) -> Graph:
        query_str = f"DESCRIBE {identifier.n3()}"
        if graph_name is not None:
            result = self.query(
                query_str, default_graph=False, named_graphs=[graph_name]
            )
        else:
            result = self.query(query_str)
        return result.graph
