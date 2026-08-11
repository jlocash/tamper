from typing import Annotated

from fastapi import Depends, Request

from tamper.app.config import Settings, get_settings
from tamper.app.ingest import Ingest, IngestQueue
from tamper.app.kg import KnowledgeGraph
from tamper.storage import AssetStorage, IngestStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_kg(request: Request):
    return request.app.state.kg


def get_asset_storage(request: Request) -> AssetStorage:
    return request.app.state.asset_storage


def get_ingest_storage(request: Request) -> IngestStorage:
    return request.app.state.ingest_storage


def get_ingests(request: Request) -> dict[str, Ingest]:
    return request.app.state.ingests


def get_ingest_queue(request: Request) -> IngestQueue:
    return request.app.state.ingest_queue


KnowledgeGraphDep = Annotated[KnowledgeGraph, Depends(get_kg)]
AssetStorageDep = Annotated[AssetStorage, Depends(get_asset_storage)]
IngestStorageDep = Annotated[IngestStorage, Depends(get_ingest_storage)]
IngestsDep = Annotated[dict[str, Ingest], Depends(get_ingests)]
IngestQueueDep = Annotated[IngestQueue, Depends(get_ingest_queue)]
