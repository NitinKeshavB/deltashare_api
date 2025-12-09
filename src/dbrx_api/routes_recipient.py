import ipaddress
from typing import (
    List,
    Optional,
)

from databricks.sdk.service.sharing import (
    AuthenticationType,
    RecipientInfo,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse

from dbrx_api.dltshr.recipient import add_recipient_ip
from dbrx_api.dltshr.recipient import create_recipient_d2d as create_recipient_for_d2d
from dbrx_api.dltshr.recipient import create_recipient_d2o as create_recipient_for_d2o
from dbrx_api.dltshr.recipient import delete_recipient
from dbrx_api.dltshr.recipient import get_recipients as get_recipient_by_name
from dbrx_api.dltshr.recipient import (
    list_recipients,
    revoke_recipient_ip,
    rotate_recipient_token,
    update_recipient_description,
    update_recipient_expiration_time,
)
from dbrx_api.schemas import (
    GetRecipientsQueryParams,
    GetRecipientsResponse,
)
from dbrx_api.settings import Settings

ROUTER_RECIPIENT = APIRouter(tags=["Recipients"])


@ROUTER_RECIPIENT.get(
    "/recipients/{recipient_name}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"detail": "Recipient not found"}}},
        },
    },
)
async def get_recipients(request: Request, recipient_name: str, response: Response) -> RecipientInfo:
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


##########################


@ROUTER_RECIPIENT.get(
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
                        "detail": "No recipients found for search criteria.",
                    }
                }
            },
        },
    },
)
async def list_recipients_all(
    request: Request, response: Response, query_params: GetRecipientsQueryParams = Depends()
):
    """List all recipients or with optional prefix filtering."""
    settings: Settings = request.app.state.settings

    recipients = list_recipients(
        prefix=query_params.prefix,
        max_results=query_params.page_size,
        dltshr_workspace_url=settings.dltshr_workspace_url,
    )

    if len(recipients) == 0:
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT, content={"detail": "No recipients found for search criteria."}
        )

    response.status_code = status.HTTP_200_OK
    message = f"Fetched {len(recipients)} recipients!"
    return GetRecipientsResponse(Message=message, Recipient=recipients)


##########################


@ROUTER_RECIPIENT.delete(
    "/recipients/{recipient_name}",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"detail": "Recipient not found"}}},
        },
        status.HTTP_200_OK: {
            "description": "Deleted Recipient successfully!",
            "content": {"application/json": {"example": {"detail": "Deleted Recipient successfully!"}}},
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Permission denied to delete recipient",
            "content": {
                "application/json": {
                    "example": {"detail": "Permission denied to delete recipient as user is not the owner"}
                }
            },
        },
    },
)
async def delete_recipient_by_name(request: Request, recipient_name: str):
    """Delete a Recipient."""
    settings: Settings = request.app.state.settings
    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)
    if recipient:
        response = delete_recipient(recipient_name, settings.dltshr_workspace_url)
        if response == "User is not an owner of Recipient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied to delete recipient as user is not the owner: {recipient_name}",
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Deleted Recipient successfully!"},
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Recipient not found: {recipient_name}",
    )


##########################


@ROUTER_RECIPIENT.post(
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
    request: Request,
    response: Response,
    recipient_name: str,
    recipient_identifier: str,
    description: str,
    sharing_code: Optional[str] = None,
) -> RecipientInfo:
    """Create a recipient for Databricks to Databricks sharing."""
    settings: Settings = request.app.state.settings
    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

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
        dltshr_workspace_url=settings.dltshr_workspace_url,
    )

    if isinstance(recipient, str) and recipient.startswith("Invalid recipient_identifier"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=recipient,
        )

    if "already exists with same sharing identifier" in recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=recipient,
        )

    if recipient:
        response.status_code = status.HTTP_201_CREATED
    return recipient


##########################


@ROUTER_RECIPIENT.post(
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
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid IP addresses or CIDR blocks",
            "content": {"application/json": {"example": {"Message": "Invalid IP addresses or CIDR blocks"}}},
        },
    },
)
async def create_recipient_databricks_to_opensharing(
    request: Request,
    response: Response,
    recipient_name: str,
    description: str,
    ip_access_list: Optional[List[str]] = None,
) -> RecipientInfo:
    """Create a recipient for Databricks to Databricks sharing."""
    settings: Settings = request.app.state.settings
    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

    if recipient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recipient already exists: {recipient_name}",
        )

    # Validate IP access list if provided
    if ip_access_list and len(ip_access_list) > 0:
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

    recipient = create_recipient_for_d2o(
        recipient_name=recipient_name,
        description=description,
        ip_access_list=ip_access_list,
        dltshr_workspace_url=settings.dltshr_workspace_url,
    )

    if recipient:
        response.status_code = status.HTTP_201_CREATED
    return recipient


##########################


