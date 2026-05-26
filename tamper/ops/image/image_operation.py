import abc
import logging
from datetime import datetime
from os import PathLike
from pathlib import Path
from uuid import uuid4

from rdflib import Graph, URIRef, PROV
from rdflib.extras.describer import Describer

from tamper.assets import build_asset_from_file
from tamper.namespaces import TAMPER

logger = logging.getLogger(__name__)


class ImageOperation(abc.ABC):
    __rdf_type__ = TAMPER.ImageOperation

    def apply(self, input_image_file: Path, input_image_uri: URIRef, out_dir: PathLike[str]) -> tuple[URIRef, Graph]:
        out_dir = Path(out_dir)
        if not out_dir.exists():
            raise ValueError(f"Output directory {out_dir} does not exist")
        if not out_dir.is_dir():
            raise ValueError(f"Output directory {out_dir} is not a directory")

        subgraph = Graph()
        op_uri = URIRef(f"operation://{uuid4()}")
        op = Describer(subgraph, about=op_uri)
        op.rdftype(self.__rdf_type__)
        op.value(PROV.startedAtTime, datetime.now())
        op.value(PROV.used, input_image_uri)

        self._parameters(op)
        new_asset_file = self._apply(input_image_file, out_dir)
        asset_uri = build_asset_from_file(subgraph, new_asset_file)
        op.rev(PROV.wasGeneratedBy, asset_uri)
        op.value(PROV.endedAtTime, datetime.now())

        return asset_uri, subgraph

    @abc.abstractmethod
    def _parameters(self, op: Describer):
        pass

    @abc.abstractmethod
    def _apply(self, image_file: Path, out_dir: Path) -> Path:
        pass
