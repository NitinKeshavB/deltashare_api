"""FastAPI application for Databricks Delta Sharing recipients."""

import ipaddress
from datetime import datetime
from typing import (
    List,
    Optional,
)

from databricks.sdk.service.sharing import (
    AuthenticationType,
    RecipientInfo,
)
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dbrx_api.recipient import add_recipient_ip
from dbrx_api.recipient import create_recipient_d2d as create_recipient_for_d2d
from dbrx_api.recipient import create_recipient_d2o as create_recipient_for_d2o
from dbrx_api.recipient import delete_recipient
from dbrx_api.recipient import get_recipients as get_recipient_by_name
from dbrx_api.recipient import (
    list_recipients,
    revoke_recipient_ip,
    rotate_recipient_token,
    update_recipient_description,
    update_recipient_expiration_time,
)

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


@APP.put(
    "/recipients/{recipient_name}/tokens/rotate",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
    },
)
async def rotate_recipient_tokens(
    recipient_name: str,
    expire_in_seconds: int = 0,
    response: Response = None,
):
    """Rotate a recipient token for Databricks to opensharing protocol."""

    if expire_in_seconds < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expire_in_seconds must be a non-negative integer",
        )

    recipient = get_recipient_by_name(recipient_name)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = rotate_recipient_token(
        recipient_name=recipient_name,
        expire_in_seconds=expire_in_seconds,
    )

    if response:
        response.status_code = status.HTTP_200_OK
    return recipient


@APP.put(
    "/recipients/{recipient_name}/ipaddress/add",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
    },
)
async def add_client_ip_to_databricks_opensharing(
    recipient_name: str,
    ip_access_list: List[str],
    response: Response = None,
):
    """Add IP to access list for Databricks to opensharing protocol."""
    if not ip_access_list or len(ip_access_list) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP access list cannot be empty",
        )

    # Validate each IP address or CIDR block
    invalid_ips = []
    for ip_str in ip_access_list:
        try:
            # Try parsing as network (supports both single IPs and CIDR)
            ipaddress.ip_network(ip_str.strip(), strict=False)
        except ValueError:
            invalid_ips.append(ip_str)

    if invalid_ips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Invalid IP addresses or CIDR blocks: " f"{', '.join(invalid_ips)}"),
        )

    recipient = get_recipient_by_name(recipient_name)

    if recipient.authentication_type == AuthenticationType.DATABRICKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke IP addresses for DATABRICKS to DATABRICKS type recipient. IP access lists only work with TOKEN authentication.",
        )

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = add_recipient_ip(recipient_name, ip_access_list)

    if response:
        response.status_code = status.HTTP_200_OK
    return recipient


@APP.put(
    "/recipients/{recipient_name}/ipaddress/revoke",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "The following IP addresses are not present in the recipient's IP access list and cannot be revoked",
            "content": {
                "application/json": {
                    "example": {
                        "Message": "The following IP addresses are not present in the recipient's IP access list and cannot be revoked"
                    }
                }
            },
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "IP access list cannot be empty",
            "content": {"application/json": {"example": {"Message": "IP access list cannot be empty"}}},
        },
    },
)
async def revoke_client_ip_from_databricks_opensharing(
    recipient_name: str,
    ip_access_list: List[str],
    response: Response = None,
):
    """revoke IP to access list for Databricks to opensharing protocol."""
    if not ip_access_list or len(ip_access_list) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP access list cannot be empty",
        )

    # Validate each IP address or CIDR block
    invalid_ips = []
    for ip_str in ip_access_list:
        try:
            # Try parsing as network (supports both single IPs and CIDR)
            ipaddress.ip_network(ip_str.strip(), strict=False)
        except ValueError:
            invalid_ips.append(ip_str)

    if invalid_ips:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Invalid IP addresses or CIDR blocks: " f"{', '.join(invalid_ips)}"),
        )

    recipient = get_recipient_by_name(recipient_name)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    if recipient.authentication_type == AuthenticationType.DATABRICKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke IP addresses for DATABRICKS to DATABRICKS type recipient. IP access lists only work with TOKEN authentication.",
        )

    # Check which IPs are not present in the recipient's current IP list
    current_ips = []
    if recipient.ip_access_list and recipient.ip_access_list.allowed_ip_addresses:
        current_ips = recipient.ip_access_list.allowed_ip_addresses

    ips_not_present = [ip for ip in ip_access_list if ip.strip() not in current_ips]

    if ips_not_present:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"The following IP addresses are not present in the recipient's "
                f"IP access list and cannot be revoked: {', '.join(ips_not_present)}"
            ),
        )

    recipient = revoke_recipient_ip(recipient_name, ip_access_list)

    if response:
        response.status_code = status.HTTP_200_OK
    return recipient


@APP.put(
    "/recipients/{recipient_name}/description/update",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Description cannot be empty",
            "content": {"application/json": {"example": {"Message": "Description cannot be empty"}}},
        },
    },
)
async def update_recipients_description(
    recipient_name: str,
    description: str,
    response: Response = None,
):
    """Rotate a recipient token for Databricks to opensharing protocol."""

    if not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description cannot be empty",
        )

    recipient = get_recipient_by_name(recipient_name)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = update_recipient_description(
        recipient_name=recipient_name,
        description=description,
    )

    if response:
        response.status_code = status.HTTP_200_OK
    return recipient


@APP.put(
    "/recipients/{recipient_name}/expiration_time/update",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Expiration time in days cannot be negative or empty",
            "content": {
                "application/json": {"example": {"Message": "Expiration time in days cannot be negative or empty"}}
            },
        },
    },
)
async def update_recipients_expiration_time(
    recipient_name: str,
    expiration_time_in_days: int,
    response: Response = None,
):
    """Rotate a recipient token for Databricks to opensharing protocol."""

    if expiration_time_in_days < 0 or expiration_time_in_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration time in days cannot be negative or empty",
        )

    recipient = get_recipient_by_name(recipient_name)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = update_recipient_expiration_time(
        recipient_name=recipient_name,
        expiration_time=expiration_time_in_days,
    )

    if response:
        response.status_code = status.HTTP_200_OK
    return recipient


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(APP, host="0.0.0.0", port=8000)
