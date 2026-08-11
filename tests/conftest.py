from pathlib import Path

import pytest

from tamper.core import AssetWorkspace, load_asset_from_file
from tamper.core.workspace import hex_digest
from tamper.storage import AssetStorage

TEST_MEDIA = Path(__file__).parent / "test-media"

ASSETS_BUCKET = "tamper-assets"
INGEST_BUCKET = "tamper-ingest"


class FakeObjectStorage:
    """A dict-backed stand-in for ObjectStorage, keyed by (bucket, key)."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def object_exists(self, bucket_name, key):
        return (bucket_name, key) in self.objects

    def presign_put(self, bucket_name, key, expires=900):
        return f"https://fake.invalid/{bucket_name}/{key}"

    def presign_get(
        self, bucket_name, key, content_type="application/octet-stream", expires=900
    ):
        return f"https://fake.invalid/{bucket_name}/{key}"

    def download_object(self, bucket_name, key, local_filename):
        Path(local_filename).write_bytes(self.objects[(bucket_name, key)])

    def upload_object(self, bucket_name, key, local_filename):
        self.objects[(bucket_name, key)] = Path(local_filename).read_bytes()

    def copy_object(self, src_bucket, src_key, dest_bucket, dest_key):
        self.objects[(dest_bucket, dest_key)] = self.objects[(src_bucket, src_key)]

    def delete_object(self, bucket_name, key):
        del self.objects[(bucket_name, key)]


@pytest.fixture
def object_storage():
    return FakeObjectStorage()


@pytest.fixture
def asset_storage(object_storage):
    return AssetStorage(object_storage, ASSETS_BUCKET)


@pytest.fixture
def workspace(asset_storage, tmp_path):
    return AssetWorkspace(asset_storage, tmp_path / "work")


@pytest.fixture
def load_asset(asset_storage):
    """
    Loads a local media file as an asset and uploads its bytes to asset
    storage, so operations can resolve it the way they would in production.
    """

    def _load_asset(graph, src: Path):
        asset = load_asset_from_file(graph, src)
        asset_storage.upload_asset_file(hex_digest(asset), str(src))
        return asset

    return _load_asset
