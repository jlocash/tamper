"""Behavioral tests for tamper.ops.transcode.Transcode.

Transcode subsumes the old TranscodeAudio and TranscodeVideo operations: a
single operation re-encodes the audio stream, the video stream, or both, and
copies any stream it is not given an encoder for.
"""

from pathlib import Path

import ffmpeg
import pytest
from rdflib import PROV, Graph

from tamper.core.assets import StreamContainer
from tamper.core.operation import OperationURI
from tamper.ops import Transcode

TEST_MEDIA = Path(__file__).parent / "test-media"
MP4 = TEST_MEDIA / "video" / "file_example_MP4_480_1_5MG.mp4"
WAV = TEST_MEDIA / "audio" / "file_example_WAV_1MG.wav"
MP3 = TEST_MEDIA / "audio" / "file_example_MP3_700KB.mp3"
PNG = TEST_MEDIA / "images" / "file_example_PNG_500kB.png"


def _streams(path: Path) -> list[dict]:
    return ffmpeg.probe(str(path))["streams"]


def _audio_stream(path: Path) -> dict:
    return next(s for s in _streams(path) if s["codec_type"] == "audio")


def _codecs(path: Path, codec_type: str) -> list[str]:
    return [s["codec_name"] for s in _streams(path) if s["codec_type"] == codec_type]


def _run(src: Path, workspace, load_asset, **params):
    """Run Transcode over ``src``, returning (input asset, output asset, op)."""
    g = Graph()
    asset = load_asset(g, src)
    op = Transcode.new(g, OperationURI())
    for name, value in params.items():
        setattr(op, name, value)
    op.used(asset.identifier)
    op.mutate(workspace)

    generated = next(op.get_generated(), None)
    assert generated is not None, "operation did not record a generated asset"
    return asset, StreamContainer(g, generated.identifier), op


class TestTranscodeAudioStream:
    def test_transcodes_to_requested_encoder(self, workspace, load_asset):
        _, out, _ = _run(
            WAV, workspace, load_asset, audio_encoder="libmp3lame", target_bitrate=64000
        )

        out_file = workspace.cache_path(out)
        assert out_file.suffix == ".mp3"
        assert _audio_stream(out_file)["codec_name"] == "mp3"

    def test_applies_target_bitrate(self, workspace, load_asset):
        _, out, _ = _run(
            WAV, workspace, load_asset, audio_encoder="libmp3lame", target_bitrate=64000
        )

        bit_rate = int(_audio_stream(workspace.cache_path(out))["bit_rate"])
        assert abs(bit_rate - 64000) / 64000 < 0.2

    def test_records_provenance(self, workspace, load_asset):
        src, out, op = _run(
            MP3, workspace, load_asset, audio_encoder="libmp3lame", target_bitrate=64000
        )

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]
        assert out.media_type.startswith("audio/")


class TestTranscodeVideoStream:
    def test_transcodes_to_requested_encoder(self, workspace, load_asset):
        _, out, _ = _run(MP4, workspace, load_asset, video_encoder="libx264", crf=35)

        out_file = workspace.cache_path(out)
        assert out_file.suffix == ".mp4"
        assert _codecs(out_file, "video") == ["h264"]

    def test_output_registered_as_video_asset(self, workspace, load_asset):
        _, out, _ = _run(MP4, workspace, load_asset, video_encoder="libx264", crf=35)

        assert out.media_type.startswith("video/")
        assert out.has_video()

    def test_copies_audio_stream(self, workspace, load_asset):
        src, out, _ = _run(MP4, workspace, load_asset, video_encoder="libx264", crf=35)

        assert src.has_audio()
        assert out.has_audio()

    def test_records_provenance(self, workspace, load_asset):
        src, out, op = _run(MP4, workspace, load_asset, video_encoder="libx264", crf=35)

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]


class TestTranscodeBothStreams:
    def test_reencodes_video_and_audio(self, workspace, load_asset):
        _, out, _ = _run(
            MP4,
            workspace,
            load_asset,
            video_encoder="libx264",
            crf=35,
            audio_encoder="aac",
            target_bitrate=64000,
        )

        out_file = workspace.cache_path(out)
        assert _codecs(out_file, "video") == ["h264"]
        assert _codecs(out_file, "audio") == ["aac"]


class TestTranscodeValidation:
    def test_no_encoder_raises(self, workspace, load_asset):
        g = Graph()
        asset = load_asset(g, MP4)
        op = Transcode.new(g, OperationURI())
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(workspace)

    def test_audio_encoder_on_asset_without_audio_raises(self, workspace, load_asset):
        g = Graph()
        asset = load_asset(g, PNG)
        op = Transcode.new(g, OperationURI())
        op.audio_encoder = "libmp3lame"
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(workspace)

    def test_video_encoder_on_asset_without_video_raises(self, workspace, load_asset):
        g = Graph()
        asset = load_asset(g, MP3)
        op = Transcode.new(g, OperationURI())
        op.video_encoder = "libx264"
        op.crf = 35
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(workspace)

    def test_mutate_without_input_raises(self, workspace, load_asset):
        g = Graph()
        op = Transcode.new(g, OperationURI())
        op.audio_encoder = "libmp3lame"

        with pytest.raises(ValueError):
            op.mutate(workspace)
