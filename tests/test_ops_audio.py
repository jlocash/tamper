from pathlib import Path

import ffmpeg
import pytest

from rdflib import RDF
from tamper.app.kg.local import check_consistency
from tamper.vocabularies import TAMPER

from tamper.ops.audio import ResampleAudio, TranscodeAudio

TEST_MEDIA_DIR = Path(__file__).parent / "test-media" / "audio"


@pytest.fixture
def sample_wav(tmp_path: Path) -> Path:
    src = TEST_MEDIA_DIR / "file_example_WAV_1MG.wav"
    dst = tmp_path / src.name
    dst.write_bytes(src.read_bytes())
    return dst


@pytest.fixture
def sample_mp3(tmp_path: Path) -> Path:
    src = TEST_MEDIA_DIR / "file_example_MP3_700KB.mp3"
    dst = tmp_path / src.name
    dst.write_bytes(src.read_bytes())
    return dst


def audio_stream(path: Path) -> dict:
    streams = ffmpeg.probe(str(path))["streams"]
    return next(s for s in streams if s["codec_type"] == "audio")


# --- ResampleAudio -------------------------------------------------------


class TestResampleAudio:
    def test_produces_output(self, sample_wav: Path, tmp_path: Path):
        out = tmp_path / "out.wav"
        op = ResampleAudio(target_sample_rate=22050)
        op.transform(sample_wav, out)

        assert out.exists()
        assert out.stat().st_size > 0

    def test_changes_sample_rate(self, sample_wav: Path, tmp_path: Path):
        # fixture is 44100 Hz; resample to a clearly different rate
        assert int(audio_stream(sample_wav)["sample_rate"]) == 44100

        out = tmp_path / "out.wav"
        op = ResampleAudio(target_sample_rate=8000)
        op.transform(sample_wav, out)

        assert int(audio_stream(out)["sample_rate"]) == 8000

    def test_invalid_rate_raises(self):
        with pytest.raises(ValueError):
            ResampleAudio(target_sample_rate=0)

    def test_records_parameters_in_graph(self):
        op = ResampleAudio(target_sample_rate=16000)
        g = op.graph()

        assert (op.subject, RDF.type, TAMPER.ResampleAudio) in g
        assert g.value(op.subject, TAMPER.targetSampleRate).toPython() == 16000

    def test_copy_from_graph_round_trips(self):
        op = ResampleAudio(target_sample_rate=16000)
        copy = ResampleAudio.copy_from_graph(op.graph(), op.subject)

        assert copy.target_sample_rate == 16000

    def test_copy_from_graph_missing_property_raises(self):
        op = ResampleAudio(target_sample_rate=16000)
        g = op.graph()
        g.remove((op.subject, TAMPER.targetSampleRate, None))

        with pytest.raises(ValueError):
            ResampleAudio.copy_from_graph(g, op.subject)


# --- TranscodeAudio ------------------------------------------------------


class TestTranscodeAudio:
    def test_produces_output(self, sample_mp3: Path, tmp_path: Path):
        out = tmp_path / "out.mp3"
        op = TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=64000)
        op.transform(sample_mp3, out)

        assert out.exists()
        assert out.stat().st_size > 0

    def test_invalid_bitrate_raises(self):
        with pytest.raises(ValueError):
            TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=0)

    def test_invalid_encoder_raises(self):
        with pytest.raises(ValueError):
            TranscodeAudio(audio_encoder="", target_bitrate=64000)

    def test_records_parameters_in_graph(self):
        op = TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=64000)
        g = op.graph()

        assert (op.subject, RDF.type, TAMPER.TranscodeAudio) in g
        assert g.value(op.subject, TAMPER.audioEncoder).toPython() == "libmp3lame"
        assert g.value(op.subject, TAMPER.targetBitRate).toPython() == 64000

    def test_copy_from_graph_round_trips(self):
        op = TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=64000)
        copy = TranscodeAudio.copy_from_graph(op.graph(), op.subject)

        assert copy.audio_encoder == "libmp3lame"
        assert copy.target_bitrate == 64000

    def test_copy_from_graph_missing_property_raises(self):
        op = TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=64000)
        g = op.graph()
        g.remove((op.subject, TAMPER.audioEncoder, None))

        with pytest.raises(ValueError):
            TranscodeAudio.copy_from_graph(g, op.subject)


@pytest.mark.parametrize(
    "op",
    [
        ResampleAudio(target_sample_rate=8000),
        ResampleAudio(target_sample_rate=44100),
        TranscodeAudio(audio_encoder="libmp3lame", target_bitrate=64000),
        TranscodeAudio(audio_encoder="aac", target_bitrate=128000),
    ],
    ids=lambda op: type(op).__name__,
)
def test_operation_graph_is_ontology_consistent(op):
    """Serialized audio operations must pass the same consistency check the kg runs on insert."""
    check_consistency(op.graph())
