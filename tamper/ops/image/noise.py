import os
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import numpy as np
from rdflib import Graph, URIRef, PROV, XSD
from rdflib.extras.describer import Describer

from tamper.assets import get_file_sha256
from tamper.namespaces import TAMPER
from .image_operation import ImageOperation


class AddGaussianNoise(ImageOperation):
    __rdf_type__ = TAMPER.AddGaussianNoise

    def __init__(self, graph: Graph, out_dir: PathLike[str], image_uri: URIRef, mean: float, std: float):
        super().__init__(graph, out_dir)
        self.image_uri = image_uri
        self.mean = mean
        self.std = std

    def _parameters(self, op: Describer):
        op.value(TAMPER.gaussianMean, self.mean, datatype=XSD.decimal)
        op.value(TAMPER.gaussianStd, self.std, datatype=XSD.decimal)
        op.value(PROV.used, self.image_uri)

    def _apply(self) -> Path:
        img_file = self.graph.value(subject=self.image_uri, predicate=TAMPER.filePath)
        if img_file is None:
            raise ValueError("No file path found for asset")

        img = cv2.imread(str(img_file))

        noise = np.random.normal(self.mean, self.std, img.shape)
        noisy_img = np.clip(img + noise, 0, 255).astype(np.uint8)

        suffix = Path(img_file).suffix
        tmp_file = NamedTemporaryFile(suffix=suffix, delete=False, delete_on_close=False)
        cv2.imwrite(tmp_file.name, noisy_img)

        checksum = get_file_sha256(tmp_file.name)
        new_img_file = self.out_dir / (checksum + suffix)
        os.rename(tmp_file.name, new_img_file)

        return new_img_file
