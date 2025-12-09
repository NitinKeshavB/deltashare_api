####################################
# --- Request/response schemas --- #
####################################

from datetime import datetime
from typing import (
    List,
    Optional,
)

from databricks.sdk.service.sharing import RecipientInfo
from pydantic import (
    BaseModel,
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


# delete (cruD)
class DeleteRecipientResponse(BaseModel):
    """Response model for deleting a recipient."""

    message: str
    status_code: int
