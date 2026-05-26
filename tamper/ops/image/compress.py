import os
import shutil
import tempfile
from os import PathLike
from pathlib import Path

import cv2
from rdflib import Graph, URIRef, PROV, XSD, Node, RDF
from rdflib.extras.describer import Describer

from tamper.assets import get_file_sha256
from tamper.namespaces import TAMPER
from .image_operation import ImageOperation


class CompressImage(ImageOperation):
    __rdf_type__ = TAMPER.CompressImage

    def __init__(self, quality_factor: int):
        self.quality_factor = quality_factor

    def _parameters(self, op: Describer):
        op.value(TAMPER.qualityFactor, self.quality_factor, datatype=XSD.nonNegativeInteger)

    def _apply(self, asset_file: Path, out_dir: Path) -> Path:
        img = cv2.imread(str(asset_file))
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        cv2.imwrite(tmp_path, img, [cv2.IMWRITE_JPEG_QUALITY, self.quality_factor])
        checksum = get_file_sha256(tmp_path)
        new_img_file = out_dir / (checksum + ".jpg")
        shutil.move(tmp_path, new_img_file)
        return new_img_file

    @classmethod
    def from_rdf(cls, graph: Graph, uri: Node):
        # if not (uri, RDF.type, cls.__rdf_type__) in graph:
        #     raise ValueError(f"Node is not of type {cls.__rdf_type__}")

        quality_factor = graph.value(subject=uri, predicate=TAMPER.qualityFactor)
        if quality_factor is None:
            raise ValueError("No quality factor found")

        return cls(quality_factor=int(quality_factor))
