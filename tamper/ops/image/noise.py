import os
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import numpy as np
from rdflib import Graph, URIRef, PROV, XSD, RDF
from rdflib.extras.describer import Describer

from tamper.assets import get_file_sha256
from tamper.namespaces import TAMPER
from .image_operation import ImageOperation


class AddGaussianNoise(ImageOperation):
    __rdf_type__ = TAMPER.AddGaussianNoise

    def __init__(self, mean: float, std: float):
        self.mean = mean
        self.std = std

    def _parameters(self, op: Describer):
        op.value(TAMPER.gaussianMean, self.mean, datatype=XSD.decimal)
        op.value(TAMPER.gaussianStd, self.std, datatype=XSD.decimal)

    def _apply(self, img_file: Path, out_dir: Path) -> Path:
        img = cv2.imread(str(img_file))

        noise = np.random.normal(self.mean, self.std, img.shape)
        noisy_img = np.clip(img + noise, 0, 255).astype(np.uint8)

        suffix = Path(img_file).suffix
        tmp_file = NamedTemporaryFile(suffix=suffix, delete=False, delete_on_close=False)
        cv2.imwrite(tmp_file.name, noisy_img)

        checksum = get_file_sha256(tmp_file.name)
        new_img_file = out_dir / (checksum + suffix)
        os.rename(tmp_file.name, new_img_file)

        return new_img_file

    @classmethod
    def from_rdf(cls, graph: Graph, uri: URIRef):
        # if not (uri, RDF.type, cls.__rdf_type__) in graph:
        #     raise ValueError(f"Node is not of type {cls.__rdf_type__}")

        mean = graph.value(subject=uri, predicate=TAMPER.gaussianMean)
        if mean is None:
            raise ValueError("No mean found")

        std = graph.value(subject=uri, predicate=TAMPER.gaussianStd)
        if std is None:
            raise ValueError("No std found")

        return cls(mean=float(mean), std=float(std))
