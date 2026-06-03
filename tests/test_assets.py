import hashlib
from pathlib import Path

import pytest
from rdflib import Graph, RDF

from tamper.assets import (
    AudioAsset,
    AudioStream,
    VideoAsset,
    VideoStream,
    load_asset_from_file,
    get_file_sha256,
    _get_frame_rate,
)
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
        assert (
            _get_frame_rate({"r_frame_rate": "0/0", "avg_frame_rate": "25/1"}) == 25.0
        )

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
        asset = load_asset_from_file(g, IMAGES / "file_example_JPG_100kB.jpg")
        return asset

    def test_uri_starts_with_asset_scheme(self, jpg):
        assert jpg.subject.startswith("asset://")

    def test_uri_encodes_sha256(self, jpg):
        checksum = get_file_sha256(IMAGES / "file_example_JPG_100kB.jpg")
        assert str(jpg.subject) == f"asset://{checksum}"

    def test_rdftype_image_asset(self, jpg):
        assert TAMPER.ImageAsset in _objects(jpg.graph, jpg.subject, RDF.type)

    def test_media_type_jpeg(self, jpg):
        assert jpg.media_type == "image/jpeg"

    def test_checksum_format(self, jpg):
        checksum = jpg.checksum
        assert checksum.startswith("sha256:")
        assert len(checksum) == len("sha256:") + 64

    def test_width_positive(self, jpg):
        assert jpg.width > 0

    def test_height_positive(self, jpg):
        assert jpg.height > 0

    def test_pixel_format_present(self, jpg):
        assert jpg.pixel_format is not None

    def test_png_classified_correctly(self):
        g = Graph()
        img = load_asset_from_file(g, IMAGES / "file_example_PNG_500kB.png")
        assert TAMPER.ImageAsset in _objects(g, img.subject, RDF.type)
        assert img.media_type == "image/png"

    def test_webp_classified_correctly(self):
        g = Graph()
        img = load_asset_from_file(g, IMAGES / "file_example_WEBP_50kB.webp")
        assert TAMPER.ImageAsset in _objects(g, img.subject, RDF.type)
        assert str(_value(g, img.subject, TAMPER.mediaType)) == "image/webp"

    def test_gif_classified_correctly(self):
        g = Graph()
        img = load_asset_from_file(g, IMAGES / "file_example_GIF_500kB.gif")
        assert TAMPER.ImageAsset in _objects(g, img.subject, RDF.type)
        assert str(_value(g, img.subject, TAMPER.mediaType)) == "image/gif"


class TestAudioAsset:
    @pytest.fixture(scope="class")
    def mp3(self):
        g = Graph()
        asset = load_asset_from_file(g, AUDIO / "file_example_MP3_700KB.mp3")
        return asset

    def test_rdftype_audio_asset(self, mp3: AudioAsset):
        assert TAMPER.AudioAsset in _objects(mp3.graph, mp3.subject, RDF.type)

    def test_media_type_starts_with_audio(self, mp3: AudioAsset):
        assert mp3.media_type.startswith("audio/")

    def test_checksum_format(self, mp3: AudioAsset):
        assert mp3.checksum.startswith("sha256:")

    def test_has_at_least_one_stream(self, mp3: AudioAsset):
        assert len(mp3.streams) > 0

    def test_stream_typed_as_audio_stream(self, mp3: AudioAsset):
        assert any(s for s in mp3.streams if isinstance(s, AudioStream))

    def test_audio_stream_has_codec(self, mp3: AudioAsset):
        audio_streams = [s for s in mp3.streams if isinstance(s, AudioStream)]
        for s in audio_streams:
            assert s.codec is not None

    def test_wav_classified_correctly(self):
        g = Graph()
        asset = load_asset_from_file(g, AUDIO / "file_example_WAV_1MG.wav")
        assert isinstance(asset, AudioAsset)


class TestVideoAsset:
    @pytest.fixture(scope="class")
    def mp4(self):
        g = Graph()
        asset = load_asset_from_file(g, VIDEO / "file_example_MP4_480_1_5MG.mp4")
        return asset

    def test_rdftype_video_asset(self, mp4: VideoAsset):
        assert TAMPER.VideoAsset in _objects(mp4.graph, mp4.subject, RDF.type)

    def test_media_type_starts_with_video(self, mp4: VideoAsset):
        assert mp4.media_type.startswith("video/")

    def test_uri_encodes_sha256(self, mp4: VideoAsset):
        checksum = get_file_sha256(VIDEO / "file_example_MP4_480_1_5MG.mp4")
        assert str(mp4.subject) == f"asset://{checksum}"

    def test_has_video_stream(self, mp4: VideoAsset):
        assert any(s for s in mp4.streams if isinstance(s, VideoStream))

    def test_has_audio_stream(self, mp4: VideoAsset):
        assert any(s for s in mp4.streams if isinstance(s, AudioStream))

    def test_video_stream_has_dimensions(self, mp4: VideoAsset):
        video_streams = [s for s in mp4.streams if isinstance(s, VideoStream)]
        assert len(video_streams) > 0
        for vs in video_streams:
            assert vs.width > 0
            assert vs.height > 0

    def test_video_stream_has_frame_rate(self, mp4: VideoAsset):
        video_streams = [s for s in mp4.streams if isinstance(s, VideoStream)]
        assert len(video_streams) > 0
        for vs in video_streams:
            frame_rate = vs.frame_rate
            assert frame_rate is not None
            assert frame_rate > 0

    def test_video_stream_has_codec(self, mp4: VideoAsset):
        video_streams = [s for s in mp4.streams if isinstance(s, VideoStream)]
        assert len(video_streams) > 0
        for vs in video_streams:
            assert vs.codec is not None

    def test_stream_has_index(self, mp4: VideoAsset):
        for s in mp4.streams:
            assert s.stream_index is not None

    def test_webm_classified_correctly(self):
        g = Graph()
        asset = load_asset_from_file(g, VIDEO / "file_example_WEBM_480_900KB.webm")
        assert isinstance(asset, VideoAsset)
