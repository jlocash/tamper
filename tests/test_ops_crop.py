"""Behavioral tests for tamper.ops.crop.

Crop is split by media: Crop extracts a rectangular region from an image
(via OpenCV); Crop crops a video (via ffmpeg's crop filter, re-encoding the
cropped video stream and copying any audio stream through unchanged).
"""

from pathlib import Path

import ffmpeg
import pytest
from rdflib import PROV, Graph

from tamper.core import ImageAsset, VideoAsset, load_asset_from_file
from tamper.core.operation import OperationURI
from tamper.ops import Crop

TEST_MEDIA = Path(__file__).parent / "test-media"
JPG = TEST_MEDIA / "images" / "file_example_JPG_100kB.jpg"
MP4 = TEST_MEDIA / "video" / "file_example_MP4_480_1_5MG.mp4"


def _streams(path: Path) -> list[dict]:
    return ffmpeg.probe(str(path))["streams"]


def _run(op_cls, src: Path, out_dir: Path, asset_cls, **params):
    """Run ``op_cls`` over ``src``, returning (input asset, output asset, op)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    g = Graph()
    asset = load_asset_from_file(g, src)
    op = op_cls.new(g, OperationURI())
    for name, value in params.items():
        setattr(op, name, value)
    op.used(asset.identifier)
    op.mutate(out_dir)

    generated = next(op.get_generated(), None)
    assert generated is not None, "operation did not record a generated asset"
    return asset, asset_cls(g, generated.identifier), op


class TestCropImage:
    def test_output_has_crop_dimensions(self, tmp_path):
        _, out, _ = _run(
            Crop, JPG, tmp_path, ImageAsset, x=10, y=10, width=50, height=40
        )
        assert out.width == 50
        assert out.height == 40

    def test_records_provenance(self, tmp_path):
        src, out, op = _run(
            Crop, JPG, tmp_path, ImageAsset, x=0, y=0, width=50, height=40
        )

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]
        assert out.identifier != src.identifier

    def test_writes_content_addressed_file_to_out_dir(self, tmp_path):
        _, out, _ = _run(Crop, JPG, tmp_path, ImageAsset, x=0, y=0, width=50, height=40)

        out_file = Path(str(out.file_path))
        assert out_file.exists()
        assert out_file.parent == tmp_path
        assert out_file.stem == out.checksum.removeprefix("sha256:")
        assert out_file.stat().st_size > 0

    def test_region_exceeding_bounds_raises(self, tmp_path):
        g = Graph()
        asset = load_asset_from_file(g, JPG)
        op = Crop.new(g, OperationURI())
        op.x = 0
        op.y = 0
        op.width = asset.width + 1
        op.height = asset.height
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(tmp_path)

    def test_mutate_without_input_raises(self, tmp_path):
        g = Graph()
        op = Crop.new(g, OperationURI())
        op.x = 0
        op.y = 0
        op.width = 50
        op.height = 40

        with pytest.raises(ValueError):
            op.mutate(tmp_path)


class TestCropVideo:
    def test_output_has_crop_dimensions(self, tmp_path):
        _, out, _ = _run(
            Crop,
            MP4,
            tmp_path,
            VideoAsset,
            x=0,
            y=0,
            width=160,
            height=120,
        )

        video = next(
            s for s in _streams(Path(str(out.file_path))) if s["codec_type"] == "video"
        )
        assert video["width"] == 160
        assert video["height"] == 120

    def test_copies_audio_stream(self, tmp_path):
        src, out, _ = _run(
            Crop,
            MP4,
            tmp_path,
            VideoAsset,
            x=0,
            y=0,
            width=160,
            height=120,
        )

        assert src.has_audio()
        assert any(
            s["codec_type"] == "audio" for s in _streams(Path(str(out.file_path)))
        )

    def test_records_provenance(self, tmp_path):
        src, out, op = _run(
            Crop,
            MP4,
            tmp_path,
            VideoAsset,
            x=0,
            y=0,
            width=160,
            height=120,
        )

        assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
        assert op.get_used() == [src.identifier]
