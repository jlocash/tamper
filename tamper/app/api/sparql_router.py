from dataclasses import dataclass
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from rdflib import URIRef

from tamper.app.api.rdf_content import AcceptHeader, sparql_route_extras, SPARQLResponse
from tamper.app.api.dependencies import KnowledgeGraphDep

from tamper.app.api.schemas import URI
from tamper.app.kg.knowledge_graph import KnowledgeGraph, MalformedQueryError

router = APIRouter(tags=["sparql"])


@dataclass
class QueryContext:
    default_graph_uris: list[URIRef]
    named_graph_uris: list[URIRef]


def get_query_context(
    default_graph_uris: list[URI] = Query(default=[], alias="default-graph-uri"),
    named_graph_uris: list[URI] = Query(default=[], alias="named-graph-uri"),
):
    return QueryContext(
        default_graph_uris=default_graph_uris,
        named_graph_uris=named_graph_uris,
    )


QueryContextDep = Annotated[QueryContext, Depends(get_query_context)]


def _sparql(kg: KnowledgeGraph, query: str, query_context: QueryContext, accept: str):
    try:
        result = kg.query(
            query,
            default_graph_uris=query_context.default_graph_uris,
            named_graph_uris=query_context.named_graph_uris,
        )
    except MalformedQueryError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed query"
        )

    return SPARQLResponse(content=result, accepts=accept)


@router.get("/sparql", **sparql_route_extras())
async def sparql_get(
    kg: KnowledgeGraphDep,
    query: str,
    query_context: QueryContextDep,
    accept: AcceptHeader,
):
    return _sparql(kg, query, query_context, accept)


@router.post("/sparql", **sparql_route_extras())
async def sparql_post(
    kg: KnowledgeGraphDep,
    query: Annotated[str, Body(media_type="application/sparql-query")],
    query_context: QueryContextDep,
    accept: AcceptHeader,
):
    return _sparql(kg, query, query_context, accept)
