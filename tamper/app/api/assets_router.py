from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse

from tamper.app.api.dependencies import AssetStorageDep, KnowledgeGraphDep
from tamper.core.assets import AssetURI, MediaAsset

router = APIRouter(tags=["assets"])


@router.get(
    "/assets/{checksum}/content",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def get_asset_content(
    checksum: str, asset_storage: AssetStorageDep, kg: KnowledgeGraphDep
):
    asset_uri = AssetURI(checksum)
    asset_description = kg.describe(asset_uri)
    if len(asset_description) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    asset = MediaAsset(asset_description, asset_uri)
    presigned_url = asset_storage.presign_get(checksum, asset.media_type)
    return RedirectResponse(
        url=presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
