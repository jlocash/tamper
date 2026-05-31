"""Tests for tamper.ops.image — image operation classes."""

from pathlib import Path

import cv2
import pytest
from rdflib import Graph, RDF, Literal, XSD

from tamper.app.kg.local import check_consistency
from tamper.ops.image import (
    AddGaussianNoise,
    CompressJPEG,
    GaussianBlur,
    MedianFilter,
    Resize,
)
from tamper.vocabularies import TAMPER

TEST_MEDIA = Path(__file__).parent / "test-media"
IMAGES = TEST_MEDIA / "images"

# A small, stable test image used across transform tests.
_JPG = IMAGES / "file_example_JPG_100kB.jpg"


# ---------------------------------------------------------------------------
# CompressJPEG
# ---------------------------------------------------------------------------


class TestCompressJPEG:
    def test_valid_construction(self):
        op = CompressJPEG(quality_factor=80)
        assert op.quality_factor == 80

    def test_boundary_zero(self):
        op = CompressJPEG(quality_factor=0)
        assert op.quality_factor == 0

    def test_boundary_hundred(self):
        op = CompressJPEG(quality_factor=100)
        assert op.quality_factor == 100

    def test_quality_below_range_raises(self):
        with pytest.raises(ValueError, match="quality_factor"):
            CompressJPEG(quality_factor=-1)

    def test_quality_above_range_raises(self):
        with pytest.raises(ValueError, match="quality_factor"):
            CompressJPEG(quality_factor=101)

    def test_subject_uri_is_unique(self):
        a = CompressJPEG(50)
        b = CompressJPEG(50)
        assert a.subject != b.subject

    def test_graph_rdftype(self):
        op = CompressJPEG(75)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.CompressJPEG) in g

    def test_graph_quality_factor_literal(self):
        op = CompressJPEG(75)
        g = op.graph()
        val = g.value(op.subject, TAMPER.qualityFactor)
        assert val is not None
        assert int(val) == 75

    def test_copy_from_graph_roundtrip(self):
        original = CompressJPEG(60)
        g = original.graph()
        restored = CompressJPEG.copy_from_graph(g, original.subject)
        assert restored.quality_factor == 60

    def test_copy_from_graph_missing_quality_raises(self):
        g = Graph()
        from rdflib import URIRef
        subject = URIRef("operation://test-subject")
        with pytest.raises(ValueError, match="qualityFactor"):
            CompressJPEG.copy_from_graph(g, subject)

    def test_transform_produces_jpeg_file(self, tmp_path):
        op = CompressJPEG(85)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        assert out.exists()
        assert out.stat().st_size > 0
        # verify it is a valid image
        img = cv2.imread(str(out))
        assert img is not None

    def test_transform_output_is_valid_jpeg(self, tmp_path):
        op = CompressJPEG(50)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        img = cv2.imread(str(out))
        assert img is not None
        assert img.ndim == 3


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------


class TestResize:
    def test_valid_construction(self):
        op = Resize(width=320, height=240)
        assert op.width == 320
        assert op.height == 240
        assert op.interpolation == "linear"

    def test_custom_interpolation(self):
        op = Resize(640, 480, interpolation="cubic")
        assert op.interpolation == "cubic"

    def test_all_valid_interpolations(self):
        for method in ("nearest", "linear", "cubic", "area", "lanczos4"):
            op = Resize(100, 100, interpolation=method)
            assert op.interpolation == method

    def test_invalid_interpolation_raises(self):
        with pytest.raises(ValueError, match="interpolation"):
            Resize(100, 100, interpolation="bicubic")

    def test_graph_rdftype(self):
        op = Resize(100, 200)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.Resize) in g

    def test_graph_width_height_literals(self):
        op = Resize(320, 240)
        g = op.graph()
        assert int(g.value(op.subject, TAMPER.targetWidth)) == 320
        assert int(g.value(op.subject, TAMPER.targetHeight)) == 240

    def test_graph_interpolation_literal(self):
        op = Resize(100, 100, interpolation="area")
        g = op.graph()
        assert str(g.value(op.subject, TAMPER.interpolation)) == "area"

    def test_copy_from_graph_roundtrip(self):
        original = Resize(128, 64, interpolation="nearest")
        g = original.graph()
        restored = Resize.copy_from_graph(g, original.subject)
        assert restored.width == 128
        assert restored.height == 64
        assert restored.interpolation == "nearest"

    def test_copy_from_graph_missing_width_raises(self):
        g = Graph()
        from rdflib import URIRef
        subject = URIRef("operation://test")
        with pytest.raises(ValueError, match="targetWidth"):
            Resize.copy_from_graph(g, subject)

    def test_copy_from_graph_missing_height_raises(self):
        from rdflib import URIRef
        subject = URIRef("operation://test")
        g = Graph()
        g.add((subject, TAMPER.targetWidth, Literal(100, datatype=XSD.positiveInteger)))
        with pytest.raises(ValueError, match="targetHeight"):
            Resize.copy_from_graph(g, subject)

    def test_copy_from_graph_missing_interpolation_raises(self):
        from rdflib import URIRef
        subject = URIRef("operation://test")
        g = Graph()
        g.add((subject, TAMPER.targetWidth, Literal(100, datatype=XSD.positiveInteger)))
        g.add((subject, TAMPER.targetHeight, Literal(100, datatype=XSD.positiveInteger)))
        with pytest.raises(ValueError, match="interpolation"):
            Resize.copy_from_graph(g, subject)

    def test_transform_produces_correct_dimensions(self, tmp_path):
        op = Resize(width=50, height=30)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        img = cv2.imread(str(out))
        assert img is not None
        h, w = img.shape[:2]
        assert w == 50
        assert h == 30


