import os
from os import PathLike
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rdflib import Graph

from tamper.app.kg.local import LocalKnowledgeGraph, InconsistencyError
from tamper.assets import build_asset_from_file
from tamper.core.ontology import ProvOntology
from tamper.namespaces import TAMPER
from tamper.core import Ontology

mcp = FastMCP("Tamper MCP Server")

dataset_file = os.environ['TAMPER_DATASET_FILE']
kg = LocalKnowledgeGraph(Path(dataset_file))


@mcp.tool
def track_media_asset(file_path: PathLike[str]) -> str:
    """
    Tracks a media asset in the knowledge graph.
    :param file_path: The file path of the media asset.
    :return: The serialized media asset graph in Turtle format.
    """
    g = Graph()
    build_asset_from_file(g, file_path)
    kg.insert_statements_default(g)
    kg.commit()
    return g.serialize(format="turtle")


@mcp.tool
def sparql_query(sparql_query_str: str) -> str | bool:
    """
    Executes a (read-only) SPARQL query against the knowledge graph.
    :param sparql_query_str: The SPARQL query to execute. Must be one of the following: SELECT, ASK, CONSTRUCT, DESCRIBE.
    :return: In the case of a CONSTRUCT query, the result is the graph serialized in Turtle format. Otherwise, the result is a JSON object containing the results of the query.
    """
    result = kg.query(sparql_query_str)
    if result.graph:
        result.graph.bind("tamper", TAMPER)
        return result.graph.serialize(format="turtle")
    return result.serialize(format="json")


@mcp.tool
def sparql_update(sparql_update_str: str) -> None:
    """
    Executes a SPARQL update against the knowledge graph.

    :param sparql_update_str: The SPARQL update to execute.
    :return: None. Throws if the update fails.
    """
    try:
        kg.update(sparql_update_str)
        kg.commit()
    except InconsistencyError as e:
        raise ToolError(str(e)) from e


@mcp.resource("ontology://tamper")
def get_ontology() -> str:
    """
    Retrieves the Tamper ontology.
    :return: The Tamper ontology serialized in Turtle format.
    """
    return Ontology.serialize(format="turtle")


@mcp.resource("ontology://prov-o")
def get_prov_ontology() -> str:
    """
    Retrieves the PROV-O ontology.

    :return: The PROV-O ontology serialized in Turtle format.
    """
    return ProvOntology.serialize(format="turtle")


if __name__ == "__main__":
    mcp.run()
