import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from tamper.app.config import get_settings
from tamper.app.ingest import IngestQueue
from tamper.app.ingest.ingest_worker import SimpleIngestWorker
from .assets_router import router as assets_router
from .ingest_router import router as ingest_router
from .sparql_router import router as sparql_router
from .datasets_router import router as dataset_router
from .scalar_router import router as scalar_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
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


app = FastAPI(title="Tamper API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(assets_router)
app.include_router(ingest_router)
app.include_router(sparql_router)
app.include_router(dataset_router)
app.include_router(scalar_router)
