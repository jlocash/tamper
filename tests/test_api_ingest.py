"""Tests for the ingest API — presigned staging, commit, and the background worker."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rdflib import URIRef

from tamper.app.api.dependencies import (
    get_ingest_queue,
    get_ingest_storage,
    get_ingests,
)
from tamper.app.api.ingest_router import router
from tamper.app.ingest import IngestQueue, SimpleIngestWorker
from tamper.app.kg import LocalKnowledgeGraph
from tamper.storage import AssetStorage, IngestStorage
from tamper.vocabularies import TAMPER

from .conftest import ASSETS_BUCKET, INGEST_BUCKET, TEST_MEDIA

IMAGE = TEST_MEDIA / "images" / "file_example_PNG_500kB.png"


@pytest.fixture
def kg(tmp_path):
    return LocalKnowledgeGraph(tmp_path / "graph")


@pytest.fixture
def client(kg, object_storage):
    """A test client wired to a fake object store and a throwaway graph."""
    ingests = {}
    ingest_storage = IngestStorage(object_storage, INGEST_BUCKET)
    queue = IngestQueue(
        SimpleIngestWorker(
            asset_storage=AssetStorage(object_storage, ASSETS_BUCKET),
            ingest_storage=ingest_storage,
            kg=kg,
        )
    )

    async def lifespan(app):
        await queue.start()
        yield
        await queue.stop()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    app.dependency_overrides[get_ingests] = lambda: ingests
    app.dependency_overrides[get_ingest_queue] = lambda: queue
    app.dependency_overrides[get_ingest_storage] = lambda: ingest_storage

    with TestClient(app) as client:
        yield client


def stage(client, object_storage, ingest_id, data: bytes) -> str:
    """Requests a presigned upload and puts ``data`` at the returned key."""
    upload = client.post(f"/ingest/{ingest_id}/asset").json()
    object_storage.objects[(INGEST_BUCKET, upload["key"])] = data
    return upload["key"]


PENDING = ("pending-commit", "committing")


def commit(client, ingest_id, timeout: float = 30.0) -> dict:
    """Commits an ingest and returns its state once the worker is done with it."""
    assert client.post(f"/ingest/{ingest_id}/commit").status_code == 202
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get(f"/ingest/{ingest_id}").json()
        if state["status"] not in PENDING:
            return state
        # the worker commits on its own thread; poll until it lands
        time.sleep(0.01)
    raise AssertionError(f"ingest {ingest_id} never left the committing state")


def asset_key(hex_digest: str) -> str:
    return f"assets/sha256/{hex_digest[:2]}/{hex_digest[2:4]}/{hex_digest}"


class TestCreateIngest:
    def test_returns_open_ingest_with_id(self, client):
        response = client.post("/ingest")
        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["status"] == "open"
        assert body["assets"] == {}

    def test_ids_are_unique(self, client):
        first = client.post("/ingest").json()["id"]
        second = client.post("/ingest").json()["id"]
        assert first != second

    def test_ingest_is_retrievable(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        assert client.get(f"/ingest/{ingest_id}").json()["id"] == ingest_id

    def test_unknown_ingest_is_404(self, client):
        assert client.get("/ingest/does-not-exist").status_code == 404


class TestCreateIngestAsset:
    def test_returns_key_and_url(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        response = client.post(f"/ingest/{ingest_id}/asset")
        assert response.status_code == 201
        body = response.json()
        assert body["key"].startswith(f"{ingest_id}/")
        assert body["url"].endswith(body["key"])

    def test_keys_are_unique_per_asset(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        first = client.post(f"/ingest/{ingest_id}/asset").json()["key"]
        second = client.post(f"/ingest/{ingest_id}/asset").json()["key"]
        assert first != second

    def test_staged_asset_is_tracked_on_the_ingest(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        key = client.post(f"/ingest/{ingest_id}/asset").json()["key"]
        assets = client.get(f"/ingest/{ingest_id}").json()["assets"]
        assert assets[key] == {
            "key": key,
            "status": "staged",
            "asset_trn": None,
            "error": None,
        }

    def test_unknown_ingest_is_404(self, client):
        assert client.post("/ingest/does-not-exist/asset").status_code == 404

    def test_rejected_once_committed(self, client, object_storage):
        ingest_id = client.post("/ingest").json()["id"]
        commit(client, ingest_id)
        assert client.post(f"/ingest/{ingest_id}/asset").status_code == 409


class TestCommitIngest:
    def test_unknown_ingest_is_404(self, client):
        assert client.post("/ingest/does-not-exist/commit").status_code == 404

    def test_cannot_commit_twice(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        commit(client, ingest_id)
        assert client.post(f"/ingest/{ingest_id}/commit").status_code == 409

    def test_empty_ingest_completes(self, client):
        ingest_id = client.post("/ingest").json()["id"]
        assert commit(client, ingest_id)["status"] == "completed"

    def test_ingests_staged_asset(self, client, object_storage):
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, IMAGE.read_bytes())

        state = commit(client, ingest_id)

        assert state["status"] == "completed"
        assert state["assets"][key]["status"] == "processed"
        assert state["assets"][key]["asset_trn"].startswith("trn:asset:")
        assert state["assets"][key]["error"] is None

    def test_object_is_copied_to_its_content_addressed_key(
        self, client, object_storage
    ):
        ingest_id = client.post("/ingest").json()["id"]
        data = IMAGE.read_bytes()
        key = stage(client, object_storage, ingest_id, data)

        state = commit(client, ingest_id)

        digest = state["assets"][key]["asset_trn"].removeprefix("trn:asset:")
        assert object_storage.objects[(ASSETS_BUCKET, asset_key(digest))] == data

    def test_staged_object_is_deleted(self, client, object_storage):
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, IMAGE.read_bytes())

        commit(client, ingest_id)

        assert (INGEST_BUCKET, key) not in object_storage.objects

    def test_asset_metadata_lands_in_the_default_graph(
        self, client, object_storage, kg
    ):
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, IMAGE.read_bytes())

        state = commit(client, ingest_id)

        asset_trn = URIRef(state["assets"][key]["asset_trn"])
        description = kg.describe(asset_trn)
        assert description.value(asset_trn, TAMPER.mediaType).toPython() == "image/png"
        assert description.value(asset_trn, TAMPER.width).toPython() == 850

    def test_asset_is_described_only_by_intrinsic_facts(
        self, client, object_storage, kg
    ):
        """Location is derived from the checksum, never recorded in the graph."""
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, IMAGE.read_bytes())

        state = commit(client, ingest_id)

        asset_trn = URIRef(state["assets"][key]["asset_trn"])
        turtle = kg.describe(asset_trn).serialize(format="turtle")
        assert "filePath" not in turtle
        assert str(IMAGE) not in turtle

    def test_identical_uploads_collapse_to_one_asset(self, client, object_storage):
        ingest_id = client.post("/ingest").json()["id"]
        data = IMAGE.read_bytes()
        first = stage(client, object_storage, ingest_id, data)
        second = stage(client, object_storage, ingest_id, data)

        state = commit(client, ingest_id)

        assert state["status"] == "completed"
        assert (
            state["assets"][first]["asset_trn"] == state["assets"][second]["asset_trn"]
        )

    def test_never_uploaded_asset_fails_without_blocking_the_others(
        self, client, object_storage
    ):
        ingest_id = client.post("/ingest").json()["id"]
        good = stage(client, object_storage, ingest_id, IMAGE.read_bytes())
        missing = client.post(f"/ingest/{ingest_id}/asset").json()["key"]

        state = commit(client, ingest_id)

        assert state["status"] == "failed"
        assert state["assets"][good]["status"] == "processed"
        assert state["assets"][missing]["status"] == "failed"
        assert state["assets"][missing]["error"]

    def test_unsupported_media_type_fails_the_asset(self, client, object_storage):
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, b"not a media file")

        state = commit(client, ingest_id)

        assert state["status"] == "failed"
        assert state["assets"][key]["status"] == "failed"
        assert "Unknown media type" in state["assets"][key]["error"]

    def test_failed_asset_keeps_its_staged_object_for_a_retry(
        self, client, object_storage
    ):
        ingest_id = client.post("/ingest").json()["id"]
        key = stage(client, object_storage, ingest_id, b"not a media file")

        commit(client, ingest_id)

        assert (INGEST_BUCKET, key) in object_storage.objects
