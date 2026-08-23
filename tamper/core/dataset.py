from datetime import datetime
from rdflib import DCTERMS, PROV, XSD, URIRef

from tamper.core import MediaAsset
from tamper.vocabularies import TAMPER
from ._common import MappedProperty, Resource


class Dataset(Resource):
    """A dataset is an RDF graph describing media assets"""

    __rdf_type__ = TAMPER.Dataset

    title: MappedProperty[str] = MappedProperty(DCTERMS.title, XSD.string)
    description: MappedProperty[str] = MappedProperty(DCTERMS.description, XSD.string)
    created: MappedProperty[datetime] = MappedProperty(DCTERMS.created, XSD.dateTime)
    modified: MappedProperty[datetime] = MappedProperty(DCTERMS.modified, XSD.dateTime)
    creator: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.creator, XSD.string)
    publisher: MappedProperty[str | URIRef] = MappedProperty(
        DCTERMS.publisher, XSD.string
    )
    license: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.license, XSD.string)
    rights: MappedProperty[str | URIRef] = MappedProperty(DCTERMS.rights, XSD.string)
    language: MappedProperty[str | URIRef] = MappedProperty(
        DCTERMS.language, XSD.string
    )

    @property
    def members(self) -> list[MediaAsset]:
        return [
            MediaAsset(self.graph, asset.identifier)
            for asset in self.objects(PROV.hadMember)
        ]

    def add_member(self, asset: MediaAsset | URIRef):
        self.add(PROV.hadMember, asset)
