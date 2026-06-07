"""Tests for tamper.app.kg.local — LocalKnowledgeGraph and helpers."""

import tarfile

import pytest
from rdflib import Graph, URIRef, Literal, Dataset, XSD

from tamper.app.kg.local import (
    LocalKnowledgeGraph,
    check_consistency,
)
from tamper.utils.make_tarball import get_asset_files, make_tarball
from tamper.vocabularies import TAMPER

_EX = URIRef("https://example.org/")
_SUBJECT = URIRef("https://example.org/subject")
_PREDICATE = URIRef("https://example.org/predicate")
_OBJECT = Literal("hello", datatype=XSD.string)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kg(tmp_path):
    """A fresh LocalKnowledgeGraph backed by a temp file."""
    return LocalKnowledgeGraph(tmp_path / "dataset.trig")


@pytest.fixture
def simple_graph():
    """A tiny rdflib.Graph with one triple."""
    g = Graph()
    g.add((_SUBJECT, _PREDICATE, _OBJECT))
    return g


# ---------------------------------------------------------------------------
# LocalKnowledgeGraph — construction
# ---------------------------------------------------------------------------


class TestLocalKnowledgeGraphInit:
    def test_opens_without_existing_file(self, tmp_path):
        path = tmp_path / "new.trig"
        assert not path.exists()
        kg = LocalKnowledgeGraph(path)
        assert kg is not None

    def test_opens_existing_file(self, tmp_path):
        path = tmp_path / "dataset.trig"
        # create and persist a graph with one triple
        kg1 = LocalKnowledgeGraph(path)
        g = Graph()
        g.add((_SUBJECT, _PREDICATE, _OBJECT))
        kg1.insert_statements_default(g)
        kg1.commit()

        # re-open and verify the triple survived
        kg2 = LocalKnowledgeGraph(path)
        result = list(kg2.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert result[0]


# ---------------------------------------------------------------------------
# insert / query
# ---------------------------------------------------------------------------


class TestInsertAndQuery:
    def test_insert_default_and_ask(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        result = list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert result[0]

    def test_insert_named_graph_and_select(self, kg, simple_graph):
        # query() materializes a flat union of the requested graphs, so named
        # graphs are selected out-of-band via named_graphs rather than an
        # in-query GRAPH {} clause.
        graph_name = URIRef("https://example.org/g1")
        kg.insert_statements(graph_name, simple_graph)
        result = list(
            kg.query(
                f"SELECT ?o WHERE {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}",
                default_graph=False,
                named_graphs=[graph_name],
            )
        )
        assert len(result) == 1
        assert str(result[0].o) == "hello"

    def test_query_empty_graph_returns_no_rows(self, kg):
        result = list(kg.query("SELECT ?s WHERE { ?s ?p ?o }"))
        assert result == []

    def test_describe_returns_graph(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        result = kg.query(f"DESCRIBE <{_SUBJECT}>")
        assert result.graph is not None
        assert len(result.graph) > 0


# ---------------------------------------------------------------------------
# query scoping — default_graph toggle + named_graphs union
# ---------------------------------------------------------------------------


class TestQueryScoping:
    """query() runs against the flat union of the selected graphs."""

    def _ask(self, kg, **kwargs):
        return list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}", **kwargs))[0]

    def test_default_query_excludes_named_graph(self, kg, simple_graph):
        graph_name = URIRef("https://example.org/g1")
        kg.insert_statements(graph_name, simple_graph)
        # default graph only (the default) does not see named-graph triples
        assert not self._ask(kg)

    def test_named_graph_excluded_from_default_only_query(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        # asking for a named graph with default_graph=False sees nothing
        assert not self._ask(
            kg, default_graph=False, named_graphs=[URIRef("https://example.org/g1")]
        )

    def test_union_of_default_and_named(self, kg):
        default_g = Graph()
        default_g.add((_SUBJECT, _PREDICATE, Literal("from-default")))
        kg.insert_statements_default(default_g)

        named = URIRef("https://example.org/g1")
        named_g = Graph()
        named_g.add(
            (URIRef("https://example.org/s2"), _PREDICATE, Literal("from-named"))
        )
        kg.insert_statements(named, named_g)

        rows = list(
            kg.query(
                "SELECT ?o WHERE { ?s ?p ?o }",
                default_graph=True,
                named_graphs=[named],
            )
        )
        values = {str(r.o) for r in rows}
        assert values == {"from-default", "from-named"}

    def test_query_named_helper_scopes_to_single_graph(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)  # noise in the default graph
        named = URIRef("https://example.org/g1")
        kg.insert_statements(named, simple_graph)

        rows = list(
            kg.query_named(
                named, f"SELECT ?o WHERE {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"
            )
        )
        # exactly one row — only the named graph is in scope, not the default
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# graph accessors — get_default_graph / get_named_graph / any / describe
# ---------------------------------------------------------------------------


class TestGraphAccessors:
    def test_get_default_graph_returns_contents(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        g = kg.get_default_graph()
        assert (_SUBJECT, _PREDICATE, _OBJECT) in g

    def test_get_default_graph_is_detached_copy(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        g = kg.get_default_graph()
        g.remove((_SUBJECT, _PREDICATE, _OBJECT))
        # mutating the returned copy must not affect the store
        assert kg.any((_SUBJECT, _PREDICATE, None))

    def test_get_named_graph_returns_contents(self, kg, simple_graph):
        named = URIRef("https://example.org/g1")
        kg.insert_statements(named, simple_graph)
        g = kg.get_named_graph(named)
        assert (_SUBJECT, _PREDICATE, _OBJECT) in g

    def test_get_named_graph_missing_raises(self, kg):
        from tamper.app.kg.knowledge_graph import GraphNotFoundError

        with pytest.raises(GraphNotFoundError):
            kg.get_named_graph(URIRef("https://example.org/missing"))

    def test_any_true_for_present_triple(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        assert kg.any((_SUBJECT, None, None, None))

    def test_any_accepts_triple_pattern(self, kg, simple_graph):
        # the server relies on the 3-element pattern form
        kg.insert_statements_default(simple_graph)
        assert kg.any((_SUBJECT, _PREDICATE, None))

    def test_any_false_for_absent_triple(self, kg):
        assert not kg.any((URIRef("https://example.org/nope"), None, None, None))

    def test_any_sees_named_graph(self, kg, simple_graph):
        named = URIRef("https://example.org/g1")
        kg.insert_statements(named, simple_graph)
        assert kg.any((_SUBJECT, None, None, None))

    def test_describe_default_graph(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        g = kg.describe(_SUBJECT)
        assert (_SUBJECT, _PREDICATE, _OBJECT) in g

    def test_describe_scoped_to_named_graph(self, kg, simple_graph):
        named = URIRef("https://example.org/g1")
        kg.insert_statements(named, simple_graph)
        # without the graph_name the subject lives in a named graph, not default
        assert len(kg.describe(_SUBJECT)) == 0
        result = kg.describe(_SUBJECT, named)
        assert (_SUBJECT, _PREDICATE, _OBJECT) in result


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_default(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        kg.delete_statements_default(simple_graph)
        result = list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert not result[0]

    def test_delete_named_graph(self, kg, simple_graph):
        graph_name = URIRef("https://example.org/g1")
        kg.insert_statements(graph_name, simple_graph)
        kg.delete_statements(graph_name, simple_graph)
        result = list(
            kg.query(
                f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}",
                default_graph=False,
                named_graphs=[graph_name],
            )
        )
        assert not result[0]


# ---------------------------------------------------------------------------
# commit / rollback
# ---------------------------------------------------------------------------


class TestCommitAndRollback:
    def test_commit_persists_data(self, tmp_path, simple_graph):
        path = tmp_path / "dataset.trig"
        kg = LocalKnowledgeGraph(path)
        kg.insert_statements_default(simple_graph)
        kg.commit()
        assert path.exists()

        kg2 = LocalKnowledgeGraph(path)
        result = list(kg2.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert result[0]

    def test_rollback_undoes_uncommitted_insert(self, tmp_path, simple_graph):
        path = tmp_path / "dataset.trig"
        kg = LocalKnowledgeGraph(path)
        # commit empty state first
        kg.commit()

        kg.insert_statements_default(simple_graph)
        kg.rollback()

        result = list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert not result[0]


# ---------------------------------------------------------------------------
# SPARQL update
# ---------------------------------------------------------------------------


class TestSparqlUpdate:
    # NOTE: rdflib's Dataset.update() requires quads; bare triples in
    # INSERT DATA (without GRAPH {}) raise ValueError. The correct pattern
    # is always to insert into a named graph.
    def test_update_inserts_into_named_graph(self, kg):
        graph_name = URIRef("https://example.org/g1")
        kg.update(
            f"INSERT DATA {{ GRAPH <{graph_name}> {{ <{_SUBJECT}> <{_PREDICATE}> 42 }} }}"
        )
        result = list(
            kg.query(
                f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}",
                default_graph=False,
                named_graphs=[graph_name],
            )
        )
        assert result[0]

    def test_update_invalid_sparql_raises(self, kg):
        with pytest.raises(Exception):
            kg.update("THIS IS NOT SPARQL")


# ---------------------------------------------------------------------------
# check_consistency
# ---------------------------------------------------------------------------


class TestCheckConsistency:
    def test_consistent_graph_does_not_raise(self):
        g = Graph()
        g.add((_SUBJECT, _PREDICATE, _OBJECT))
        # plain graph with no ontology constraints should pass
        check_consistency(g)

    def test_consistent_dataset_does_not_raise(self):
        ds = Dataset()
        ds.default_graph.add((_SUBJECT, _PREDICATE, _OBJECT))
        check_consistency(ds)


# ---------------------------------------------------------------------------
# make_tarball / get_asset_files
# ---------------------------------------------------------------------------


class TestGetAssetFiles:
    def test_empty_dataset_yields_nothing(self):
        ds = Dataset()
        assert list(get_asset_files(ds)) == []

    def test_yields_asset_with_file_path_and_checksum(self, tmp_path):
        dummy = tmp_path / "dummy.txt"
        dummy.write_text("data")

        ds = Dataset()
        asset_uri = URIRef("asset://abc123")
        ds.default_graph.add((asset_uri, TAMPER.filePath, Literal(str(dummy))))
        ds.default_graph.add((asset_uri, TAMPER.checksum, Literal("sha256:abc123")))

        rows = list(get_asset_files(ds))
        assert len(rows) == 1
        uri, file_path, checksum = rows[0]
        assert uri == asset_uri
        assert "sha256:abc123" in checksum


class TestMakeTarball:
    def test_creates_tarball_with_dataset_trig(self, tmp_path):
        ds = Dataset()
        out = tmp_path / "out.tar.gz"
        make_tarball(ds, out)
        assert out.exists()
        with tarfile.open(out, "r:gz") as tar:
            names = tar.getnames()
        assert "dataset.trig" in names

    def test_tarball_includes_media_asset(self, tmp_path):
        dummy = tmp_path / "image.jpg"
        dummy.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        ds = Dataset()
        asset_uri = URIRef("asset://deadbeef")
        checksum_str = "sha256:deadbeef"
        ds.default_graph.add((asset_uri, TAMPER.filePath, Literal(str(dummy))))
        ds.default_graph.add((asset_uri, TAMPER.checksum, Literal(checksum_str)))

        out = tmp_path / "out.tar.gz"
        make_tarball(ds, out)

        with tarfile.open(out, "r:gz") as tar:
            names = tar.getnames()
        assert any("deadbeef" in n for n in names)

    def test_tarball_rewrites_file_path_in_dataset(self, tmp_path):
        dummy = tmp_path / "video.mp4"
        dummy.write_bytes(b"\x00" * 50)

        ds = Dataset()
        asset_uri = URIRef("asset://cafebabe")
        ds.default_graph.add((asset_uri, TAMPER.filePath, Literal(str(dummy))))
        ds.default_graph.add((asset_uri, TAMPER.checksum, Literal("sha256:cafebabe")))

        out = tmp_path / "out.tar.gz"
        make_tarball(ds, out)

        with tarfile.open(out, "r:gz") as tar:
            trig_member = tar.getmember("dataset.trig")
            f = tar.extractfile(trig_member)
            content = f.read().decode("utf-8")

        # original absolute path should NOT appear; relative assets/ path should
        assert str(dummy) not in content
        assert "cafebabe" in content
