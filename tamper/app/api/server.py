import logging

from fastapi import FastAPI
from contextlib import asynccontextmanager

from tamper.app.config import get_settings
from tamper.app.ingest import IngestQueue
from tamper.app.ingest.ingest_worker import SimpleIngestWorker
from .ingest_router import router as ingest_router
from .sparql_router import router as sparql_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level="INFO")
    settings = get_settings()
    app.state.kg = settings.get_kg()
    app.state.asset_storage = settings.get_asset_storage()
    app.state.ingest_storage = settings.get_ingest_storage()
    app.state.ingests = {}

    ingest_worker = SimpleIngestWorker(
        asset_storage=app.state.asset_storage,
        ingest_storage=app.state.ingest_storage,
        kg=app.state.kg,
    )

    app.state.ingest_queue = IngestQueue(ingest_worker)
    await app.state.ingest_queue.start()
    yield
    await app.state.ingest_queue.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(ingest_router)
app.include_router(sparql_router)
