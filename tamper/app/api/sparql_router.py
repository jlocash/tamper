from dataclasses import dataclass
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Header,
    Query,
    Response,
    status,
)
from pydantic import PlainValidator
from rdflib import URIRef

from tamper.app.api.dependencies import KnowledgeGraphDep

from tamper.app.kg.knowledge_graph import KnowledgeGraph, MalformedQueryError

router = APIRouter(tags=["sparql"])

ASK_FORMATS = {
    "application/sparql-results+json": "json",
    "application/sparql-results+xml": "xml",
}

SELECT_FORMATS = {**ASK_FORMATS, "text/csv": "csv"}

CONSTRUCT_FORMATS = {
    "text/turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/rdf+xml": "xml",
    "application/n-triples": "nt",
    "application/n-quads": "nq",
}

DESCRIBE_FORMATS = CONSTRUCT_FORMATS

RESPONSE_FORMATS = {
    "ASK": ASK_FORMATS,
    "SELECT": SELECT_FORMATS,
    "CONSTRUCT": CONSTRUCT_FORMATS,
    "DESCRIBE": DESCRIBE_FORMATS,
}

DEFAULT_RESPONSE_FORMATS = {
    "SELECT": "application/sparql-results+json",
    "ASK": "application/sparql-results+json",
    "CONSTRUCT": "text/turtle",
    "DESCRIBE": "text/turtle",
}

SPARQL_RESPONSE_TYPES = {
    k: {}
    for k in {**ASK_FORMATS, **SELECT_FORMATS, **CONSTRUCT_FORMATS, **DESCRIBE_FORMATS}
}


def _negotiate(accept: str | None, formats: dict[str, str], default: str) -> str:
    if not accept:
        return default
    for entry in accept.split(","):
        media_type = entry.split(";")[0].strip()
        if media_type in formats:
            return media_type
        if media_type == "*/*":
            return default
    raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE)


@dataclass
class QueryContext:
    default_graph_uris: list[URIRef]
    named_graph_uris: list[URIRef]


URI = Annotated[URIRef, PlainValidator(URIRef, json_schema_input_type=str)]


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

    media_type = _negotiate(
        accept, RESPONSE_FORMATS[result.type], DEFAULT_RESPONSE_FORMATS[result.type]
    )

    resp_content = result.serialize(format=RESPONSE_FORMATS[result.type][media_type])
    resp = Response(content=resp_content, media_type=media_type)
    resp.headers["Vary"] = "Accept"
    return resp


@router.get(
    "/sparql",
    status_code=status.HTTP_200_OK,
    response_class=Response,
    responses={
        status.HTTP_200_OK: {"content": SPARQL_RESPONSE_TYPES},
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "No acceptable response media type"
        },
    },
)
async def sparql_get(
    kg: KnowledgeGraphDep,
    query: str,
    query_context: QueryContextDep,
    accept: Annotated[str | None, Header()] = None,
):
    return _sparql(kg, query, query_context, accept)


@router.post(
    "/sparql",
    status_code=status.HTTP_200_OK,
    response_class=Response,
    responses={
        status.HTTP_200_OK: {"content": SPARQL_RESPONSE_TYPES},
        status.HTTP_406_NOT_ACCEPTABLE: {
            "description": "No acceptable response media type"
        },
    },
)
async def sparql_post(
    kg: KnowledgeGraphDep,
    query: Annotated[str, Body(media_type="application/sparql-query")],
    query_context: QueryContextDep,
    accept: Annotated[str | None, Header()] = None,
):
    return _sparql(kg, query, query_context, accept)
