import abc
from datetime import datetime
import os
from os import PathLike
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from PIL import Image
from rdflib import Graph, URIRef, PROV, XSD
from rdflib.extras.describer import Describer

from tamper.assets import get_file_sha256, build_asset_from_file
from tamper.namespaces import TAMPER


class Operation(abc.ABC):
    __rdf_type__ = TAMPER.Operation

    def __init__(self, graph: Graph, out_dir: PathLike[str]):
        self.graph = graph
        self.out_dir = Path(out_dir)

    def apply(self) -> tuple[Graph, URIRef]:
        subgraph = Graph()
        op_uri = URIRef(f"operation://{uuid4()}")
        op = Describer(subgraph, about=op_uri)
        op.rdftype(self.__rdf_type__)
        op.value(PROV.startedAtTime, datetime.now())

        self._parameters(op)
        new_asset_file = self._apply()
        asset_uri = build_asset_from_file(subgraph, new_asset_file)
        op.rev(PROV.wasGeneratedBy, asset_uri)
        op.value(PROV.endedAtTime, datetime.now())

        return subgraph, asset_uri

    @abc.abstractmethod
    def _parameters(self, op: Describer):
        pass

    @abc.abstractmethod
    def _apply(self):
        raise NotImplementedError("Subclasses must implement this method")


class CompressImage(Operation):
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

        img = Image.open(str(asset_file))
        temp_file = NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(temp_file.name, "JPEG", quality=self.quality)

        checksum = get_file_sha256(temp_file.name)
        new_img_file = self.out_dir / (checksum + ".jpg")
        os.rename(temp_file.name, new_img_file)

        return new_img_file
