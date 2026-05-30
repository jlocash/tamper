"""Tests for tamper.ops.video — TranscodeVideo operation."""

from pathlib import Path

import pytest
from rdflib import Graph, RDF

from tamper.ops.video import TranscodeVideo
from tamper.vocabularies import TAMPER

TEST_MEDIA = Path(__file__).parent / "test-media"
VIDEO = TEST_MEDIA / "video"

_MP4 = VIDEO / "file_example_MP4_480_1_5MG.mp4"


class TestTranscodeVideo:
    def test_valid_construction(self):
        op = TranscodeVideo(video_encoder="libx264", crf=23)
        assert op.video_encoder == "libx264"
        assert op.crf == 23

    def test_crf_boundary_zero(self):
        op = TranscodeVideo("libx264", crf=0)
        assert op.crf == 0

    def test_crf_boundary_63(self):
        op = TranscodeVideo("libx264", crf=63)
        assert op.crf == 63

    def test_empty_encoder_raises(self):
        with pytest.raises(ValueError, match="video_encoder"):
            TranscodeVideo("", crf=23)

    def test_crf_below_range_raises(self):
        with pytest.raises(ValueError, match="crf"):
            TranscodeVideo("libx264", crf=-1)

    def test_crf_above_range_raises(self):
        with pytest.raises(ValueError, match="crf"):
            TranscodeVideo("libx264", crf=64)

    def test_subject_uri_is_unique(self):
        a = TranscodeVideo("libx264", 23)
        b = TranscodeVideo("libx264", 23)
        assert a.subject != b.subject

    def test_graph_rdftype(self):
        op = TranscodeVideo("libx264", 23)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.TranscodeVideo) in g

    def test_graph_video_encoder_literal(self):
        op = TranscodeVideo("libvpx-vp9", 30)
        g = op.graph()
        assert str(g.value(op.subject, TAMPER.videoEncoder)) == "libvpx-vp9"

    def test_graph_crf_literal(self):
        op = TranscodeVideo("libx264", 18)
        g = op.graph()
        assert int(g.value(op.subject, TAMPER.crf)) == 18

    def test_copy_from_graph_roundtrip(self):
        original = TranscodeVideo("libx265", 28)
        g = original.graph()
        restored = TranscodeVideo.copy_from_graph(g, original.subject)
        assert restored.video_encoder == "libx265"
        assert restored.crf == 28

    def test_copy_from_graph_missing_encoder_raises(self):
        from rdflib import URIRef
        g = Graph()
        subject = URIRef("operation://test")
        with pytest.raises(ValueError, match="video encoder"):
            TranscodeVideo.copy_from_graph(g, subject)

    def test_copy_from_graph_missing_crf_raises(self):
        from rdflib import URIRef, Literal
        subject = URIRef("operation://test")
        g = Graph()
        g.add((subject, TAMPER.videoEncoder, Literal("libx264")))
        with pytest.raises(ValueError, match="CRF"):
            TranscodeVideo.copy_from_graph(g, subject)

    def test_transform_produces_output_file(self, tmp_path):
        op = TranscodeVideo(video_encoder="libx264", crf=40)
        out = tmp_path / "out.mp4"
        op.transform(_MP4, out)
        assert out.exists()
        assert out.stat().st_size > 0
