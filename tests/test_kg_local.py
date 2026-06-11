"""Tests for the KnowledgeGraph interface and LocalKnowledgeGraph-specific helpers."""

import tarfile

import pytest
from rdflib import Graph, URIRef, Literal, Dataset, XSD

from tamper.app.kg.local import (
    LocalKnowledgeGraph,
    check_consistency,
)
from tamper.core.assets import AssetURI
from tamper.utils.make_tarball import get_asset_files, make_tarball
from tamper.vocabularies import TAMPER

_SUBJECT = URIRef("https://example.org/subject")
_PREDICATE = URIRef("https://example.org/predicate")
_PREDICATE2 = URIRef("https://example.org/predicate2")
_OBJECT = Literal("hello", datatype=XSD.string)
_OBJECT2 = Literal("world", datatype=XSD.string)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_local_kg(tmp_path):
    return LocalKnowledgeGraph(tmp_path / "dataset.trig")


_KG_IMPLS = [_make_local_kg]
_KG_IDS = ["LocalKnowledgeGraph"]


@pytest.fixture(params=_KG_IMPLS, ids=_KG_IDS)
def kg(request, tmp_path):
    """A fresh KnowledgeGraph instance, parameterized over all implementations."""
    return request.param(tmp_path)


@pytest.fixture
def simple_graph():
    """A tiny rdflib.Graph with one triple."""
    g = Graph()
    g.add((_SUBJECT, _PREDICATE, _OBJECT))
    return g


# ---------------------------------------------------------------------------
# KnowledgeGraph interface — insert / query
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
# KnowledgeGraph interface — query scoping
# ---------------------------------------------------------------------------


class TestQueryScoping:
    """query() runs against the flat union of the selected graphs."""

    def _ask(self, kg, **kwargs):
        return list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}", **kwargs))[0]

    def test_default_query_excludes_named_graph(self, kg, simple_graph):
        graph_name = URIRef("https://example.org/g1")
        kg.insert_statements(graph_name, simple_graph)
        assert not self._ask(kg)

    def test_named_graph_excluded_from_default_only_query(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
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
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# KnowledgeGraph interface — graph accessors
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
        assert len(kg.describe(_SUBJECT)) == 0
        result = kg.describe(_SUBJECT, named)
        assert (_SUBJECT, _PREDICATE, _OBJECT) in result


# ---------------------------------------------------------------------------
# KnowledgeGraph interface — delete
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
# KnowledgeGraph interface — replace
# ---------------------------------------------------------------------------


class TestReplace:
    def test_replace_default_updates_existing_value(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)

        updated = Graph()
        updated.add((_SUBJECT, _PREDICATE, _OBJECT2))
        kg.replace_statements_default(updated)

        g = kg.get_default_graph()
        assert list(g.objects(_SUBJECT, _PREDICATE)) == [_OBJECT2]

    def test_replace_default_no_duplicate_on_repeated_call(self, kg, simple_graph):
        kg.insert_statements_default(simple_graph)
        kg.replace_statements_default(simple_graph)

        g = kg.get_default_graph()
        assert len(list(g.objects(_SUBJECT, _PREDICATE))) == 1

    def test_replace_default_only_clears_matching_sp_pairs(self, kg):
        g = Graph()
        g.add((_SUBJECT, _PREDICATE, _OBJECT))
        g.add((_SUBJECT, _PREDICATE2, _OBJECT2))
        kg.insert_statements_default(g)

        replacement = Graph()
        replacement.add((_SUBJECT, _PREDICATE, Literal("new", datatype=XSD.string)))
        kg.replace_statements_default(replacement)

        default = kg.get_default_graph()
        assert list(default.objects(_SUBJECT, _PREDICATE)) == [
            Literal("new", datatype=XSD.string)
        ]
        assert list(default.objects(_SUBJECT, _PREDICATE2)) == [_OBJECT2]

    def test_replace_default_inserts_when_no_prior_value(self, kg):
        replacement = Graph()
        replacement.add((_SUBJECT, _PREDICATE, _OBJECT))
        kg.replace_statements_default(replacement)

        assert kg.any((_SUBJECT, _PREDICATE, None))

    def test_replace_named_updates_existing_value(self, kg, simple_graph):
        named = URIRef("https://example.org/g1")
        kg.insert_statements(named, simple_graph)

        updated = Graph()
        updated.add((_SUBJECT, _PREDICATE, _OBJECT2))
        kg.replace_statements(named, updated)

        g = kg.get_named_graph(named)
        assert list(g.objects(_SUBJECT, _PREDICATE)) == [_OBJECT2]

    def test_replace_named_does_not_affect_default_graph(self, kg, simple_graph):
        named = URIRef("https://example.org/g1")
        kg.insert_statements_default(simple_graph)
        kg.insert_statements(named, simple_graph)

        updated = Graph()
        updated.add((_SUBJECT, _PREDICATE, _OBJECT2))
        kg.replace_statements(named, updated)

        default = kg.get_default_graph()
        assert list(default.objects(_SUBJECT, _PREDICATE)) == [_OBJECT]


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
        kg1 = LocalKnowledgeGraph(path)
        g = Graph()
        g.add((_SUBJECT, _PREDICATE, _OBJECT))
        kg1.insert_statements_default(g)
        kg1.commit()

        kg2 = LocalKnowledgeGraph(path)
        result = list(kg2.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert result[0]


# ---------------------------------------------------------------------------
# LocalKnowledgeGraph — commit / rollback
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
        kg.commit()

        kg.insert_statements_default(simple_graph)
        kg.rollback()

        result = list(kg.query(f"ASK {{ <{_SUBJECT}> <{_PREDICATE}> ?o }}"))
        assert not result[0]


# ---------------------------------------------------------------------------
# check_consistency helper
# ---------------------------------------------------------------------------


class TestCheckConsistency:
    def test_consistent_graph_does_not_raise(self):
        g = Graph()
        g.add((_SUBJECT, _PREDICATE, _OBJECT))
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
        asset_uri = AssetURI("abc123")
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
        asset_uri = AssetURI("deadbeef")
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
        asset_uri = AssetURI("cafebabe")
        ds.default_graph.add((asset_uri, TAMPER.filePath, Literal(str(dummy))))
        ds.default_graph.add((asset_uri, TAMPER.checksum, AssetURI("cafebabe")))

        out = tmp_path / "out.tar.gz"
        make_tarball(ds, out)

        with tarfile.open(out, "r:gz") as tar:
            trig_member = tar.getmember("dataset.trig")
            f = tar.extractfile(trig_member)
            content = f.read().decode("utf-8")

        assert str(dummy) not in content
        assert "cafebabe" in content
