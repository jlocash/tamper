from pathlib import Path

from rdflib import Graph

from tamper.core import ImageAsset, load_asset_from_file
from tamper.core.operation import OperationURI
from tamper.ops import AddGaussianNoise, AddSaltPepperNoise

IMAGES = Path(__file__).parent / "test-media" / "images"
JPG = IMAGES / "file_example_JPG_100kB.jpg"
PNG = IMAGES / "file_example_PNG_500kB.png"

# One representative parameterization per operation, shared by the
# interface-contract tests below.
OPS = [
    (AddGaussianNoise, {"mean": 0.0, "std": 25.0, "seed": 42}),
    (AddSaltPepperNoise, {"amount": 0.05, "salt_ratio": 0.5, "seed": 42}),
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


class TestAddSaltPepperNoise:
    def test_preserves_dimensions(self, tmp_path):
        src, out, _ = _run(
            AddSaltPepperNoise, JPG, tmp_path, amount=0.05, salt_ratio=0.5, seed=42
        )
        assert out.width == src.width
        assert out.height == src.height

    def test_same_seed_is_reproducible(self, tmp_path):
        _, a, _ = _run(
            AddSaltPepperNoise,
            JPG,
            tmp_path / "a",
            amount=0.05,
            salt_ratio=0.5,
            seed=42,
        )
        _, b, _ = _run(
            AddSaltPepperNoise,
            JPG,
            tmp_path / "b",
            amount=0.05,
            salt_ratio=0.5,
            seed=42,
        )
        assert a.checksum == b.checksum

    def test_different_seeds_differ(self, tmp_path):
        _, a, _ = _run(
            AddSaltPepperNoise, JPG, tmp_path / "a", amount=0.05, salt_ratio=0.5, seed=1
        )
        _, b, _ = _run(
            AddSaltPepperNoise, JPG, tmp_path / "b", amount=0.05, salt_ratio=0.5, seed=2
        )
        assert a.checksum != b.checksum
