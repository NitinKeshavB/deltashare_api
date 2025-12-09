from databricks.sdk.service.sharing import RecipientInfo
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)

from dbrx_api.dltshr.recipient import get_recipients as get_recipient_by_name
from dbrx_api.settings import Settings

ROUTER_SHARE = APIRouter(tags=["Shares"])


@ROUTER_SHARE.get(
    "/recipients/{recipient_name}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"detail": "Recipient not found"}}},
        },
    },
)
async def get_shares(request: Request, recipient_name: str, response: Response) -> RecipientInfo:
    """Get a specific recipient by name."""
    settings: Settings = request.app.state.settings
    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    if recipient:
        response.status_code = status.HTTP_200_OK
    return recipient
