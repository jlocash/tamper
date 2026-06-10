"""Behavioral tests for tamper.ops.video — TranscodeVideo."""

from pathlib import Path
from uuid import uuid4

import ffmpeg
import pytest
from rdflib import PROV, Graph, URIRef

from tamper.core import VideoAsset, load_asset_from_file
from tamper.ops.video import TranscodeVideo

TEST_MEDIA = Path(__file__).parent / "test-media"
MP4 = TEST_MEDIA / "video" / "file_example_MP4_480_1_5MG.mp4"
MP3 = TEST_MEDIA / "audio" / "file_example_MP3_700KB.mp3"


def _streams(path: Path) -> list[dict]:
    return ffmpeg.probe(str(path))["streams"]


def _run(src: Path, out_dir: Path, **params):
    """Run TranscodeVideo over ``src``, returning (input, output, op)."""
    g = Graph()
    asset = load_asset_from_file(g, src)
    op = TranscodeVideo.new(g, URIRef(f"operation://{uuid4()}"))
    for name, value in params.items():
        setattr(op, name, value)
    op.used(asset.identifier)
    op.mutate(out_dir)

    generated = next(op.get_generated(), None)
    assert generated is not None, "operation did not record a generated asset"
    return asset, VideoAsset(g, generated.identifier), op


class TestTranscodeVideo:
    def test_transcodes_to_requested_encoder(self, tmp_path):
        _, out, _ = _run(MP4, tmp_path, video_encoder="libx264", crf=35)

        out_file = Path(str(out.file_path))
        assert out_file.suffix == ".mp4"
        codecs = [
            s["codec_name"] for s in _streams(out_file) if s["codec_type"] == "video"
        ]
        assert codecs == ["h264"]

    def test_output_registered_as_video_asset(self, tmp_path):
        _, out, _ = _run(MP4, tmp_path, video_encoder="libx264", crf=35)

        assert out.media_type.startswith("video/")
        assert out.has_video()

    def test_copies_audio_stream(self, tmp_path):
        src, out, _ = _run(MP4, tmp_path, video_encoder="libx264", crf=35)

        assert src.has_audio()
        assert any(
            s["codec_type"] == "audio" for s in _streams(Path(str(out.file_path)))
        )

    def test_records_provenance(self, tmp_path):
        src, out, op = _run(MP4, tmp_path, video_encoder="libx264", crf=35)

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]

    def test_input_without_video_stream_raises(self, tmp_path):
        g = Graph()
        asset = load_asset_from_file(g, MP3)
        op = TranscodeVideo.new(g, URIRef(f"operation://{uuid4()}"))
        op.video_encoder = "libx264"
        op.crf = 35
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(tmp_path)

    def test_mutate_without_input_raises(self, tmp_path):
        g = Graph()
        op = TranscodeVideo.new(g, URIRef(f"operation://{uuid4()}"))
        op.video_encoder = "libx264"
        op.crf = 35

        with pytest.raises(ValueError):
            op.mutate(tmp_path)
