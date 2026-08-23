from fastapi import APIRouter, HTTPException, status
from rdflib import Graph

from tamper.core.identifiers import DatasetURI
from .rdf_content import rdf_route_extras, RDFResponse, AcceptHeader
from .dependencies import KnowledgeGraphDep
from .schemas import CreateDataset

from tamper.app.services import dataset

router = APIRouter()


@router.get("/datasets", **rdf_route_extras(status.HTTP_200_OK))
async def list_datasets(kg: KnowledgeGraphDep, accept: AcceptHeader):
    datasets = dataset.list_datasets(kg)
    if len(datasets) > 0:
        return RDFResponse(datasets[0].graph, status.HTTP_200_OK, accept)
    return RDFResponse(Graph(), status.HTTP_204_NO_CONTENT, accept)


@router.post("/datasets", **rdf_route_extras(status.HTTP_201_CREATED))
async def create_dataset(
    body: CreateDataset, kg: KnowledgeGraphDep, accept: AcceptHeader
):
    try:
        ds = dataset.create_dataset(kg, body)
    except dataset.DatasetAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return RDFResponse(ds.graph, status.HTTP_201_CREATED, accept)


@router.get("/dataset/{slug}", **rdf_route_extras(status.HTTP_200_OK))
async def get_dataset(slug: str, kg: KnowledgeGraphDep, accept: AcceptHeader):
    dataset_uri = DatasetURI(slug)
    try:
        ds = dataset.get_dataset(kg, dataset_uri)
    except dataset.DatasetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return RDFResponse(ds.graph, status.HTTP_200_OK, accept)
