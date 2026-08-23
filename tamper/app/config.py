from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rdflib import Graph

from tamper.app.kg import KnowledgeGraph, LocalKnowledgeGraph
from tamper.core import Catalog
from tamper.core.identifiers import TamperURI
from tamper.storage import AssetStorage, IngestStorage, ObjectStorage

CATALOG_URI = TamperURI("catalog", "0")


class Settings(BaseSettings):
    """
    Tamper's runtime configuration, read from the environment and ``.env``.

    Field names map to upper-case environment variables, so ``tamper_home``
    is set with ``TAMPER_HOME``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tamper_home: Path = Field(
        default_factory=lambda: Path.home() / ".tamper",
        description="Directory holding operation plans, the RDF graph, and scratch files",
    )

    s3_endpoint_url: str
    s3_region_name: str
    tamper_assets_bucket: str = "tamper-assets"
    tamper_ingest_bucket: str = "tamper-ingest"

    cors_allow_origins: list[str] = Field(
        default_factory=list,
        description="Browser origins permitted to call the API, e.g. a frontend dev server",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @computed_field
    @property
    def plans_dir(self) -> Path:
        return self.tamper_home / "plans"

    @computed_field
    @property
    def graph_dir(self) -> Path:
        return self.tamper_home / "graph"

    @computed_field
    @property
    def work_dir(self) -> Path:
        """Scratch space where operations materialize assets while they run"""
        return self.tamper_home / "work"

    @property
    def catalog_uri(self) -> TamperURI:
        return CATALOG_URI

    def ensure_directories_exist(self):
        for directory in (self.tamper_home, self.plans_dir, self.work_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if not self.graph_dir.exists():
            self.init_catalog()

    def init_catalog(self):
        kg = self.get_kg()
        cat = Catalog.new(Graph(), CATALOG_URI)
        cat.title = "Tamper dataset catalog"
        cat.description = "The central catalog of available datasets"
        cat.created = datetime.now()
        kg.insert_statements_default(cat.graph)
        kg.commit()

    def get_kg(self) -> KnowledgeGraph:
        return LocalKnowledgeGraph(self.graph_dir)

    def get_object_storage(self) -> ObjectStorage:
        return ObjectStorage(
            endpoint_url=self.s3_endpoint_url,
            region_name=self.s3_region_name,
        )

    def get_asset_storage(self) -> AssetStorage:
        return AssetStorage(self.get_object_storage(), self.tamper_assets_bucket)

    def get_ingest_storage(self) -> IngestStorage:
        return IngestStorage(self.get_object_storage(), self.tamper_ingest_bucket)


@lru_cache
def get_settings() -> Settings:
    """
    The process-wide settings. Cached so the environment is read once, and
    overridable in tests via FastAPI's dependency_overrides.
    """
    return Settings()
