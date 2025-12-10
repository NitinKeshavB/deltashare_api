"""Module for managing Databricks recipients for Delta Sharing."""
from datetime import (
    datetime,
    timezone,
)
from typing import (
    List,
    Optional,
)

try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sharing import (
        PermissionsChange,
        SharedDataObject,
        SharedDataObjectDataObjectType,
        SharedDataObjectUpdate,
        SharedDataObjectUpdateAction,
    )

    from dbrx_api.dbrx_auth.token_gen import get_auth_token
except ImportError:
    print("failed to import libraries")

import os

###################################


def list_share(
    dltshr_workspace_url: str,
    max_results: Optional[int] = 100,
    prefix: Optional[str] = None,
) -> List:
    """List all Delta Sharing recipients with optional prefix filter.

    Args:
        dltshr_workspace_url: Databricks workspace URL
        max_results: Maximum results per page (default: 100)
        prefix: Optional name prefix to filter recipients

    Returns:
        List of recipient objects
    """
    try:
        session_token = get_auth_token(datetime.now(timezone.utc))[0]
        w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)

        all_shares = []

        # List all shares using SDK
        for share in w_client.shares.list(max_results=max_results):
            if prefix:
                if prefix in str(share.name):
                    all_shares.append(share)
            else:
                all_shares.append(share)

        return all_shares
    except Exception as e:
        print(f"✗ Error listing shares: {e}")
        raise


def get_shares(share_name: str, dltshr_workspace_url: str):
    """Get recipient details by name.

    Args:
        recipient_name: Name of the recipient (case-sensitive)
        dltshr_workspace_url: Databricks workspace URL

    Returns:
        RecipientInfo object or None if not found
    """
    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)

        # Get recipient by name
        response = w_client.shares.get(name=share_name)
        return response

    except Exception as e:
        print(f"✗ Error retrieving share '{share_name}': {e}")
        return None


def create_share(dltshr_workspace_url: str, share_name: str, description: str, storage_root: str = None):
    """Create a share for Delta Sharing.

    Args:
        workspace_url: Databricks workspace URL
        share_name: Unique share name
        description: Share description/comment
        storage_root: Optional storage root URL for the share

    Returns:
        ShareInfo object or error message string

    Note:
        Caller must be a metastore admin or have CREATE_SHARE privilege.
    """
    # Get authentication token
    session_token = get_auth_token(datetime.now(timezone.utc))[0]

    # Create workspace client
    w_client = WorkspaceClient(host=workspace_url, token=session_token)
    try:
        # Create share
        response = w_client.shares.create(name=share_name, comment=description, storage_root=storage_root)
    except Exception as e:
        err_msg = str(e)

        if "already exists" in err_msg or "AlreadyExists" in err_msg:
            print(f"✗ Share '{share_name}' already exists.")
            return f"Share already exists with name '{share_name}'"
        elif "PERMISSION_DENIED" in err_msg or "PermissionDenied" in err_msg:
            print(f"✗ Permission denied: User lacks CREATE_SHARE privilege or is not a metastore admin.")
            return (
                "Permission denied to create share. Caller must be a metastore admin or have CREATE_SHARE privilege."
            )
        elif "User is not an owner of Share" in err_msg or "PERMISSION_DENIED" in err_msg:
            print(f"✗ Permission denied to delete share: {share_name}")
            return "User is not an owner of Share"
        elif "INVALID_PARAMETER_VALUE" in err_msg or "invalid" in err_msg.lower():
            print(f"✗ Invalid parameter: {err_msg}")
            return f"Invalid parameter in share creation: {err_msg}"
        elif "RESOURCE_DOES_NOT_EXIST" in err_msg:
            print(f"✗ Storage root location does not exist or is not accessible.")
            return "Storage root location does not exist or is not accessible"
        elif "INVALID_STATE" in err_msg:
            print(f"✗ Invalid state: {err_msg}")
            return f"Invalid state for share creation: {err_msg}"
        else:
            print(f"✗ Error creating share '{share_name}': {e}")
            raise

    return response


