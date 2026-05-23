import os
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
from rdflib import Graph, URIRef, PROV, XSD
from rdflib.extras.describer import Describer

from tamper.assets import get_file_sha256
from tamper.namespaces import TAMPER
from .image_operation import ImageOperation


class CompressImage(ImageOperation):
    __rdf_type__ = TAMPER.CompressImage

    def __init__(self, graph: Graph, out_dir: PathLike[str], image_uri: URIRef, quality: int):
        super().__init__(graph, out_dir)
        self.image_uri = image_uri
        self.quality = quality

    def _parameters(self, op: Describer):
        op.value(TAMPER.qualityFactor, self.quality, datatype=XSD.nonNegativeInteger)
        op.value(PROV.used, self.image_uri)

    def _apply(self) -> Path:
        asset_file = self.graph.value(subject=self.image_uri, predicate=TAMPER.filePath)
        if asset_file is None:
            raise ValueError("No file path found for asset")

        img = cv2.imread(str(asset_file))
        temp_file = NamedTemporaryFile(suffix=".jpg", delete=False, delete_on_close=False)
        cv2.imwrite(temp_file.name, img, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        checksum = get_file_sha256(temp_file.name)
        new_img_file = self.out_dir / (checksum + ".jpg")
        os.rename(temp_file.name, new_img_file)
        return new_img_file
