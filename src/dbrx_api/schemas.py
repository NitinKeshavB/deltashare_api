####################################
# --- Request/response schemas --- #
####################################

from datetime import datetime
from typing import (
    List,
    Optional,
)

from databricks.sdk.service.sharing import (
    RecipientInfo,
    ShareInfo,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)


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


class GetSharesResponse(BaseModel):
    """Response model for listing shares."""

    Message: str
    Share: List[ShareInfo]


# read (cRud)
class GetRecipientsQueryParams(BaseModel):
    """Query parameters for listing recipients."""

    prefix: Optional[str] = None
    page_size: Optional[int] = 100

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v):
        """Validate that page_size is greater than 0."""
        if v is not None and v <= 0:
            raise ValueError("page_size must be greater than 0")
        return v


class GetSharesQueryParams(BaseModel):
    """Query parameters for listing shares."""

    prefix: Optional[str] = None
    page_size: Optional[int] = 100

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v):
        """Validate that page_size is greater than 0."""
        if v is not None and v <= 0:
            raise ValueError("page_size must be greater than 0")
        return v


class AddDataObjectsRequest(BaseModel):
    """Request model for adding data objects to a share."""

    tables: Optional[List[str]] = []
    views: Optional[List[str]] = []
    schemas: Optional[List[str]] = []

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tables": ["catalog.schema.table1", "catalog.schema.table2"],
                "views": ["catalog.schema.view1"],
                "schemas": ["catalog.schema"],
            }
        }
    )


# delete (cruD)
class DeleteRecipientResponse(BaseModel):
    """Response model for deleting a recipient."""

    message: str
    status_code: int