def add_data_object_to_share(
    dltshr_workspace_url: str,
    share_name: str,
    objects_to_add: [List[dict]],
):
    """Create a share for Delta Sharing.

    Args:
        dltshr_workspace_url: Databricks workspace URL
        share_name: Unique share name
        description: Share description/comment
        storage_root: Optional storage root URL for the share

    Returns:
        ShareInfo object or error message string

    Note:
        Caller must be a metastore admin or have CREATE_SHARE privilege.
    """
    # Get authentication token
    session_token = get_auth_token(datetime.now(timezone.utc))[0]

    # Create workspace client
    w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)
    try:
        if objects_to_add is None or len(objects_to_add) == 0:
            return "No data objects provided to add to share."

        tables_to_add = objects_to_add.get("tables", [])
        views_to_add = objects_to_add.get("views", [])
        schemas_to_add = objects_to_add.get("schemas", [])

        if len(tables_to_add) == 0 and len(views_to_add) == 0 and len(schemas_to_add) == 0:
            return "No data objects provided to add to share."

        add_table_updates = []
        add_view_updates = []
        add_schema_updates = []

        if tables_to_add:
            add_table_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.ADD,
                    data_object=SharedDataObject(
                        name=table_name, data_object_type=SharedDataObjectDataObjectType.TABLE
                    ),
                )
                for table_name in tables_to_add
            ]

        if views_to_add:
            add_view_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.ADD,
                    data_object=SharedDataObject(name=view_name, data_object_type=SharedDataObjectDataObjectType.VIEW),
                )
                for view_name in views_to_add
            ]

        if schemas_to_add:
            # Extract schema names from tables and views being added
            table_schemas = set()
            view_schemas = set()

            for table_name in tables_to_add:
                # Extract schema from fully qualified name (catalog.schema.table)
                parts = table_name.split(".")
                if len(parts) >= 2:
                    schema_fqn = ".".join(parts[:-1])  # catalog.schema
                    table_schemas.add(schema_fqn)

            for view_name in views_to_add:
                parts = view_name.split(".")
                if len(parts) >= 2:
                    schema_fqn = ".".join(parts[:-1])
                    view_schemas.add(schema_fqn)

            # Check for conflicts
            conflicting_schemas = []
            for schema_name in schemas_to_add:
                if schema_name in table_schemas or schema_name in view_schemas:
                    conflicting_schemas.append(schema_name)

            if conflicting_schemas:
                conflict_msg = f"Cannot add schemas {conflicting_schemas} as individual tables/views from these schemas are already part of same request"
                print(f"✗ {conflict_msg}")
                return conflict_msg

            add_schema_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.ADD,
                    data_object=SharedDataObject(
                        name=schema_name, data_object_type=SharedDataObjectDataObjectType.SCHEMA
                    ),
                )
                for schema_name in schemas_to_add
            ]

        all_updates = add_table_updates + add_view_updates + add_schema_updates
        if all_updates:
            response = w_client.shares.update(name=share_name, updates=all_updates)
            return response

    except Exception as e:
        err_msg = str(e)

        if "ResourceAlreadyExists" in err_msg or "already exists" in err_msg:
            print(f"✗ Data object already exists in share: {err_msg}")
            return f"Data object already exists in share: {share_name}"
        elif "PERMISSION_DENIED" in err_msg or "PermissionDenied" in err_msg:
            print(f"✗ Permission denied: User lacks SELECT privilege on data objects or is not share owner")
            return "Permission denied. Share owner must have SELECT privilege on data objects."
        elif "User is not an owner of Share" in err_msg or "PERMISSION_DENIED" in err_msg:
            print(f"✗ Permission denied to delete share: {share_name}")
            return "User is not an owner of Share"
        elif "RESOURCE_DOES_NOT_EXIST" in err_msg or "does not exist" in err_msg:
            print(f"✗ Data object not found: {err_msg}")
            return f"Data object not found: {err_msg}"
        elif (
            "databricks.sdk.errors.platform.InvalidParameterValue" in err_msg
            or "is a table and not a VIEW"
            or "is a VIEW and not a Table" in err_msg.lower()
        ):
            print(f"✗ Invalid parameter: {err_msg}")
            return f"Invalid parameter in data object : {err_msg}"
        else:
            print(f"✗ Error adding data objects to share '{share_name}': {e}")
            raise


