from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from tamper.app.api.dependencies import AssetStorageDep, KnowledgeGraphDep
from tamper.app.api.rdf_content import AcceptHeader, RDFResponse, rdf_route_extras
from tamper.app.services import assets
from tamper.core import MediaAsset
from tamper.core.assets import AssetURI

router = APIRouter(tags=["assets"])


def requires_asset(checksum: str, kg: KnowledgeGraphDep) -> MediaAsset:
    asset_uri = AssetURI(checksum)
    try:
        return assets.get_asset(kg, asset_uri)
    except assets.AssetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/assets/{checksum}", **rdf_route_extras(status.HTTP_200_OK))
async def get_asset(
    asset: Annotated[MediaAsset, Depends(requires_asset)],
    accept: AcceptHeader,
):
    return RDFResponse(content=asset.graph, accepts=accept)


@router.get(
    "/assets/{checksum}/content",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def get_asset_content(
    checksum: str,
    asset: Annotated[MediaAsset, Depends(requires_asset)],
    asset_storage: AssetStorageDep,
):
    presigned_url = asset_storage.presign_get(checksum, asset.media_type)
    return RedirectResponse(
        url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
