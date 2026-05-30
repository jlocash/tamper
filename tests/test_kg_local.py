"""Tests for tamper.app.kg.local — LocalKnowledgeGraph and helpers."""

import tarfile
from pathlib import Path

import pytest
from rdflib import Graph, URIRef, Literal, Dataset

from tamper.app.kg.local import LocalKnowledgeGraph, InconsistencyError, check_consistency
from tamper.utils.make_tarball import get_asset_files, make_tarball
from tamper.vocabularies import TAMPER

_EX = URIRef("https://example.org/")
_SUBJECT = URIRef("https://example.org/subject")
_PREDICATE = URIRef("https://example.org/predicate")
_OBJECT = Literal("hello")


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
        graph_name = URIRef("https://example.org/g1")
        kg.insert_statements(graph_name, simple_graph)
        result = list(kg.query(
            f"SELECT ?o WHERE {{ GRAPH <{graph_name}> {{ <{_SUBJECT}> <{_PREDICATE}> ?o }} }}"
        ))
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
        result = list(kg.query(
            f"ASK {{ GRAPH <{graph_name}> {{ <{_SUBJECT}> <{_PREDICATE}> ?o }} }}"
        ))
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
        result = list(kg.query(
            f"ASK {{ GRAPH <{graph_name}> {{ <{_SUBJECT}> <{_PREDICATE}> ?o }} }}"
        ))
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