def revoke_data_object_from_share(
    dltshr_workspace_url: str,
    share_name: str,
    objects_to_revoke: [List[dict]],
):
    """Create a share for Delta Sharing.

    Args:
        dltshr_workspace_url: Databricks workspace URL
        share_name: Unique share name
        description: Share description/comment
        storage_root: Optional storage root URL for the share

    Returns:
        ShareInfo object or error message string

    Note:
        Caller must be a metastore admin or have CREATE_SHARE privilege.
    """
    # Get authentication token
    session_token = get_auth_token(datetime.now(timezone.utc))[0]

    # Create workspace client
    w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)
    try:
        if objects_to_revoke is None or len(objects_to_revoke) == 0:
            return "No data objects provided to revoke from share."

        tables_to_revoke = objects_to_revoke.get("tables", [])
        views_to_revoke = objects_to_revoke.get("views", [])
        schemas_to_revoke = objects_to_revoke.get("schemas", [])

        if len(tables_to_revoke) == 0 and len(views_to_revoke) == 0 and len(schemas_to_revoke) == 0:
            return "No data objects provided to revoke from share."

        add_table_updates = []
        add_view_updates = []
        add_schema_updates = []

        if tables_to_revoke:
            add_table_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.REMOVE,
                    data_object=SharedDataObject(
                        name=table_name, data_object_type=SharedDataObjectDataObjectType.TABLE
                    ),
                )
                for table_name in tables_to_revoke
            ]

        if views_to_revoke:
            add_view_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.REMOVE,
                    data_object=SharedDataObject(name=view_name, data_object_type=SharedDataObjectDataObjectType.VIEW),
                )
                for view_name in views_to_revoke
            ]

        if schemas_to_revoke:
            # Extract schema names from tables and views being revoked
            table_schemas = set()
            view_schemas = set()

            for table_name in tables_to_revoke:
                # Extract schema from fully qualified name (catalog.schema.table)
                parts = table_name.split(".")
                if len(parts) >= 2:
                    schema_fqn = ".".join(parts[:-1])  # catalog.schema
                    table_schemas.add(schema_fqn)

            for view_name in views_to_revoke:
                parts = view_name.split(".")
                if len(parts) >= 2:
                    schema_fqn = ".".join(parts[:-1])
                    view_schemas.add(schema_fqn)

            # Check for conflicts
            conflicting_schemas = []
            for schema_name in schemas_to_revoke:
                if schema_name in table_schemas or schema_name in view_schemas:
                    conflicting_schemas.append(schema_name)

            if conflicting_schemas:
                conflict_msg = f"Cannot remove schemas {conflicting_schemas} as individual tables/views from these schemas are already part of same request"
                print(f"✗ {conflict_msg}")
                return conflict_msg

            add_schema_updates = [
                SharedDataObjectUpdate(
                    action=SharedDataObjectUpdateAction.REMOVE,
                    data_object=SharedDataObject(
                        name=schema_name, data_object_type=SharedDataObjectDataObjectType.SCHEMA
                    ),
                )
                for schema_name in schemas_to_revoke
            ]

        all_updates = add_table_updates + add_view_updates + add_schema_updates
        if all_updates:
            response = w_client.shares.update(name=share_name, updates=all_updates)
            return response

    except Exception as e:
        err_msg = str(e)

        if "ResourceAlreadyExists" in err_msg or "already exists" in err_msg:
            print(f"✗ Data object already exists in share: {err_msg}")
            return f"Data object already exists in share: {share_name}"
        elif "PERMISSION_DENIED" in err_msg or "PermissionDenied" in err_msg:
            print(f"✗ Permission denied: User lacks SELECT privilege on data objects or is not share owner")
            return "Permission denied. Share owner must have SELECT privilege on data objects."
        elif "User is not an owner of Share" in err_msg or "PERMISSION_DENIED" in err_msg:
            return "User is not an owner of Share"
        elif "RESOURCE_DOES_NOT_EXIST" in err_msg or "does not exist" in err_msg:
            print(f"✗ Data object not found: {err_msg}")
            return f"Data object not found: {err_msg}"
        elif (
            "databricks.sdk.errors.platform.InvalidParameterValue" in err_msg
            or "is a table and not a VIEW"
            or "is a VIEW and not a Table" in err_msg.lower()
        ):
            print(f"✗ Invalid parameter: {err_msg}")
            return f"Invalid parameter in data object : {err_msg}"
        else:
            print(f"✗ Error adding data objects to share '{share_name}': {e}")
            raise


