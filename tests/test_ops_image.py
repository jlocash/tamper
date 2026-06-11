"""Behavioral tests for tamper.ops.image operations.

Each operation is exercised through its public interface: instantiate with
``Operation.new``, set parameters via the mapped properties, attach the input
asset with ``used()``, run ``mutate(out_dir)``, and observe the generated
asset recorded in the graph.
"""

from pathlib import Path

import pytest
from rdflib import PROV, Graph

from tamper.core import ImageAsset, load_asset_from_file
from tamper.core.operation import OperationURI
from tamper.ops.image import (
    AddGaussianNoise,
    CompressJPEG,
    CompressWebP,
    CropImage,
    GaussianBlur,
    MedianFilter,
    Resize,
)

IMAGES = Path(__file__).parent / "test-media" / "images"
JPG = IMAGES / "file_example_JPG_100kB.jpg"
PNG = IMAGES / "file_example_PNG_500kB.png"

# One representative parameterization per operation, shared by the
# interface-contract tests below.
OPS = [
    (CompressJPEG, {"quality_factor": 80}),
    (CompressWebP, {"quality_factor": 80}),
    (CropImage, {"x": 0, "y": 0, "width": 50, "height": 40}),
    (Resize, {"width": 64, "height": 48, "interpolation": "linear"}),
    (MedianFilter, {"kernel_size": 3}),
    (GaussianBlur, {"kernel_size": 3, "sigma": 2.0}),
    (AddGaussianNoise, {"mean": 0.0, "std": 25.0, "seed": 42}),
]

OP_IDS = [cls.__name__ for cls, _ in OPS]


def _run(op_cls, src: Path, out_dir: Path, **params):
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
    return asset, ImageAsset(g, generated.identifier), op


# --- Interface contract shared by every image operation --------------------


@pytest.mark.parametrize("op_cls,params", OPS, ids=OP_IDS)
def test_records_provenance(op_cls, params, tmp_path):
    src, out, op = _run(op_cls, JPG, tmp_path, **params)

    assert (out.identifier, PROV.wasGeneratedBy, op.identifier) in op.graph
    assert op.get_used() == [src.identifier]
    assert out.identifier != src.identifier


@pytest.mark.parametrize("op_cls,params", OPS, ids=OP_IDS)
def test_writes_content_addressed_file_to_out_dir(op_cls, params, tmp_path):
    _, out, _ = _run(op_cls, JPG, tmp_path, **params)

    out_file = Path(str(out.file_path))
    assert out_file.exists()
    assert out_file.parent == tmp_path
    assert out_file.stem == out.checksum.removeprefix("sha256:")
    assert out_file.stat().st_size > 0


@pytest.mark.parametrize("op_cls,params", OPS, ids=OP_IDS)
def test_mutate_without_input_raises(op_cls, params, tmp_path):
    g = Graph()
    op = op_cls.new(g, OperationURI())
    for name, value in params.items():
        setattr(op, name, value)

    with pytest.raises(ValueError):
        op.mutate(tmp_path)


# --- Operation-specific behavior --------------------------------------------


class TestCompressJPEG:
    def test_output_is_jpeg(self, tmp_path):
        _, out, _ = _run(CompressJPEG, PNG, tmp_path, quality_factor=80)
        assert out.media_type == "image/jpeg"

    def test_lower_quality_gives_smaller_file(self, tmp_path):
        _, low, _ = _run(CompressJPEG, JPG, tmp_path / "low", quality_factor=10)
        _, high, _ = _run(CompressJPEG, JPG, tmp_path / "high", quality_factor=95)

        low_size = Path(str(low.file_path)).stat().st_size
        high_size = Path(str(high.file_path)).stat().st_size
        assert low_size < high_size


class TestCompressWebP:
    def test_output_is_webp(self, tmp_path):
        _, out, _ = _run(CompressWebP, JPG, tmp_path, quality_factor=80)
        assert out.media_type == "image/webp"


class TestCropImage:
    def test_output_has_crop_dimensions(self, tmp_path):
        _, out, _ = _run(CropImage, JPG, tmp_path, x=10, y=10, width=50, height=40)
        assert out.width == 50
        assert out.height == 40

    def test_region_exceeding_bounds_raises(self, tmp_path):
        g = Graph()
        asset = load_asset_from_file(g, JPG)
        op = CropImage.new(g, OperationURI())
        op.x = 0
        op.y = 0
        op.width = asset.width + 1
        op.height = asset.height
        op.used(asset.identifier)

        with pytest.raises(ValueError):
            op.mutate(tmp_path)


class TestResize:
    def test_output_has_target_dimensions(self, tmp_path):
        _, out, _ = _run(
            Resize, JPG, tmp_path, width=64, height=48, interpolation="linear"
        )
        assert out.width == 64
        assert out.height == 48


class TestMedianFilter:
    def test_preserves_dimensions(self, tmp_path):
        src, out, _ = _run(MedianFilter, JPG, tmp_path, kernel_size=3)
        assert out.width == src.width
        assert out.height == src.height


class TestGaussianBlur:
    def test_preserves_dimensions(self, tmp_path):
        src, out, _ = _run(GaussianBlur, JPG, tmp_path, kernel_size=3, sigma=2.0)
        assert out.width == src.width
        assert out.height == src.height


class TestAddGaussianNoise:
    def test_same_seed_is_reproducible(self, tmp_path):
        _, a, _ = _run(
            AddGaussianNoise, JPG, tmp_path / "a", mean=0.0, std=25.0, seed=42
        )
        _, b, _ = _run(
            AddGaussianNoise, JPG, tmp_path / "b", mean=0.0, std=25.0, seed=42
        )
        assert a.checksum == b.checksum

    def test_different_seeds_differ(self, tmp_path):
        _, a, _ = _run(
            AddGaussianNoise, JPG, tmp_path / "a", mean=0.0, std=25.0, seed=1
        )
        _, b, _ = _run(
            AddGaussianNoise, JPG, tmp_path / "b", mean=0.0, std=25.0, seed=2
        )
        assert a.checksum != b.checksum
