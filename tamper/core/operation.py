import abc
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import tempfile

from rdflib import PROV, XSD, Node

from tamper.core.assets import load_asset_from_file
from tamper.core.workspace import AssetWorkspace
from tamper.vocabularies import TAMPER

from ._common import Resource, MappedProperty


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
    def mutate(self, workspace: AssetWorkspace):
        """
        Runs the operation, writing the asset it generates into ``workspace``.

        :param workspace: resolves the operation's input assets to local files
            and publishes the generated one back to asset storage
        """
        pass

    @contextmanager
    def _generates_file(self, workspace: AssetWorkspace, *args, **kwargs):
        """
        Yields a temporary path for the operation to write its output to. On a
        clean exit the file is described as an asset, published to asset
        storage, and attributed to this operation.
        """
        fd, tmp_path = tempfile.mkstemp(*args, dir=workspace.work_dir, **kwargs)
        os.close(fd)
        try:
            yield tmp_path
            asset = load_asset_from_file(self.graph, tmp_path)
            workspace.publish(asset, tmp_path)
            asset.was_generated_by = self.identifier
        finally:
            # publish() moves the file into the workspace cache, so this only
            # cleans up when the operation failed part way through
            Path(tmp_path).unlink(missing_ok=True)
