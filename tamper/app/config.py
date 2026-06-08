from datetime import datetime
import logging
import os
from pathlib import Path

from rdflib import Graph, URIRef

from tamper.app.kg.knowledge_graph import KnowledgeGraph
from tamper.app.kg.local import LocalKnowledgeGraph
from tamper.dataset import Catalog

logger = logging.getLogger(__name__)

CATALOG_URI = URIRef("tamper://catalog")


class Config:
    def __init__(self):
        if "TAMPER_HOME" in os.environ:
            self.TAMPER_HOME_DIR = Path(os.environ["TAMPER_HOME"])
        else:
            self.TAMPER_HOME_DIR = Path(os.environ["HOME"]) / ".tamper"
            logger.info("TAMPER_HOME not set, defaulting to %s", self.TAMPER_HOME_DIR)

        self.TAMPER_PLANS_DIR = self.TAMPER_HOME_DIR / "plans"
        self.TAMPER_MEDIA_DIR = self.TAMPER_HOME_DIR / "media"
        self.TAMPER_CATALOG_FILE = self.TAMPER_HOME_DIR / "catalog.trig"
        self.TAMPER_CATALOG_URI = URIRef("tamper://catalog")

    def ensure_directories_exist(self):
        if not self.TAMPER_HOME_DIR.exists():
            logger.info("Initializing home directory at %s", self.TAMPER_HOME_DIR)
            self.TAMPER_HOME_DIR.mkdir(parents=True)
        if not self.TAMPER_PLANS_DIR.exists():
            logger.info("Initializing plans directory at %s", self.TAMPER_PLANS_DIR)
            self.TAMPER_PLANS_DIR.mkdir(parents=True)
        if not self.TAMPER_MEDIA_DIR.exists():
            logger.info("initializing media directory at %s", self.TAMPER_MEDIA_DIR)
            self.TAMPER_MEDIA_DIR.mkdir(parents=True)
        if not self.TAMPER_CATALOG_FILE.exists():
            logger.info("Initializing catalog at %s", self.TAMPER_CATALOG_FILE)
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
        return LocalKnowledgeGraph(self.TAMPER_CATALOG_FILE)


config = Config()
