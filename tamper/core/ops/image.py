from os import PathLike
from pathlib import Path

import cv2
import numpy as np
from rdflib import Node, RDF, Literal, XSD
from rdflib.graph import Graph
from rdflib.term import URIRef

from namespaces import TAMPER

from .operation import Operation


class CompressJPEG(Operation):
    quality_factor: int

    def __init__(self, quality_factor: int):
        super().__init__()
        self.quality_factor = quality_factor

    def transform(self, input_asset_file: PathLike[str], output_asset_file: PathLike[str]):
        img = cv2.imread(str(input_asset_file))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.quality_factor])
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
            raise ValueError(f"Graph is missing property {TAMPER.qualityFactor} for subject {subject}")
        return cls(quality_factor=int(quality_factor))


class AddGaussianNoise(Operation):
    def __init__(self, mean: float, std: float):
        super().__init__()
        self.mean = mean
        self.std = std

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.AddGaussianNoise))
        g.add((self.subject, TAMPER.gaussianMean, Literal(self.mean, datatype=XSD.float)))
        g.add((self.subject, TAMPER.gaussianStd, Literal(self.std, datatype=XSD.float)))
        return g

    def transform(self, input_image_file: PathLike[str], output_image_file: PathLike[str]):
        img = cv2.imread(str(input_image_file))
        noise = np.random.normal(self.mean, self.std, img.shape)
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
            raise ValueError(f"Graph is missing property {TAMPER.gaussianMean} for subject {subject}")

        std = graph.value(subject=subject, predicate=TAMPER.gaussianStd)
        if std is None:
            raise ValueError(f"Graph is missing property {TAMPER.gaussianStd} for subject {subject}")

        return cls(mean=float(mean), std=float(std))
