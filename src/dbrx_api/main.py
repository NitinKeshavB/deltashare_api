"""FastAPI application for Databricks Delta Sharing recipients."""

from datetime import datetime
from typing import (
    List,
    Optional,
)

from databricks.sdk.service.sharing import RecipientInfo
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dbrx_api.recipient import create_recipient_d2d as create_recipient_for_d2d
from dbrx_api.recipient import create_recipient_d2o as create_recipient_for_d2o
from dbrx_api.recipient import delete_recipient
from dbrx_api.recipient import get_recipients as get_recipient_by_name
from dbrx_api.recipient import list_recipients

#####################
# --- Constants --- #
#####################

APP = FastAPI()

####################################
# --- Request/response schemas --- #
####################################


# read (cRud)
class RecipientMetadata(BaseModel):
    """Metadata for a recipient."""

    name: str
    auth_type: str
    created_at: datetime


# read (cRud)
class GetRecipientsResponse(BaseModel):
    """Response model for listing recipients."""

    Message: str
    Recipient: List[RecipientInfo]


# read (cRud)
class GetRecipientsQueryParams(BaseModel):
    """Query parameters for listing recipients."""

    prefix: Optional[str] = None
    page_size: Optional[int] = 100

    def __init__(self, **data):
        """Initialize and validate query parameters."""
        super().__init__(**data)
        if self.page_size is not None and self.page_size <= 0:
            raise ValueError("page_size must be greater than 0")


# delete (cruD)
class DeleteRecipientResponse(BaseModel):
    """Response model for deleting a recipient."""

    message: str
    status_code: int


# create/update (CrUd)
class PutFileResponse(BaseModel):
    """Response model for file operations."""

    file_path: str
    message: str


##########################


@APP.get(
    "/recipients/{recipient_name}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"detail": "Recipient not found"}}},
        },
    },
)
async def get_recipients(recipient_name: str) -> RecipientInfo:
    """Get a specific recipient by name."""
    recipient = get_recipient_by_name(recipient_name)

    if recipient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )
    return recipient


@APP.get(
    "/recipients",
    responses={
        status.HTTP_200_OK: {
            "description": "Recipients fetched successfully",
            "content": {
                "application/json": {
                    "example": {
                        "Message": "Fetched 5 recipients!",
                        "Recipient": [],
                    }
                }
            },
        },
        status.HTTP_204_NO_CONTENT: {
            "description": "No recipients found for search criteria",
            "content": {
                "application/json": {
                    "example": {
                        "Message": "No recipients found for search criteria.",
                        "Recipient": [],
                    }
                }
            },
        },
    },
)
async def list_recipients_all(
    query_params: GetRecipientsQueryParams = Depends(),
):
    """List all recipients or with optional prefix filtering."""
    recipients = list_recipients(
        prefix=query_params.prefix,
        max_results=query_params.page_size,
    )

    if len(recipients) == 0:
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content={
                "Message": "No recipients found for search criteria.",
                "Recipient": [],
            },
        )

    message = f"Fetched {len(recipients)} recipients!"
    return GetRecipientsResponse(Message=message, Recipient=recipients)


##########################


@APP.delete(
    "/recipients/{recipient_name}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"detail": "Recipient not found"}}},
        },
    },
)
async def delete_recipient_by_name(recipient_name: str) -> JSONResponse:
    """Delete a Recipient."""
    recipient = get_recipient_by_name(recipient_name)
    if recipient:
        delete_recipient(recipient_name)
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content={"message": "Deleted Recipient successfully!"},
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Recipient not found: {recipient_name}",
    )


@APP.post(
    "/Recipients/d2d/{recipient_name}",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Recipients created successfully",
            "content": {"application/json": {"example": {"Message": "Recipient created successfully!"}}},
        },
        status.HTTP_409_CONFLICT: {
            "description": "Recipient already exists",
            "content": {"application/json": {"example": {"Message": "Recipient already exists"}}},
        },
    },
)
async def create_recipient_databricks_to_databricks(
    recipient_name: str,
    recipient_identifier: str,
    description: str,
    sharing_code: Optional[str] = None,
    response: Response = None,
) -> RecipientInfo:
    """Create a recipient for Databricks to Databricks sharing."""
    recipient = get_recipient_by_name(recipient_name)

    if recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recipient already exists: {recipient_name}",
        )

    recipient = create_recipient_for_d2d(
        recipient_name=recipient_name,
        recipient_identifier=recipient_identifier,
        description=description,
        sharing_code=sharing_code,
    )

    if response:
        response.status_code = status.HTTP_201_CREATED
    return recipient


@APP.post(
    "/Recipients/d2o/{recipient_name}",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Recipients created successfully",
            "content": {"application/json": {"example": {"Message": "Recipient created successfully!"}}},
        },
        status.HTTP_409_CONFLICT: {
            "description": "Recipient already exists",
            "content": {"application/json": {"example": {"Message": "Recipient already exists"}}},
        },
    },
)
async def create_recipient_databricks_to_opensharing(
    recipient_name: str,
    description: str,
    ip_access_list: Optional[List[str]] = None,
    response: Response = None,
) -> RecipientInfo:
    """Create a recipient for Databricks to Databricks sharing."""
    recipient = get_recipient_by_name(recipient_name)

    if recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recipient already exists: {recipient_name}",
        )

    recipient = create_recipient_for_d2o(
        recipient_name=recipient_name,
        description=description,
        ip_access_list=ip_access_list,
    )

    if response:
        response.status_code = status.HTTP_201_CREATED
    return recipient


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(APP, host="0.0.0.0", port=8000)
