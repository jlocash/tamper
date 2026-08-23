from pathlib import Path

from rdflib import Graph

from tamper.core import ImageAsset
from tamper.core.identifiers import OperationURI
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


def _run(op_cls, src: Path, workspace, load_asset, **params):
    """Run ``op_cls`` over ``src``, returning (input asset, output asset, op)."""
    g = Graph()
    asset = load_asset(g, src)
    op = op_cls.new(g, OperationURI())
    for name, value in params.items():
        setattr(op, name, value)
    op.used(asset.identifier)
    op.mutate(workspace)

    generated = next(op.get_generated(), None)
    assert generated is not None, "operation did not record a generated asset"
    return asset, ImageAsset(g, generated.identifier), op


class TestAddGaussianNoise:
    def test_same_seed_is_reproducible(self, workspace, load_asset):
        _, a, _ = _run(
            AddGaussianNoise, JPG, workspace, load_asset, mean=0.0, std=25.0, seed=42
        )
        _, b, _ = _run(
            AddGaussianNoise, JPG, workspace, load_asset, mean=0.0, std=25.0, seed=42
        )
        assert a.checksum == b.checksum

    def test_different_seeds_differ(self, workspace, load_asset):
        _, a, _ = _run(
            AddGaussianNoise, JPG, workspace, load_asset, mean=0.0, std=25.0, seed=1
        )
        _, b, _ = _run(
            AddGaussianNoise, JPG, workspace, load_asset, mean=0.0, std=25.0, seed=2
        )
        assert a.checksum != b.checksum


class TestAddSaltPepperNoise:
    def test_preserves_dimensions(self, workspace, load_asset):
        src, out, _ = _run(
            AddSaltPepperNoise,
            JPG,
            workspace,
            load_asset,
            amount=0.05,
            salt_ratio=0.5,
            seed=42,
        )
        assert out.width == src.width
        assert out.height == src.height

    def test_same_seed_is_reproducible(self, workspace, load_asset):
        _, a, _ = _run(
            AddSaltPepperNoise,
            JPG,
            workspace,
            load_asset,
            amount=0.05,
            salt_ratio=0.5,
            seed=42,
        )
        _, b, _ = _run(
            AddSaltPepperNoise,
            JPG,
            workspace,
            load_asset,
            amount=0.05,
            salt_ratio=0.5,
            seed=42,
        )
        assert a.checksum == b.checksum

    def test_different_seeds_differ(self, workspace, load_asset):
        _, a, _ = _run(
            AddSaltPepperNoise,
            JPG,
            workspace,
            load_asset,
            amount=0.05,
            salt_ratio=0.5,
            seed=1,
        )
        _, b, _ = _run(
            AddSaltPepperNoise,
            JPG,
            workspace,
            load_asset,
            amount=0.05,
            salt_ratio=0.5,
            seed=2,
        )
        assert a.checksum != b.checksum
