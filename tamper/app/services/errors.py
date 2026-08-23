from tamper.core.identifiers import URIRef


class ResourceNotFoundError(Exception):
    def __init__(self, resource_id: URIRef):
        super().__init__(f"Resource {resource_id.n3()} not found")


class ResourceAlreadyExistsError(Exception):
    def __init__(self, resource_id: URIRef):
        super().__init__(f"Resource {resource_id.n3()} already exists")
