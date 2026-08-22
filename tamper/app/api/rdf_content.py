
from fastapi import HTTPException, Response, status
from rdflib import Graph
from rdflib.query import Result


ASK_FORMATS = {
    "application/sparql-results+json": "json",
    "application/sparql-results+xml": "xml",
}

SELECT_FORMATS = {**ASK_FORMATS, "text/csv": "csv"}

GRAPH_RESPONSE_FORMATS = {
    "text/turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/rdf+xml": "xml",
    "application/n-triples": "nt",
    "application/n-quads": "nq",
}

RESPONSE_FORMATS = {
    "ASK": ASK_FORMATS,
    "SELECT": SELECT_FORMATS,
    "CONSTRUCT": GRAPH_RESPONSE_FORMATS,
    "DESCRIBE": GRAPH_RESPONSE_FORMATS,
}


DEFAULT_GRAPH_RESPONSE_FORMAT = "text/turtle"

DEFAULT_RESPONSE_FORMAT = {
    "SELECT": "application/sparql-results+json",
    "ASK": "application/sparql-results+json",
    "CONSTRUCT": DEFAULT_GRAPH_RESPONSE_FORMAT,
    "DESCRIBE": DEFAULT_GRAPH_RESPONSE_FORMAT,
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


class RDFResponse(Response):
    """Custom response class for handling RDF graphs.
    The default serialization format is tex/turtle, but
    an alternative format can be set via the `accepts` parameter
    of the init method"""

    def __init__(
        self,
        content: Graph,
        status_code=status.HTTP_200_OK,
        accepts: str | None = None,
    ):
        media_type = _negotiate(
            accepts, GRAPH_RESPONSE_FORMATS, DEFAULT_GRAPH_RESPONSE_FORMAT
        )
        super().__init__(
            content=content,
            status_code=status_code,
            headers={"Vary": "Accept"},
            media_type=media_type,
            background=None,
        )

    def render(self, graph: Graph):
        return graph.serialize(format=GRAPH_RESPONSE_FORMATS[self.media_type]).encode()


class SPARQLResponse(Response):
    """
    Custom FastAPI Response class for handling SPARQL query results.
    The content should be an rdflib.query.Result, and the media_type
    will be negotiated based on the value of the `accepts` parameter
    and the query result type.
    """

    def __init__(
        self,
        content: Result,
        status_code=status.HTTP_200_OK,
        accepts: str | None = None,
    ):
        query_type = content.type
        media_type = _negotiate(
            accepts,
            RESPONSE_FORMATS[query_type],
            DEFAULT_RESPONSE_FORMAT[query_type],
        )
        super().__init__(
            content=content,
            status_code=status_code,
            headers={"Vary": "Accept"},
            media_type=media_type,
            background=None,
        )

    def render(self, query_result: Result):
        return query_result.serialize(
            format=RESPONSE_FORMATS[query_result.type][self.media_type]
        )


def rdf_route_extras(ok_status_code: int):
    return {
        "status_code": ok_status_code,
        "response_class": RDFResponse,
        "responses": {
            status.HTTP_200_OK: {
                "content": {fmt: {} for fmt in GRAPH_RESPONSE_FORMATS}
            },
            status.HTTP_406_NOT_ACCEPTABLE: {
                "description": "No acceptable response media type"
            },
        },
    }


def sparql_route_extras():
    return {
        "status_code": status.HTTP_200_OK,
        "response_class": SPARQLResponse,
        "responses": {
            status.HTTP_200_OK: {
                fmt: {}
                for fmt in {**ASK_FORMATS, **SELECT_FORMATS, **GRAPH_RESPONSE_FORMATS}
            },
            status.HTTP_406_NOT_ACCEPTABLE: {
                "description": "No acceptable response media type"
            },
        },
    }