@ROUTER_RECIPIENT.put(
    "/recipients/{recipient_name}/tokens/rotate",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "expire_in_seconds must be a non-negative integer",
            "content": {
                "application/json": {"example": {"Message": "Iexpire_in_seconds must be a non-negative integer"}}
            },
        },
    },
)
async def rotate_recipient_tokens(
    request: Request, response: Response, recipient_name: str, expire_in_seconds: int = 0
) -> RecipientInfo:
    """Rotate a recipient token for Databricks to opensharing protocol."""
    settings: Settings = request.app.state.settings
    if expire_in_seconds < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expire_in_seconds must be a non-negative integer",
        )

    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = rotate_recipient_token(
        recipient_name=recipient_name,
        expire_in_seconds=expire_in_seconds,
        dltshr_workspace_url=settings.dltshr_workspace_url,
    )

    if isinstance(recipient, str) and "Cannot extend the token expiration time" in recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=recipient,
        )
    elif isinstance(recipient, str) and "Recipient already has maximum number of active tokens" in recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=recipient,
        )
    else:
        response.status_code = status.HTTP_200_OK
        return recipient


##########################


@ROUTER_RECIPIENT.put(
    "/recipients/{recipient_name}/ipaddress/add",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "IP access list cannot be empty",
            "content": {"application/json": {"example": {"Message": "IP access list cannot be empty"}}},
        },
    },
)
async def add_client_ip_to_databricks_opensharing(
    request: Request, recipient_name: str, ip_access_list: List[str], response: Response
):
    """Add IP to access list for Databricks to opensharing protocol."""
    settings: Settings = request.app.state.settings

    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

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

    recipient = add_recipient_ip(recipient_name, ip_access_list, settings.dltshr_workspace_url)

    if recipient:
        response.status_code = status.HTTP_200_OK
    return recipient


@ROUTER_RECIPIENT.put(
    "/recipients/{recipient_name}/ipaddress/revoke",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "IP access list cannot be empty",
            "content": {"application/json": {"example": {"Message": "IP access list cannot be empty"}}},
        },
    },
)
async def revoke_client_ip_from_databricks_opensharing(
    request: Request, recipient_name: str, ip_access_list: List[str], response: Response
) -> RecipientInfo:
    """revoke IP to access list for Databricks to opensharing protocol."""
    settings: Settings = request.app.state.settings

    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

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

    recipient = revoke_recipient_ip(recipient_name, ip_access_list, settings.dltshr_workspace_url)

    if recipient:
        response.status_code = status.HTTP_200_OK
    return recipient


@ROUTER_RECIPIENT.put(
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
        status.HTTP_403_FORBIDDEN: {
            "description": "Permission denied to update description of recipient as user is not the owner",
            "content": {
                "application/json": {
                    "example": {
                        "Message": "Permission denied to update description of recipient as user is not the owner"
                    }
                }
            },
        },
    },
)
async def update_recipients_description(
    request: Request,
    recipient_name: str,
    description: str,
    response: Response,
) -> RecipientInfo:
    """Rotate a recipient token for Databricks to opensharing protocol."""
    settings: Settings = request.app.state.settings

    if not description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description cannot be empty",
        )

    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    recipient = update_recipient_description(
        recipient_name=recipient_name,
        description=description,
        dltshr_workspace_url=settings.dltshr_workspace_url,
    )
    if isinstance(recipient, str) and recipient == "User is not an owner of Recipient":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permission denied to update description of recipient: " f"{recipient_name} as user is not the owner"
            ),
        )
    else:
        response.status_code = status.HTTP_200_OK
        return recipient


@ROUTER_RECIPIENT.put(
    "/recipients/{recipient_name}/expiration_time/update",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Recipient not found",
            "content": {"application/json": {"example": {"Message": "Recipient not found"}}},
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Expiration time in days cannot be negative or empty or zero",
            "content": {
                "application/json": {
                    "example": {"Message": "Expiration time in days cannot be negative or empty or zero"}
                }
            },
        },
    },
)
async def update_recipients_expiration_time(
    request: Request, recipient_name: str, expiration_time_in_days: int, response: Response
) -> RecipientInfo:
    """Rotate a recipient token for Databricks to opensharing protocol."""
    settings: Settings = request.app.state.settings

    recipient = get_recipient_by_name(recipient_name, settings.dltshr_workspace_url)

    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient not found: {recipient_name}",
        )

    elif recipient.authentication_type == AuthenticationType.DATABRICKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update expiration time for DATABRICKS to DATABRICKS type recipient. Expiration time only works with TOKEN authentication.",
        )
    elif expiration_time_in_days <= 0 or expiration_time_in_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration time in days cannot be negative or empty",
        )

    else:
        recipient = update_recipient_expiration_time(
            recipient_name=recipient_name,
            expiration_time=expiration_time_in_days,
            dltshr_workspace_url=settings.dltshr_workspace_url,
        )

        if recipient:
            response.status_code = status.HTTP_200_OK
        return recipient
