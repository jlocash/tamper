import os
import tempfile
from abc import abstractmethod, ABC
from pathlib import Path
from uuid import uuid4

from rdflib import Graph, Node
from rdflib.term import URIRef


class Operation(ABC):
    def __init__(self):
        self.subject = URIRef(f"operation://{uuid4()}")

    def transform(self, input_asset_file: Path, output_asset_file: Path):
        """
        Executes the media operation given the input file, and writes the result to the output file

        :param input_asset_file: Path to the input media asset
        :param output_asset_file: Path to write the output media asset
        """
        raise NotImplementedError

    def generate(self, output_asset_file: Path):
        """
        Executes the media operation and writes the generated media asset to the output file

        :param output_asset_file: Path to write the output media asset
        """
        raise NotImplementedError

    @abstractmethod
    def graph(self) -> Graph:
        """
        Serializes the operation as a `rdflib.Graph`
        """
        pass

    @classmethod
    @abstractmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        """
        Copies the operation parameters from the given graph and subject node

        :param graph: The graph to copy the operation from
        :param subject: The subject node to copy the operation from
        """
        pass