# ---------------------------------------------------------------------------
# MedianFilter
# ---------------------------------------------------------------------------


class TestMedianFilter:
    def test_valid_construction(self):
        op = MedianFilter(kernel_size=3)
        assert op.kernel_size == 3

    def test_larger_odd_kernel(self):
        op = MedianFilter(kernel_size=9)
        assert op.kernel_size == 9

    def test_even_kernel_raises(self):
        with pytest.raises(ValueError, match="odd"):
            MedianFilter(kernel_size=4)

    def test_kernel_less_than_3_raises(self):
        with pytest.raises(ValueError, match="odd"):
            MedianFilter(kernel_size=1)

    def test_graph_rdftype(self):
        op = MedianFilter(3)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.MedianFilter) in g

    def test_graph_kernel_size_literal(self):
        op = MedianFilter(5)
        g = op.graph()
        assert int(g.value(op.subject, TAMPER.kernelSize)) == 5

    def test_copy_from_graph_roundtrip(self):
        original = MedianFilter(7)
        g = original.graph()
        restored = MedianFilter.copy_from_graph(g, original.subject)
        assert restored.kernel_size == 7

    def test_copy_from_graph_missing_kernel_raises(self):
        from rdflib import URIRef
        g = Graph()
        subject = URIRef("operation://test")
        with pytest.raises(ValueError, match="kernelSize"):
            MedianFilter.copy_from_graph(g, subject)

    def test_transform_preserves_shape(self, tmp_path):
        op = MedianFilter(3)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        original_img = cv2.imread(str(_JPG))
        result_img = cv2.imread(str(out))
        assert result_img is not None
        assert result_img.shape == original_img.shape


# ---------------------------------------------------------------------------
# GaussianBlur
# ---------------------------------------------------------------------------


class TestGaussianBlur:
    def test_valid_construction(self):
        op = GaussianBlur(kernel_size=3)
        assert op.kernel_size == 3
        assert op.sigma == 0.0

    def test_custom_sigma(self):
        op = GaussianBlur(kernel_size=5, sigma=1.5)
        assert op.sigma == 1.5

    def test_even_kernel_raises(self):
        with pytest.raises(ValueError, match="odd"):
            GaussianBlur(kernel_size=4)

    def test_zero_kernel_raises(self):
        with pytest.raises(ValueError, match="odd"):
            GaussianBlur(kernel_size=0)

    def test_graph_rdftype(self):
        op = GaussianBlur(3)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.GaussianBlur) in g

    def test_graph_kernel_and_sigma(self):
        op = GaussianBlur(kernel_size=5, sigma=2.0)
        g = op.graph()
        assert int(g.value(op.subject, TAMPER.kernelSize)) == 5
        assert abs(float(g.value(op.subject, TAMPER.blurSigma)) - 2.0) < 1e-6

    def test_copy_from_graph_roundtrip(self):
        original = GaussianBlur(kernel_size=7, sigma=0.5)
        g = original.graph()
        restored = GaussianBlur.copy_from_graph(g, original.subject)
        assert restored.kernel_size == 7
        assert abs(restored.sigma - 0.5) < 1e-6

    def test_copy_from_graph_missing_kernel_raises(self):
        from rdflib import URIRef
        g = Graph()
        subject = URIRef("operation://test")
        with pytest.raises(ValueError, match="kernelSize"):
            GaussianBlur.copy_from_graph(g, subject)

    def test_copy_from_graph_missing_sigma_raises(self):
        from rdflib import URIRef
        subject = URIRef("operation://test")
        g = Graph()
        g.add((subject, TAMPER.kernelSize, Literal(3, datatype=XSD.positiveInteger)))
        with pytest.raises(ValueError, match="blurSigma"):
            GaussianBlur.copy_from_graph(g, subject)

    def test_transform_preserves_shape(self, tmp_path):
        op = GaussianBlur(kernel_size=3, sigma=1.0)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        original_img = cv2.imread(str(_JPG))
        result_img = cv2.imread(str(out))
        assert result_img is not None
        assert result_img.shape == original_img.shape


