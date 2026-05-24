import os
from os import PathLike
from pathlib import Path

import ray
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from rdflib import Graph, URIRef

from tamper.app.kg.local import LocalKnowledgeGraph, InconsistencyError
from tamper.assets import build_asset_from_file
from tamper.core.ontology import ProvOntology
from tamper.namespaces import TAMPER
from tamper.core import Ontology
from tamper.ops.image import CompressImage, AddGaussianNoise
from tamper.utils.make_tarball import make_tarball

ray.init()

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
def compress_image(output_dir: str, image_uri: str, quality_factor: int) -> str:
    """
    Runs an image compression operation on the given URI. The provided image URI must resolve to an image asset in the
    knowledge graph, AND it must have an associated file path. Assets not containing a file path are not supported.

    :param output_dir: The directory where the compressed image will be stored.
    :param image_uri: The URI of the image to compress. The URI must resolve to an image asset in the knowledge graph.
    :param quality_factor: The quality factor (0-100) for the compression.
    :return: The subgraph created as a result of the compression operation, serialized in Turtle format.
    """
    op_actor = CompressImage.remote(kg.dataset.default_graph, output_dir, URIRef(image_uri), quality_factor)
    try:
        future = op_actor.apply.remote()
        subgraph, new_image_uri = ray.get(future)
        kg.insert_statements_default(subgraph)
        kg.commit()
        return subgraph.serialize(format="turtle")
    except (InconsistencyError, ValueError) as e:
        raise ToolError(str(e)) from e


@mcp.tool
def add_gaussian_noise(output_dir: str, image_uri: str, mean: float, std: float) -> str:
    """
    Adds Gaussian noise to an image. The image URI must resolve to an image asset in the knowledge graph, AND it must
    have an associated file path. Assets not containing a file path are not supported.

    :param output_dir: The directory where the compressed image will be stored.
    :param image_uri: The URI of the image to compress. The URI must resolve to an image asset in the knowledge graph.
    :param mean: The mean value of the Gaussian noise.
    :param std: The standard deviation of the Gaussian noise.
    :return: The subgraph created as a result of the compression operation, serialized in Turtle format.
    """

    op_actor = AddGaussianNoise.remote(kg.dataset.default_graph, output_dir, URIRef(image_uri), mean, std)
    try:
        future = op_actor.apply.remote()
        subgraph, new_image_uri = ray.get(future)
        kg.insert_statements_default(subgraph)
        kg.commit()
        return subgraph.serialize(format="turtle")
    except (InconsistencyError, ValueError) as e:
        raise ToolError(str(e)) from e


@mcp.tool
def sparql_query(sparql_query_str: str) -> str | bool:
    """
    Executes a (read-only) SPARQL query against the knowledge graph. The vocabulary should ALWAYS be fetched prior to
    executing any queries. Available vocabularies are exposed via MCP resources at:
    - ontology://tamper (the Tamper core ontology)
    - ontology://prov-o (the PROV-O ontology)

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


@mcp.tool
def export_dataset(output_filename: PathLike[str]) -> None:
    """
    Exports the RDF dataset and all referenced media asset files to a tarball archive.
    The dataset is stored in TriG format in <archive root>/dataset.trig.
    Media assets are stored under <archive root>/assets and are renamed to <checksum>.<ext>.

    :param output_filename: The filename of the output tarball.
    """
    try:
        make_tarball(kg.dataset, output_filename)
    except Exception as e:
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
