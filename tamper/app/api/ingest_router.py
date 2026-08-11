import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from tamper.app.ingest import Ingest, IngestStatus, StagedAsset
from .dependencies import (
    IngestQueueDep,
    IngestStorageDep,
    IngestsDep,
)

router = APIRouter(tags=["ingest"])


def _get_ingest(ingests: dict[str, Ingest], ingest_id: str) -> Ingest:
    if ingest_id not in ingests:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ingest {ingest_id} not found")
    return ingests[ingest_id]


def _require_open(ingest: Ingest):
    if ingest.status is not IngestStatus.OPEN:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ingest {ingest.id} is already {ingest.status}"
        )


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def create_ingest(ingests: IngestsDep) -> Ingest:
    ingest = Ingest(id=secrets.token_urlsafe(12), created=datetime.now())
    ingests[ingest.id] = ingest
    return ingest


@router.get("/ingest/{ingest_id}")
async def get_ingest(ingest_id: str, ingests: IngestsDep) -> Ingest:
    return _get_ingest(ingests, ingest_id)


class StagedAssetUpload(BaseModel):
    key: str
    url: str


@router.post("/ingest/{ingest_id}/asset", status_code=status.HTTP_201_CREATED)
async def create_ingest_asset(
    ingest_id: str,
    ingests: IngestsDep,
    ingest_storage: IngestStorageDep,
) -> StagedAssetUpload:
    ingest = _get_ingest(ingests, ingest_id)
    _require_open(ingest)

    key, url = ingest_storage.presign_put(ingest_id)
    ingest.assets[key] = StagedAsset(key=key)
    return StagedAssetUpload(key=key, url=url)


@router.post("/ingest/{ingest_id}/commit", status_code=status.HTTP_202_ACCEPTED)
async def commit_ingest(
    ingest_id: str,
    ingests: IngestsDep,
    ingest_queue: IngestQueueDep,
) -> Ingest:
    ingest = _get_ingest(ingests, ingest_id)
    _require_open(ingest)

    ingest.status = IngestStatus.PENDING_COMMIT
    ingest_queue.put_ingest(ingest)
    return ingest