def add_recipients_to_share(
    dltshr_workspace_url: str,
    share_name: str,
    recipient_name: str,
):
    """List all Delta Sharing recipients with optional prefix filter.

    Args:
        dltshr_workspace_url: Databricks workspace URL
        max_results: Maximum results per page (default: 100)
        prefix: Optional name prefix to filter recipients

    Returns:
        List of recipient objects
    """
    session_token = get_auth_token(datetime.now(timezone.utc))[0]
    w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)
    try:
        response = w_client.shares.update_permissions(
            name=share_name,
            changes=[
                PermissionsChange(principal=recipient_name, add=["SELECT"])  # SELECT is the only privilege for shares
            ],
        )
        return response
    except Exception as e:
        error_msg = str(ex)
        if "User is not an owner of Share" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"✗ Permission denied to delete share: {share_name}")
            return "User is not an owner of Share"
        else:
            print(f"✗ Failed to add recipient {recipient_name} access to share {share_name} : {str(e)}")
            raise


def remove_recipients_from_share(
    dltshr_workspace_url: str,
    share_name: str,
    recipient_name: str,
):
    """List all Delta Sharing recipients with optional prefix filter.

    Args:
        dltshr_workspace_url: Databricks workspace URL
        max_results: Maximum results per page (default: 100)
        prefix: Optional name prefix to filter recipients

    Returns:
        List of recipient objects
    """
    session_token = get_auth_token(datetime.now(timezone.utc))[0]
    w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)
    try:
        response = w_client.shares.update_permissions(
            name=share_name,
            changes=[
                PermissionsChange(principal=recipient_name, add=["REMOVE"])  # SELECT is the only privilege for shares
            ],
        )
        return response
    except Exception as e:
        error_msg = str(ex)
        if "User is not an owner of Share" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"✗ Permission denied to delete share: {share_name}")
            return "User is not an owner of Share"
        else:
            print(f"✗ Failed to remove recipient {recipient_name} access to share {share_name} : {str(e)}")
            raise


def delete_share(
    share_name: str,
    dltshr_workspace_url: str,
):
    """Delete share permanently.

    Args:
        share_name: Share name
        dltshr_workspace_url: Databricks workspace URL

    Returns:
        None on success or error message string
    """
    # Validate parameters
    if not share_name or not share_name.strip():
        print("✗ Error: share_name cannot be empty")
        return None

    try:
        session_token = get_auth_token(datetime.now(timezone.utc))[0]
        w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)

        # Delete share
        w_client.shares.delete(name=share_name)
        return None

    except Exception as ex:
        error_msg = str(ex)
        if "User is not an owner of Share" in error_msg or "PERMISSION_DENIED" in error_msg:
            print(f"✗ Permission denied to delete share: {share_name}")
            return "User is not an owner of Share"
        elif "RESOURCE_DOES_NOT_EXIST" in error_msg or "does not exist" in error_msg:
            print(f"✗ Share not found: {share_name}")
            return f"Share not found: {share_name}"
        else:
            print(f"✗ Unexpected error deleting share: {ex}")
            raise


if __name__ == "__main__":
    import os

    dltshr_workspace_url = os.getenv("DLTSHR_WORKSPACE_URL")
    shares = delete_share(
        dltshr_workspace_url=dltshr_workspace_url,
        share_name="share_1-1765308492429445086",
    )
    print(shares)
