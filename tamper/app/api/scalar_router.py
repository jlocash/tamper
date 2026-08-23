from fastapi import APIRouter
from scalar_fastapi import Layout, get_scalar_api_reference

router = APIRouter()


@router.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        # openapi_url=app.openapi_url,
        layout=Layout.MODERN,
        hide_models=True,
        default_open_all_tags=True,
    )
