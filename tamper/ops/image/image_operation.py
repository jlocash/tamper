import abc
from datetime import datetime
from os import PathLike
from pathlib import Path
from uuid import uuid4

from rdflib import Graph, URIRef, PROV
from rdflib.extras.describer import Describer

from tamper.assets import build_asset_from_file
from tamper.namespaces import TAMPER


class ImageOperation(abc.ABC):
    __rdf_type__ = TAMPER.ImageOperation

    def __init__(self, graph: Graph, out_dir: PathLike[str]):
        self.graph = graph
        self.out_dir = Path(out_dir)
        if not self.out_dir.exists():
            raise ValueError(f"Output directory {self.out_dir} does not exist")
        if not self.out_dir.is_dir():
            raise ValueError(f"Output directory {self.out_dir} is not a directory")

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
    def _apply(self) -> Path:
        pass
