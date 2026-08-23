import secrets

from rdflib import URIRef


class TamperURI(URIRef):
    def __new__(cls, resource_type: str, resource_id: str):
        uri = f"trn:{resource_type}:{resource_id}"
        return super().__new__(cls, uri)

    @property
    def resource_type(self) -> str:
        return self.split(":", 2)[1]

    @property
    def resource_id(self) -> str:
        return self.split(":", 2)[2]


class AssetURI(TamperURI):
    def __new__(cls, resource_id: str):
        return super().__new__(cls, "asset", resource_id)


class StreamURI(TamperURI):
    def __new__(cls, resource_id: str):
        return super().__new__(cls, "stream", resource_id)


class OperationURI(TamperURI):
    def __new__(cls, resource_id: str | None = None):
        if resource_id is None:
            resource_id = secrets.token_urlsafe(12)
        return super().__new__(cls, "operation", resource_id)


class DatasetURI(TamperURI):
    def __new__(cls, resource_id: str | None = None):
        if resource_id is None:
            resource_id = secrets.token_urlsafe(12)
        return super().__new__(cls, "dataset", resource_id)


class PlanURI(TamperURI):
    def __new__(cls, resource_id: str | None = None):
        if resource_id is None:
            resource_id = secrets.token_urlsafe(12)
        return super().__new__(cls, "plan", resource_id)


class PlanStepURI(TamperURI):
    def __new__(cls, resource_id: str | None = None):
        if resource_id is None:
            resource_id = secrets.token_urlsafe(12)
        return super().__new__(cls, "plan-step", resource_id)


class PlanVariableURI(TamperURI):
    def __new__(cls, resource_id: str | None = None):
        if resource_id is None:
            resource_id = secrets.token_urlsafe(12)
        return super().__new__(cls, "plan-variable", resource_id)
