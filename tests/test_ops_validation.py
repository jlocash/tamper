"""Behavioral tests for tamper.ops.validation.validate_operations.

The data graphs here are Oxigraph-backed, mirroring how the plan executor
builds the materialized operation graph in production. Oxigraph canonicalizes
literal datatypes on insert (integer family -> xsd:integer, plain strings ->
xsd:string), and the operation shapes are written against those canonical
forms.
"""

import pytest
from rdflib import RDF, Graph, Literal

from tamper.core.operation import OperationURI
from tamper.errors import GraphValidationError
from tamper.ops.audio import ResampleAudio, TranscodeAudio
from tamper.ops.compress import Compress
from tamper.ops.image import (
    AddGaussianNoise,
    CropImage,
    GaussianBlur,
    MedianFilter,
    Resize,
)
from tamper.ops.video import TranscodeVideo
from tamper.ops.validation import validate_operations
from tamper.vocabularies import TAMPER


def _op_graph(op_cls, **params) -> Graph:
    """Build a single-operation graph the way the plan executor materializes one."""
    g = Graph(store="Oxigraph")
    op = op_cls.new(g, OperationURI())
    for name, value in params.items():
        setattr(op, name, value)
    return g


VALID_OPS = [
    (Compress, {"quality_factor": 80, "format": "jpeg"}),
    (Compress, {"quality_factor": 80, "format": "webp"}),
    (CropImage, {"x": 0, "y": 0, "width": 512, "height": 512}),
    (Resize, {"width": 256, "height": 256, "interpolation": "lanczos4"}),
    (MedianFilter, {"kernel_size": 5}),
    (GaussianBlur, {"kernel_size": 5, "sigma": 1.0}),
    (AddGaussianNoise, {"mean": 0.0, "std": 10.0, "seed": 42}),
    (ResampleAudio, {"target_sample_rate": 22050}),
    (TranscodeAudio, {"audio_encoder": "libmp3lame", "target_bitrate": 128000}),
    (TranscodeVideo, {"video_encoder": "libx264", "crf": 23}),
]

INVALID_OPS = [
    pytest.param(
        Compress, {"quality_factor": 101, "format": "jpeg"}, id="quality-above-max"
    ),
    pytest.param(
        Compress, {"quality_factor": -1, "format": "jpeg"}, id="quality-negative"
    ),
    pytest.param(
        Compress, {"quality_factor": 90, "format": "asdfasdf"}, id="invalid-format"
    ),
    pytest.param(Compress, {}, id="quality-missing"),
    pytest.param(
        Resize,
        {"width": 256, "height": 256, "interpolation": "bicubic"},
        id="interpolation-not-in-enum",
    ),
    pytest.param(
        Resize,
        {"width": 0, "height": 256, "interpolation": "linear"},
        id="width-not-positive",
    ),
    pytest.param(
        CropImage, {"x": -1, "y": 0, "width": 10, "height": 10}, id="crop-x-negative"
    ),
    pytest.param(
        GaussianBlur, {"kernel_size": 0, "sigma": 1.0}, id="kernel-not-positive"
    ),
    pytest.param(
        TranscodeVideo, {"video_encoder": "libx264", "crf": -1}, id="crf-negative"
    ),
]


@pytest.mark.parametrize(
    "op_cls,params", VALID_OPS, ids=[cls.__name__ for cls, _ in VALID_OPS]
)
def test_valid_operation_conforms(op_cls, params):
    validate_operations(_op_graph(op_cls, **params))


@pytest.mark.parametrize("op_cls,params", INVALID_OPS)
def test_invalid_operation_raises(op_cls, params):
    with pytest.raises(GraphValidationError):
        validate_operations(_op_graph(op_cls, **params))


def test_multiple_operations_validated_together():
    """All operations in a graph are validated"""
    g = Graph(store="Oxigraph")
    ok = Compress.new(g, OperationURI())
    ok.quality_factor = 80
    ok.format = "jpeg"
    bad = Compress.new(g, OperationURI())
    bad.quality_factor = 999
    bad.format = "jpeg"

    with pytest.raises(GraphValidationError):
        validate_operations(g)


def test_plain_literals_conform():
    """Literals with undeclared datatypes should be coerced and validated successfully"""
    g = Graph(store="Oxigraph")
    op = OperationURI()
    g.add((op, RDF.type, TAMPER.Resize))
    g.add((op, TAMPER.targetWidth, Literal(256)))
    g.add((op, TAMPER.targetHeight, Literal(256)))
    g.add((op, TAMPER.interpolation, Literal("lanczos4")))

    validate_operations(g)


def test_non_numeric_parameter_raises():
    g = Graph(store="Oxigraph")
    op = OperationURI()
    g.add((op, RDF.type, TAMPER.Compress))
    g.add((op, TAMPER.format, Literal("jpeg")))
    g.add((op, TAMPER.qualityFactor, Literal("eighty")))

    with pytest.raises(GraphValidationError):
        validate_operations(g)


def test_error_carries_validation_report():
    try:
        validate_operations(_op_graph(Compress, quality_factor=999, format="jpeg"))
    except GraphValidationError as e:
        assert e.results_graph is not None
        assert "qualityFactor" in str(e) or "Quality factor" in str(e)
    else:
        pytest.fail("expected GraphValidationError")
