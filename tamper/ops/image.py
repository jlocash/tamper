import secrets
from os import PathLike
from pathlib import Path

import cv2
import numpy as np
from rdflib import Node, RDF, Literal, XSD
from rdflib.graph import Graph
from rdflib.term import URIRef

from tamper.vocabularies import TAMPER

from .operation import Operation, PropertyMissingError


class CompressJPEG(Operation):
    quality_factor: int

    def __init__(self, quality_factor: int):
        super().__init__()
        if not 0 <= quality_factor <= 100:
            raise ValueError(
                f"quality_factor must be between 0 and 100, got {quality_factor}"
            )
        self.quality_factor = quality_factor

    def transform(
        self, input_asset_file: PathLike[str], output_asset_file: PathLike[str]
    ):
        img = cv2.imread(str(input_asset_file))
        ok, buf = cv2.imencode(
            ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.quality_factor]
        )
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        Path(output_asset_file).write_bytes(buf.tobytes())

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.CompressJPEG))
        g.add((self.subject, TAMPER.qualityFactor, Literal(self.quality_factor)))
        return g

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        quality_factor = graph.value(subject, TAMPER.qualityFactor)
        if quality_factor is None:
            raise PropertyMissingError(subject, TAMPER.qualityFactor)
        return cls(quality_factor=int(quality_factor))


class CompressWebP(Operation):
    quality_factor: int

    def __init__(self, quality_factor: int):
        super().__init__()
        if not 0 <= quality_factor <= 100:
            raise ValueError(
                f"quality_factor must be between 0 and 100, got {quality_factor}"
            )
        self.quality_factor = quality_factor

    def transform(
        self, input_asset_file: PathLike[str], output_asset_file: PathLike[str]
    ):
        img = cv2.imread(str(input_asset_file))
        ok, buf = cv2.imencode(
            ".webp", img, [cv2.IMWRITE_WEBP_QUALITY, self.quality_factor]
        )
        if not ok:
            raise RuntimeError("WebP encoding failed")
        Path(output_asset_file).write_bytes(buf.tobytes())

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.CompressWebP))
        g.add((self.subject, TAMPER.qualityFactor, Literal(self.quality_factor)))
        return g

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        quality_factor = graph.value(subject, TAMPER.qualityFactor)
        if quality_factor is None:
            raise PropertyMissingError(subject, TAMPER.qualityFactor)
        return cls(quality_factor=int(quality_factor))


class CropImage(Operation):
    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__()
        if x < 0 or y < 0:
            raise ValueError(
                f"x and y must be non-negative image coordinates, got x={x}, y={y}"
            )
        if width <= 0 or height <= 0:
            raise ValueError(
                f"width and height must be positive, got width={width}, height={height}"
            )
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def transform(
        self, input_asset_file: PathLike[str], output_asset_file: PathLike[str]
    ):
        img = cv2.imread(str(input_asset_file))
        if img is None:
            raise RuntimeError(f"Could not read image: {input_asset_file}")
        h, w = img.shape[:2]
        if self.x + self.width > w or self.y + self.height > h:
            raise ValueError(
                f"Crop region (x={self.x}, y={self.y}, width={self.width}, height={self.height}) "
                f"exceeds image bounds ({w}x{h})"
            )
        cropped = img[self.y : self.y + self.height, self.x : self.x + self.width]
        ext = Path(input_asset_file).suffix or ".png"
        ok, buf = cv2.imencode(ext, cropped)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")
        Path(output_asset_file).write_bytes(buf.tobytes())

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.CropImage))
        g.add(
            (
                self.subject,
                TAMPER.cropX,
                Literal(self.x, datatype=XSD.nonNegativeInteger),
            )
        )
        g.add(
            (
                self.subject,
                TAMPER.cropY,
                Literal(self.y, datatype=XSD.nonNegativeInteger),
            )
        )
        g.add(
            (
                self.subject,
                TAMPER.cropWidth,
                Literal(self.width, datatype=XSD.positiveInteger),
            )
        )
        g.add(
            (
                self.subject,
                TAMPER.cropHeight,
                Literal(self.height, datatype=XSD.positiveInteger),
            )
        )
        return g

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        x = graph.value(subject, TAMPER.cropX)
        if x is None:
            raise PropertyMissingError(subject, TAMPER.cropX)
        y = graph.value(subject, TAMPER.cropY)
        if y is None:
            raise PropertyMissingError(subject, TAMPER.cropY)
        width = graph.value(subject, TAMPER.cropWidth)
        if width is None:
            raise PropertyMissingError(subject, TAMPER.cropWidth)
        height = graph.value(subject, TAMPER.cropHeight)
        if height is None:
            raise PropertyMissingError(subject, TAMPER.cropHeight)
        return cls(int(x), int(y), int(width), int(height))


_INTERPOLATIONS = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "area": cv2.INTER_AREA,
    "lanczos4": cv2.INTER_LANCZOS4,
}


