"""Behavioral tests for tamper.ops.audio operations."""

from pathlib import Path
from uuid import uuid4

import ffmpeg
import pytest
from rdflib import PROV, Graph, URIRef

from tamper.core import MediaAsset, load_asset_from_file
from tamper.ops.audio import ResampleAudio, TranscodeAudio

TEST_MEDIA = Path(__file__).parent / "test-media"
WAV = TEST_MEDIA / "audio" / "file_example_WAV_1MG.wav"
MP3 = TEST_MEDIA / "audio" / "file_example_MP3_700KB.mp3"
PNG = TEST_MEDIA / "images" / "file_example_PNG_500kB.png"


def _audio_stream(path: Path) -> dict:
    streams = ffmpeg.probe(str(path))["streams"]
    return next(s for s in streams if s["codec_type"] == "audio")


def _run(op_cls, src: Path, out_dir: Path, **params):
    """Run ``op_cls`` over ``src``, returning (input asset, output asset, op)."""
    g = Graph()
    asset = load_asset_from_file(g, src)
    op = op_cls.new(g, URIRef(f"operation://{uuid4()}"))
    for name, value in params.items():
        setattr(op, name, value)
    op.used(asset.identifier)
    op.mutate(out_dir)

    generated = next(op.get_generated(), None)
    assert generated is not None, "operation did not record a generated asset"
    return asset, MediaAsset(g, generated.identifier), op


class TestResampleAudio:
    def test_changes_sample_rate(self, tmp_path):
        assert int(_audio_stream(WAV)["sample_rate"]) == 44100

        _, out, _ = _run(ResampleAudio, WAV, tmp_path, target_sample_rate=8000)
        assert int(_audio_stream(Path(str(out.file_path)))["sample_rate"]) == 8000

    def test_records_provenance(self, tmp_path):
        src, out, op = _run(ResampleAudio, WAV, tmp_path, target_sample_rate=8000)

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]
        assert out.media_type.startswith("audio/")

    def test_input_without_audio_stream_raises(self, tmp_path):
        g = Graph()
        asset = load_asset_from_file(g, PNG)
        op = ResampleAudio.new(g, URIRef(f"operation://{uuid4()}"))
        op.target_sample_rate = 8000
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(tmp_path)

    def test_mutate_without_input_raises(self, tmp_path):
        g = Graph()
        op = ResampleAudio.new(g, URIRef(f"operation://{uuid4()}"))
        op.target_sample_rate = 8000

        with pytest.raises(ValueError):
            op.mutate(tmp_path)


class TestTranscodeAudio:
    def test_transcodes_to_requested_encoder(self, tmp_path):
        _, out, _ = _run(
            TranscodeAudio,
            WAV,
            tmp_path,
            audio_encoder="libmp3lame",
            target_bitrate=64000,
        )

        out_file = Path(str(out.file_path))
        assert out_file.suffix == ".mp3"
        assert _audio_stream(out_file)["codec_name"] == "mp3"

    def test_applies_target_bitrate(self, tmp_path):
        _, out, _ = _run(
            TranscodeAudio,
            WAV,
            tmp_path,
            audio_encoder="libmp3lame",
            target_bitrate=64000,
        )

        bit_rate = int(_audio_stream(Path(str(out.file_path)))["bit_rate"])
        assert abs(bit_rate - 64000) / 64000 < 0.2

    def test_records_provenance(self, tmp_path):
        src, out, op = _run(
            TranscodeAudio,
            MP3,
            tmp_path,
            audio_encoder="libmp3lame",
            target_bitrate=64000,
        )

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]

    def test_mutate_without_input_raises(self, tmp_path):
        g = Graph()
        op = TranscodeAudio.new(g, URIRef(f"operation://{uuid4()}"))
        op.audio_encoder = "libmp3lame"
        op.target_bitrate = 64000

        with pytest.raises(ValueError):
            op.mutate(tmp_path)
