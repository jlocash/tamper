from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class IngestStatus(StrEnum):
    OPEN = "open"
    PENDING_COMMIT = "pending-commit"
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"


class StagedAssetStatus(StrEnum):
    STAGED = "staged"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class StagedAsset:
    key: str
    status: StagedAssetStatus = StagedAssetStatus.STAGED
    asset_trn: str | None = None
    error: str | None = None


@dataclass
class Ingest:
    id: str
    created: datetime
    status: IngestStatus = IngestStatus.OPEN
    assets: dict[str, StagedAsset] = field(default_factory=dict)
