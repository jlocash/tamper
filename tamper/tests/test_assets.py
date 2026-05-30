import hashlib
from pathlib import Path

import pytest
from rdflib import Graph, RDF

from tamper.assets import build_asset_from_file, get_file_sha256, _get_frame_rate
from tamper.vocabularies import TAMPER

TEST_MEDIA = Path(__file__).parent / "test-media"
IMAGES = TEST_MEDIA / "images"
AUDIO = TEST_MEDIA / "audio"
VIDEO = TEST_MEDIA / "video"


class TestGetFileSha256:
    def test_returns_64_char_hex(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        result = get_file_sha256(f)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_hashlib(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        assert get_file_sha256(f) == hashlib.sha256(b"hello world").hexdigest()

    def test_consistent(self):
        path = IMAGES / "file_example_JPG_100kB.jpg"
        assert get_file_sha256(path) == get_file_sha256(path)

    def test_different_files_differ(self):
        a = get_file_sha256(IMAGES / "file_example_JPG_100kB.jpg")
        b = get_file_sha256(IMAGES / "file_example_PNG_500kB.png")
        assert a != b


class TestGetFrameRate:
    def test_simple_integer_rate(self):
        assert _get_frame_rate({"r_frame_rate": "30/1"}) == 30.0

    def test_ntsc_fractional_rate(self):
        result = _get_frame_rate({"r_frame_rate": "30000/1001"})
        assert abs(result - 29.97002997) < 0.0001

    def test_fallback_to_avg_when_r_is_zero(self):
        assert _get_frame_rate({"r_frame_rate": "0/0", "avg_frame_rate": "25/1"}) == 25.0

    def test_avg_frame_rate_when_r_absent(self):
        assert _get_frame_rate({"avg_frame_rate": "24/1"}) == 24.0

    def test_empty_stream_returns_none(self):
        assert _get_frame_rate({}) is None

    def test_both_zero_returns_none(self):
        assert _get_frame_rate({"r_frame_rate": "0/0", "avg_frame_rate": "0/0"}) is None

    def test_zero_denominator_returns_none(self):
        assert _get_frame_rate({"r_frame_rate": "30/0"}) is None


def _objects(g, subject, predicate):
    return list(g.objects(subject, predicate))


def _value(g, subject, predicate):
    vals = _objects(g, subject, predicate)
    return vals[0] if vals else None


class TestImageAsset:
    @pytest.fixture(scope="class")
    def jpg(self):
        g = Graph()
        uri = build_asset_from_file(g, IMAGES / "file_example_JPG_100kB.jpg")
        return g, uri

    def test_uri_starts_with_asset_scheme(self, jpg):
        _, uri = jpg
        assert str(uri).startswith("asset://")

    def test_uri_encodes_sha256(self, jpg):
        g, uri = jpg
        checksum = get_file_sha256(IMAGES / "file_example_JPG_100kB.jpg")
        assert str(uri) == f"asset://{checksum}"

    def test_rdftype_image_asset(self, jpg):
        g, uri = jpg
        assert TAMPER.ImageAsset in _objects(g, uri, RDF.type)

    def test_media_type_jpeg(self, jpg):
        g, uri = jpg
        assert str(_value(g, uri, TAMPER.mediaType)) == "image/jpeg"

    def test_checksum_format(self, jpg):
        g, uri = jpg
        checksum = str(_value(g, uri, TAMPER.checksum))
        assert checksum.startswith("sha256:")
        assert len(checksum) == len("sha256:") + 64

    def test_width_positive(self, jpg):
        g, uri = jpg
        assert int(_value(g, uri, TAMPER.width)) > 0

    def test_height_positive(self, jpg):
        g, uri = jpg
        assert int(_value(g, uri, TAMPER.height)) > 0

    def test_pixel_format_present(self, jpg):
        g, uri = jpg
        assert _value(g, uri, TAMPER.pixelFormat) is not None

    def test_png_classified_correctly(self):
        g = Graph()
        uri = build_asset_from_file(g, IMAGES / "file_example_PNG_500kB.png")
        assert TAMPER.ImageAsset in _objects(g, uri, RDF.type)
        assert str(_value(g, uri, TAMPER.mediaType)) == "image/png"

    def test_webp_classified_correctly(self):
        g = Graph()
        uri = build_asset_from_file(g, IMAGES / "file_example_WEBP_50kB.webp")
        assert TAMPER.ImageAsset in _objects(g, uri, RDF.type)
        assert str(_value(g, uri, TAMPER.mediaType)) == "image/webp"

    def test_gif_classified_correctly(self):
        g = Graph()
        uri = build_asset_from_file(g, IMAGES / "file_example_GIF_500kB.gif")
        assert TAMPER.ImageAsset in _objects(g, uri, RDF.type)
        assert str(_value(g, uri, TAMPER.mediaType)) == "image/gif"


class TestAudioAsset:
    @pytest.fixture(scope="class")
    def mp3(self):
        g = Graph()
        uri = build_asset_from_file(g, AUDIO / "file_example_MP3_700KB.mp3")
        return g, uri

    def test_rdftype_audio_asset(self, mp3):
        g, uri = mp3
        assert TAMPER.AudioAsset in _objects(g, uri, RDF.type)

    def test_media_type_starts_with_audio(self, mp3):
        g, uri = mp3
        assert str(_value(g, uri, TAMPER.mediaType)).startswith("audio/")

    def test_checksum_format(self, mp3):
        g, uri = mp3
        checksum = str(_value(g, uri, TAMPER.checksum))
        assert checksum.startswith("sha256:")

    def test_has_at_least_one_stream(self, mp3):
        g, uri = mp3
        assert len(_objects(g, uri, TAMPER.hasStream)) > 0

    def test_stream_typed_as_audio_stream(self, mp3):
        g, uri = mp3
        streams = _objects(g, uri, TAMPER.hasStream)
        all_types = [t for s in streams for t in _objects(g, s, RDF.type)]
        assert TAMPER.AudioStream in all_types

    def test_audio_stream_has_codec(self, mp3):
        g, uri = mp3
        streams = _objects(g, uri, TAMPER.hasStream)
        audio_streams = [s for s in streams if (s, RDF.type, TAMPER.AudioStream) in g]
        for s in audio_streams:
            assert _value(g, s, TAMPER.codec) is not None

    def test_wav_classified_correctly(self):
        g = Graph()
        uri = build_asset_from_file(g, AUDIO / "file_example_WAV_1MG.wav")
        assert TAMPER.AudioAsset in _objects(g, uri, RDF.type)


class TestVideoAsset:
    @pytest.fixture(scope="class")
    def mp4(self):
        g = Graph()
        uri = build_asset_from_file(g, VIDEO / "file_example_MP4_480_1_5MG.mp4")
        return g, uri

    def test_rdftype_video_asset(self, mp4):
        g, uri = mp4
        assert TAMPER.VideoAsset in _objects(g, uri, RDF.type)

    def test_media_type_starts_with_video(self, mp4):
        g, uri = mp4
        assert str(_value(g, uri, TAMPER.mediaType)).startswith("video/")

    def test_uri_encodes_sha256(self, mp4):
        g, uri = mp4
        checksum = get_file_sha256(VIDEO / "file_example_MP4_480_1_5MG.mp4")
        assert str(uri) == f"asset://{checksum}"

    def test_has_video_stream(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        all_types = [t for s in streams for t in _objects(g, s, RDF.type)]
        assert TAMPER.VideoStream in all_types

    def test_has_audio_stream(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        all_types = [t for s in streams for t in _objects(g, s, RDF.type)]
        assert TAMPER.AudioStream in all_types

    def test_video_stream_has_dimensions(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        video_streams = [s for s in streams if (s, RDF.type, TAMPER.VideoStream) in g]
        assert len(video_streams) > 0
        for vs in video_streams:
            assert int(_value(g, vs, TAMPER.width)) > 0
            assert int(_value(g, vs, TAMPER.height)) > 0

    def test_video_stream_has_frame_rate(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        video_streams = [s for s in streams if (s, RDF.type, TAMPER.VideoStream) in g]
        for vs in video_streams:
            frame_rate = _value(g, vs, TAMPER.frameRate)
            assert frame_rate is not None
            assert float(frame_rate) > 0

    def test_video_stream_has_codec(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        video_streams = [s for s in streams if (s, RDF.type, TAMPER.VideoStream) in g]
        for vs in video_streams:
            assert _value(g, vs, TAMPER.codec) is not None

    def test_stream_has_index(self, mp4):
        g, uri = mp4
        streams = _objects(g, uri, TAMPER.hasStream)
        for s in streams:
            assert _value(g, s, TAMPER.streamIndex) is not None

    def test_webm_classified_correctly(self):
        g = Graph()
        uri = build_asset_from_file(g, VIDEO / "file_example_WEBM_480_900KB.webm")
        assert TAMPER.VideoAsset in _objects(g, uri, RDF.type)