class Resize(Operation):
    def __init__(self, width: int, height: int, interpolation: str = "linear"):
        super().__init__()
        if interpolation not in _INTERPOLATIONS:
            raise ValueError(
                f"Unknown interpolation '{interpolation}', expected one of {sorted(_INTERPOLATIONS)}"
            )
        self.width = width
        self.height = height
        self.interpolation = interpolation

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.Resize))
        g.add(
            (
                self.subject,
                TAMPER.targetWidth,
                Literal(self.width, datatype=XSD.positiveInteger),
            )
        )
        g.add(
            (
                self.subject,
                TAMPER.targetHeight,
                Literal(self.height, datatype=XSD.positiveInteger),
            )
        )
        g.add((self.subject, TAMPER.interpolation, Literal(self.interpolation)))
        return g

    def transform(
        self, input_image_file: PathLike[str], output_image_file: PathLike[str]
    ):
        img = cv2.imread(str(input_image_file))
        resized = cv2.resize(
            img,
            (self.width, self.height),
            interpolation=_INTERPOLATIONS[self.interpolation],
        )
        ext = Path(input_image_file).suffix or ".png"
        ok, buf = cv2.imencode(ext, resized)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")
        Path(output_image_file).write_bytes(buf.tobytes())

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        width = graph.value(subject=subject, predicate=TAMPER.targetWidth)
        if width is None:
            raise PropertyMissingError(subject, TAMPER.targetWidth)

        height = graph.value(subject=subject, predicate=TAMPER.targetHeight)
        if height is None:
            raise PropertyMissingError(subject, TAMPER.targetHeight)

        interpolation = graph.value(subject=subject, predicate=TAMPER.interpolation)
        if interpolation is None:
            raise PropertyMissingError(subject, TAMPER.interpolation)

        return cls(
            width=int(width), height=int(height), interpolation=str(interpolation)
        )


class MedianFilter(Operation):
    def __init__(self, kernel_size: int):
        super().__init__()
        if kernel_size < 3 or kernel_size % 2 == 0:
            raise ValueError(
                f"kernel_size must be an odd integer >= 3, got {kernel_size}"
            )
        self.kernel_size = kernel_size

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.MedianFilter))
        g.add(
            (
                self.subject,
                TAMPER.kernelSize,
                Literal(self.kernel_size, datatype=XSD.positiveInteger),
            )
        )
        return g

    def transform(
        self, input_image_file: PathLike[str], output_image_file: PathLike[str]
    ):
        img = cv2.imread(str(input_image_file))
        filtered = cv2.medianBlur(img, self.kernel_size)
        ext = Path(input_image_file).suffix or ".png"
        ok, buf = cv2.imencode(ext, filtered)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")
        Path(output_image_file).write_bytes(buf.tobytes())

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        kernel_size = graph.value(subject=subject, predicate=TAMPER.kernelSize)
        if kernel_size is None:
            raise PropertyMissingError(subject, TAMPER.kernelSize)
        return cls(kernel_size=int(kernel_size))


class GaussianBlur(Operation):
    def __init__(self, kernel_size: int, sigma: float = 0.0):
        super().__init__()
        if kernel_size < 1 or kernel_size % 2 == 0:
            raise ValueError(
                f"kernel_size must be an odd positive integer, got {kernel_size}"
            )
        self.kernel_size = kernel_size
        self.sigma = sigma

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.GaussianBlur))
        g.add(
            (
                self.subject,
                TAMPER.kernelSize,
                Literal(self.kernel_size, datatype=XSD.positiveInteger),
            )
        )
        g.add(
            (self.subject, TAMPER.blurSigma, Literal(self.sigma, datatype=XSD.decimal))
        )
        return g

    def transform(
        self, input_image_file: PathLike[str], output_image_file: PathLike[str]
    ):
        img = cv2.imread(str(input_image_file))
        blurred = cv2.GaussianBlur(
            img, (self.kernel_size, self.kernel_size), sigmaX=self.sigma
        )
        ext = Path(input_image_file).suffix or ".png"
        ok, buf = cv2.imencode(ext, blurred)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")
        Path(output_image_file).write_bytes(buf.tobytes())

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        kernel_size = graph.value(subject=subject, predicate=TAMPER.kernelSize)
        if kernel_size is None:
            raise PropertyMissingError(subject, TAMPER.kernelSize)

        sigma = graph.value(subject=subject, predicate=TAMPER.blurSigma)
        if sigma is None:
            raise PropertyMissingError(subject, TAMPER.blurSigma)

        return cls(kernel_size=int(kernel_size), sigma=float(sigma))


class AddGaussianNoise(Operation):
    def __init__(self, mean: float, std: float, seed: int | None = None):
        super().__init__()
        if std < 0:
            raise ValueError(f"std must be non-negative, got {std}")
        self.mean = mean
        self.std = std
        self.seed = secrets.randbits(64) if seed is None else seed

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.AddGaussianNoise))
        g.add(
            (
                self.subject,
                TAMPER.gaussianMean,
                Literal(self.mean, datatype=XSD.decimal),
            )
        )
        g.add(
            (self.subject, TAMPER.gaussianStd, Literal(self.std, datatype=XSD.decimal))
        )
        g.add(
            (
                self.subject,
                TAMPER.gaussianSeed,
                Literal(self.seed, datatype=XSD.nonNegativeInteger),
            )
        )
        return g

    def transform(
        self, input_image_file: PathLike[str], output_image_file: PathLike[str]
    ):
        img = cv2.imread(str(input_image_file))
        rng = np.random.default_rng(self.seed)
        noise = rng.normal(self.mean, self.std, img.shape)
        noisy_img = np.clip(img + noise, 0, 255).astype(np.uint8)
        ext = Path(input_image_file).suffix or ".png"
        ok, buf = cv2.imencode(ext, noisy_img)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")
        Path(output_image_file).write_bytes(buf.tobytes())

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: URIRef):
        mean = graph.value(subject=subject, predicate=TAMPER.gaussianMean)
        if mean is None:
            raise PropertyMissingError(subject, TAMPER.gaussianMean)

        std = graph.value(subject=subject, predicate=TAMPER.gaussianStd)
        if std is None:
            raise PropertyMissingError(subject, TAMPER.gaussianStd)

        seed = graph.value(subject=subject, predicate=TAMPER.gaussianSeed)

        return cls(
            mean=float(mean),
            std=float(std),
            seed=int(seed) if seed is not None else None,
        )
