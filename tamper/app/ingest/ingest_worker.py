from abc import ABC, abstractmethod
import logging
from pathlib import Path
import tempfile

from rdflib import Graph

from tamper.app.kg.knowledge_graph import KnowledgeGraph
from tamper.core._common import TamperURI
from tamper.core.assets import load_asset_from_file
from tamper.core.workspace import hex_digest as hex_digest_of
from tamper.storage import AssetStorage, IngestStorage

from .ingest import Ingest, IngestStatus, StagedAssetStatus

logger = logging.getLogger(__name__)


class IngestWorker(ABC):
    @abstractmethod
    def commit(self, ingest: Ingest) -> Graph:
        pass


class SimpleIngestWorker(IngestWorker):
    def __init__(
        self,
        asset_storage: AssetStorage,
        ingest_storage: IngestStorage,
        kg: KnowledgeGraph,
    ):
        self.asset_storage = asset_storage
        self.ingest_storage = ingest_storage
        self.kg = kg

    def commit(self, ingest: Ingest):
        logger.info("Processing ingest job %s", ingest.id)
        ingest_graph_uri = TamperURI("ingest", ingest.id)
        for staged in ingest.assets.values():
            if staged.status is StagedAssetStatus.PROCESSED:
                continue
            try:
                subgraph, asset_trn = self._materialize(staged.key)
                self.kg.insert_statements(ingest_graph_uri, subgraph)

                staged.status = StagedAssetStatus.PROCESSED
                staged.asset_trn = asset_trn
                staged.error = None

                self.ingest_storage.delete(staged.key)

            except Exception as e:
                logger.exception(
                    "Ingest %s: error processing key %s", ingest.id, staged.key
                )
                staged.status = StagedAssetStatus.FAILED
                staged.error = str(e)
                continue

        failed = any(
            asset.status is StagedAssetStatus.FAILED for asset in ingest.assets.values()
        )
        if not failed:
            self.kg.move_to_default(ingest_graph_uri)

        ingest.status = IngestStatus.FAILED if failed else IngestStatus.COMPLETED

    def _materialize(self, key: str) -> tuple[Graph, str]:
        """
        Downloads a staged object, builds its asset subgraph, and copies the
        object to its content-addressed key. Blocking; runs in a worker thread.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = Path(tmp_dir) / "asset"
            self.ingest_storage.download(key, str(local_path))

            subgraph = Graph()
            asset = load_asset_from_file(subgraph, local_path)
            hex_digest = hex_digest_of(asset)

            if not self.asset_storage.asset_file_exists(hex_digest):
                self.asset_storage.copy_from(
                    self.ingest_storage.bucket_name, key, hex_digest
                )

            return subgraph, str(asset.identifier)
