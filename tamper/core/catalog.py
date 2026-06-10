from datetime import datetime

from rdflib import URIRef, DCAT, DCTERMS, XSD
from ._common import MappedProperty, Resource
from .dataset import Dataset


class Catalog(Resource):
    """A catalog is a record/collection of datasets"""

    __rdf_type__ = DCAT.Catalog

    title: MappedProperty[str] = MappedProperty(DCTERMS.title, XSD.string)
    description: MappedProperty[str] = MappedProperty(DCTERMS.description, XSD.string)
    created: MappedProperty[datetime] = MappedProperty(DCTERMS.created, XSD.dateTime)
    modified: MappedProperty[datetime] = MappedProperty(DCTERMS.modified, XSD.dateTime)

    def add_dataset(self, identifier: URIRef):
        self.add(DCAT.dataset, identifier)

    def datasets(self) -> list[Dataset]:
        datasets = []
        for ds in self.objects(DCAT.dataset):
            datasets.append(Dataset(self.graph, ds.identifier))
        return datasets
