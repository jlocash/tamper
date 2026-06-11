import abc
from contextlib import contextmanager
from datetime import datetime
import mimetypes
import os
from pathlib import Path
import secrets
import tempfile

from rdflib import PROV, XSD, Node

from tamper.core.assets import load_asset_from_file
from tamper.vocabularies import TAMPER

from ._common import Resource, MappedProperty, TamperURI


class OperationURI(TamperURI):
    def __new__(cls, value: str | None = None):
        if value is None:
            value = secrets.token_urlsafe(12)
        return super().__new__(cls, "operation", value)


class Operation(Resource, abc.ABC):
    __rdf_type__ = TAMPER.Operation

    started_at_time: MappedProperty[datetime] = MappedProperty(
        PROV.startedAtTime, XSD.dateTime
    )
    ended_at_time: MappedProperty[datetime] = MappedProperty(
        PROV.endedAtTime, XSD.dateTime
    )

    def get_used(self):
        return list(self.graph.objects(self.identifier, PROV.used))

    def used(self, v: Resource | Node):
        self.add(PROV.used, v)

    def generated(self, v: Resource | Node):
        if isinstance(v, Resource):
            v = v.identifier
        self.graph.add((v, PROV.wasGeneratedBy, self.identifier))

    def get_generated(self):
        return self.subjects(PROV.wasGeneratedBy)

    @abc.abstractmethod
    def mutate(self, out_dir: os.PathLike[str] | None = None):
        pass

    @contextmanager
    def _generates_file(self, *args, **kwargs):
        fd, tmp_path = tempfile.mkstemp(*args, **kwargs)
        os.close(fd)
        try:
            yield tmp_path
            asset = load_asset_from_file(self.graph, tmp_path)
            suffix = Path(asset.file_path).suffix
            if suffix is None:
                suffix = mimetypes.guess_extension(asset.media_type)
            checksum = asset.checksum.split(":")[-1]
            new_file_path = Path(tmp_path).parent / (checksum + suffix)
            asset.move_file(new_file_path)
            asset.was_generated_by = self.identifier
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise
