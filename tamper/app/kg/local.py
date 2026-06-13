from contextlib import contextmanager
from os import PathLike

import reasonable
from oxrdflib import OxigraphStore
from rdflib import URIRef, Graph, Dataset, OWL
from rdflib.graph import (
    DATASET_DEFAULT_GRAPH_ID,
    _ContextIdentifierType,
    _TripleOrQuadPatternType,
    _TripleType,
)

from tamper.vocabularies import TAMPER, load_core_ontology
from .knowledge_graph import GraphNotFoundError, KnowledgeGraph
from pathlib import Path


class InconsistencyError(Exception):
    pass


def _check_consistency(graph: Graph) -> None:
    """
    Raise InconsistencyError if any individual is (inferred to be) a member
    of two disjoint classes.
    """
    data = Graph()
    data += graph
    data += load_core_ontology()

    reasoner = reasonable.PyReasoner()
    reasoner.from_graph(data)
    for triple in reasoner.reason():
        data.add(triple)

    # reasonable won't throw exceptions on
    # inconsistencies like owlrl does, so we need
    # to check for them manually
    qres = data.query(f"""
    PREFIX owl: <{OWL}>
    SELECT DISTINCT ?s ?A ?B WHERE {{
        ?s a ?A, ?B .
        FILTER(?A != ?B)
        {{ ?A owl:disjointWith ?B }}
        UNION
        {{ 
            ?axiom a owl:AllDisjointClasses ;
                owl:members/rdf:rest*/rdf:first ?A ;
                owl:members/rdf:rest*/rdf:first ?B .
        }}
    }}
    """)

    errors = []
    for row in qres:
        errors.append(
            f"Disjoint classes {row.A} and {row.B} have a common individual {row.s}"
        )

    if len(errors):
        raise InconsistencyError(errors)


class WithRollback(OxigraphStore):
    """
    Wraps an OxigraphStore and tracks a write log that can
    be undone with rollback()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_aware = True
        self.log: list[tuple[_TripleType, _ContextIdentifierType, str]] = []

    def update(self, update, initNs, initBindings, queryGraph, **kwargs):
        raise NotImplementedError("This store does not support SPARQL update")

    def _contains(self, triple, context) -> bool:
        return next(self.triples(triple, context), None) is not None

    def add(self, triple, context, quoted=False):
        if quoted:
            raise ValueError("store is not formula aware")
        if not self._contains(triple, context):
            self.log.append((triple, context.identifier, "add"))
        super().add(triple, context)

    def addN(self, quads):
        # quads is typically a generator (e.g. Graph.__iadd__); materialize it
        # so logging doesn't exhaust it before the write
        quads = list(quads)
        new = [
            ((s, p, o), ctx.identifier)
            for s, p, o, ctx in quads
            if not self._contains((s, p, o), ctx)
        ]
        super().addN(quads)
        self.log.extend((triple, name, "add") for triple, name in new)

    def remove(self, triple, context=None):
        for t, ctxs in self.triples(triple, context):
            for ctx in ctxs:
                self.log.append((t, ctx.identifier, "rm"))
        super().remove(triple, context)

    def commit(self):
        self.log = []

    def rollback_to(self, mark: int):
        while len(self.log) > mark:
            triple, identifier, optype = self.log.pop()
            context = Graph(identifier=identifier, store=self)
            if optype == "add":
                super().remove(triple, context)
            else:
                super().add(triple, context)

    def rollback(self):
        self.rollback_to(0)


class LocalKnowledgeGraph(KnowledgeGraph):
    """
    Implementation of KnowledgeGraph using a local file
    NOT thread safe
    """

    def __init__(self, data_dir: PathLike[str]):
        self.dir = Path(data_dir)
        self.store = None
        self.dataset = None
        self._tx_depth = 0
        self._open()

    def _open(self):
        self.store = WithRollback()
        self.dataset = Dataset(store=self.store)
        self.dataset.open(str(self.dir))

    def commit(self):
        self.dataset.bind("tamper", TAMPER)
        self.dataset.commit()

    def rollback(self):
        self.dataset.rollback()

    @contextmanager
    def tx(self):
        """
        Transactional scope. On error, rolls back every write made since the
        scope was entered and re-raises. The outermost tx commits on success;
        nested txs act as savepoints, leaving the commit to the outermost one.
        """
        mark = len(self.store.log)
        self._tx_depth += 1
        try:
            yield None
        except Exception:
            self.store.rollback_to(mark)
            raise
        else:
            if self._tx_depth == 1:
                self.commit()
        finally:
            self._tx_depth -= 1

    def insert_statements(self, identifier: URIRef, statements: Graph):
        with self.tx():
            g = self.dataset.graph(identifier)
            g += statements
            _check_consistency(g)

    def insert_statements_default(self, statements: Graph):
        self.insert_statements(DATASET_DEFAULT_GRAPH_ID, statements)

    def delete_statements(self, identifier: URIRef, statements: Graph):
        g = self.dataset.graph(identifier)
        g -= statements

    def delete_statements_default(self, statements: Graph):
        return self.delete_statements(DATASET_DEFAULT_GRAPH_ID, statements)

    def replace_statements(self, identifier: URIRef, statements: Graph):
        with self.tx():
            g = self.dataset.graph(identifier)
            for s, p in statements.subject_predicates():
                g.remove((s, p, None))
            g += statements
            _check_consistency(g)

    def replace_statements_default(self, statements: Graph):
        self.replace_statements(DATASET_DEFAULT_GRAPH_ID, statements)

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

    def get_named_graph(self, identifier: URIRef) -> Graph:
        copy = Graph(identifier=identifier)
        copy += self.dataset.graph(identifier)
        if len(copy) == 0:
            raise GraphNotFoundError(identifier)
        return copy

    def get_default_graph(self) -> Graph:
        return self.get_named_graph(DATASET_DEFAULT_GRAPH_ID)

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
