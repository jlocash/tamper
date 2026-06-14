from pathlib import Path

import pytest
from rdflib import PROV, Graph

from tamper.core import ImageAsset, load_asset_from_file
from tamper.core.operation import OperationURI
from tamper.ops import (
    Compress,
    AddGaussianBlur,
    MedianFilter,
    Resize,
)

IMAGES = Path(__file__).parent / "test-media" / "images"
JPG = IMAGES / "file_example_JPG_100kB.jpg"
PNG = IMAGES / "file_example_PNG_500kB.png"

# One representative parameterization per operation, shared by the
# interface-contract tests below.
OPS = [
    (Compress, {"quality_factor": 80, "format": "jpeg"}),
    (Compress, {"quality_factor": 80, "format": "webp"}),
    (Resize, {"width": 64, "height": 48, "interpolation": "linear"}),
    (MedianFilter, {"kernel_size": 3}),
    (AddGaussianBlur, {"kernel_size": 3, "sigma": 2.0}),
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


class TestCompress:
    def test_output_is_jpeg(self, tmp_path):
        _, out, _ = _run(Compress, PNG, tmp_path, quality_factor=80, format="jpeg")
        assert out.media_type == "image/jpeg"

    def test_output_is_webp(self, tmp_path):
        _, out, _ = _run(Compress, JPG, tmp_path, quality_factor=80, format="webp")
        assert out.media_type == "image/webp"

    def test_lower_quality_gives_smaller_file(self, tmp_path):
        _, low, _ = _run(
            Compress, JPG, tmp_path / "low", quality_factor=10, format="jpeg"
        )
        _, high, _ = _run(
            Compress, JPG, tmp_path / "high", quality_factor=95, format="jpeg"
        )

        low_size = Path(str(low.file_path)).stat().st_size
        high_size = Path(str(high.file_path)).stat().st_size
        assert low_size < high_size


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
        src, out, _ = _run(AddGaussianBlur, JPG, tmp_path, kernel_size=3, sigma=2.0)
        assert out.width == src.width
        assert out.height == src.height
