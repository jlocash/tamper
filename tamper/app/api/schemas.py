from typing import Annotated

from pydantic import BaseModel, Field, PlainValidator
from rdflib import Graph, URIRef

from tamper.core import Dataset
from tamper.core.identifiers import DatasetURI

URI = Annotated[URIRef, PlainValidator(URIRef, json_schema_input_type=str)]


class CreateDataset(BaseModel):
    title: str
    description: str
    slug: str
    members: list[URI] = Field(default_factory=list)

    def get_uri(self) -> URIRef:
        return DatasetURI(self.slug)

    def as_model(self, graph: Graph | None = None) -> Dataset:
        if graph is None:
            graph = Graph()

        ds = Dataset.new(graph, self.get_uri())
        ds.title = self.title
        ds.description = self.description
        for asset_uri in self.members:
            ds.add_member(asset_uri)
        return ds