# ---------------------------------------------------------------------------
# AddGaussianNoise
# ---------------------------------------------------------------------------


class TestAddGaussianNoise:
    def test_valid_construction(self):
        op = AddGaussianNoise(mean=0.0, std=1.0)
        assert op.mean == 0.0
        assert op.std == 1.0

    def test_zero_std_allowed(self):
        op = AddGaussianNoise(mean=0.0, std=0.0)
        assert op.std == 0.0

    def test_negative_mean_allowed(self):
        op = AddGaussianNoise(mean=-5.0, std=1.0)
        assert op.mean == -5.0

    def test_negative_std_raises(self):
        with pytest.raises(ValueError, match="std"):
            AddGaussianNoise(mean=0.0, std=-0.1)

    def test_graph_rdftype(self):
        op = AddGaussianNoise(0.0, 1.0)
        g = op.graph()
        assert (op.subject, RDF.type, TAMPER.AddGaussianNoise) in g

    def test_graph_mean_and_std(self):
        op = AddGaussianNoise(mean=1.5, std=3.0)
        g = op.graph()
        assert abs(float(g.value(op.subject, TAMPER.gaussianMean)) - 1.5) < 1e-6
        assert abs(float(g.value(op.subject, TAMPER.gaussianStd)) - 3.0) < 1e-6

    def test_copy_from_graph_roundtrip(self):
        original = AddGaussianNoise(mean=2.0, std=0.5)
        g = original.graph()
        restored = AddGaussianNoise.copy_from_graph(g, original.subject)
        assert abs(restored.mean - 2.0) < 1e-6
        assert abs(restored.std - 0.5) < 1e-6

    def test_copy_from_graph_missing_mean_raises(self):
        from rdflib import URIRef
        g = Graph()
        subject = URIRef("operation://test")
        with pytest.raises(ValueError, match="gaussianMean"):
            AddGaussianNoise.copy_from_graph(g, subject)

    def test_copy_from_graph_missing_std_raises(self):
        from rdflib import URIRef
        subject = URIRef("operation://test")
        g = Graph()
        g.add((subject, TAMPER.gaussianMean, Literal(0.0, datatype=XSD.decimal)))
        with pytest.raises(ValueError, match="gaussianStd"):
            AddGaussianNoise.copy_from_graph(g, subject)

    def test_transform_preserves_shape(self, tmp_path):
        op = AddGaussianNoise(mean=0.0, std=5.0)
        out = tmp_path / "out.jpg"
        op.transform(_JPG, out)
        original_img = cv2.imread(str(_JPG))
        result_img = cv2.imread(str(out))
        assert result_img is not None
        assert result_img.shape == original_img.shape


@pytest.mark.parametrize(
    "op",
    [
        CompressJPEG(0),
        CompressJPEG(100),
        Resize(320, 240, interpolation="cubic"),
        MedianFilter(3),
        GaussianBlur(kernel_size=3, sigma=0.0),
        GaussianBlur(kernel_size=5, sigma=1.5),
        AddGaussianNoise(mean=0.0, std=0.0),
        AddGaussianNoise(mean=-2.5, std=3.0),
    ],
    ids=lambda op: type(op).__name__,
)
def test_operation_graph_is_ontology_consistent(op):
    """Serialized image operations must pass the same consistency check the kg runs on insert."""
    check_consistency(op.graph())
