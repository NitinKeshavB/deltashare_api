"""Module for managing Databricks recipients for Delta Sharing."""

import os
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import (
    List,
    Optional,
)

try:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sharing import (
        AuthenticationType,
        IpAccessList,
    )

    from dbrx_api.dbrx_auth.token_gen import (
        CustomError,
        get_auth_token,
    )
except ImportError:
    print("failed to import libraries")


DLTSHR_WORKSPACE_URL = os.getenv("DLTSHR_WORKSPACE_URL")


def list_recipients(
    max_results: Optional[int] = 100,
    prefix: Optional[str] = None,
) -> list:
    """
    Retrieve all Delta Sharing recipients from Databricks workspace.

    Automatically handles pagination to fetch all recipients. Generates
    authentication token and creates WorkspaceClient for API interaction.

    Parameters
    ----------
    max_results : Optional[int], default=100
        Max results per page. Uses DEFAULT_MAX_KEY if None.
    prefix : Optional[str], default=None
        Optional prefix to filter recipients by name.

    Returns
    -------
    list
        List of recipient objects.

    Raises
    ------
    CustomError
        Authentication failure
    Exception
        API or network errors

    """
    session_token = get_auth_token(datetime.now(timezone.utc))[0]
    w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)
    all_recipients = []

    # The list() method returns an iterator that automatically handles
    # pagination
    for recipient in w_client.recipients.list(max_results=max_results or 100):
        if prefix:
            if prefix in str(recipient.name):
                all_recipients.append(recipient)
        else:
            all_recipients.append(recipient)

    return all_recipients


def get_recipients(recipient_name: str):
    """
    Retrieve a specific recipient by name from Databricks workspace.

    Fetches detailed information about a single recipient including
    authentication type, tokens, IP access lists, and metadata.

    Parameters
    ----------
    recipient_name : str
        Name of the recipient to retrieve

    Returns
    -------
    RecipientInfo
        Recipient object with full details including:
        - name, authentication_type, created_at, updated_at
        - tokens (for TOKEN type), sharing_code (for D2D)
        - ip_access_list, metastore_id, activation_url

    Raises
    ------
    CustomError
        Authentication failure
    Exception
        Recipient not found or API errors

    Notes
    -----
    Recipient name is case-sensitive and must match exactly.

    """
    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Get recipient by name
        response = w_client.recipients.get(name=recipient_name)
        return response

    except Exception as e:
        print(f"✗ Error retrieving recipient '{recipient_name}': {e}")
        return None


def create_recipient_d2d(
    recipient_name: str, recipient_identifier: str, description: str, sharing_code: Optional[str] = None
):
    """Create a Databricks-to-Databricks (D2D) recipient.

    D2D recipients authenticate using Databricks workspace credentials
    and do NOT support IP access lists (use TOKEN type for IP filtering).

    Args:
        recipient_name: Unique name for the recipient
        recipient_identifier: Global metastore ID for the recipient
            Format: cloud:region:metastore-uuid
            Example: "aws:us-west-2:d81ea1bd-b74b-4c76-bf14-2db1a74d1dd8"
        description: Comment/description for the recipient
        sharing_code: Optional sharing code for authentication

    Returns:
        RecipientInfo: Created recipient object, or None if failed

    Raises:
        CustomError: Authentication failure
        ValueError: Invalid parameters
        Exception: API or network errors

    Note:
        IP access lists are NOT supported for D2D recipients.
        Use create_recipient_token() for recipients with IP filtering.
    """
    # Get authentication token
    session_token = get_auth_token(datetime.now(timezone.utc))[0]

    # Create workspace client
    w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

    # Create D2D recipient (no ip_access_list for D2D type)
    response = w_client.recipients.create(
        name=recipient_name,
        data_recipient_global_metastore_id=recipient_identifier,
        comment=description,
        authentication_type=AuthenticationType.DATABRICKS,
        sharing_code=sharing_code if sharing_code else None,
    )

    return response


def create_recipient_d2o(
    recipient_name: str,
    description: str,
    ip_access_list: Optional[List[str]] = None,
):
    """
    Create a Databricks-to-Open Share (D2O) TOKEN-based recipient.

    D2O recipients use TOKEN authentication and support IP access lists
    for enhanced security. These recipients receive activation URLs and
    bearer tokens for accessing shared data.

    Parameters
    ----------
    recipient_name : str
        Unique name for the recipient
    description : str
        Comment/description for the recipient
    ip_access_list : list of str, optional
        Optional list of IP addresses/CIDR blocks
        Example: ["0.0.0.0/0", "212.212.3.0/24"]
        If None, no IP restrictions are applied

    Returns
    -------
    RecipientInfo
        Created recipient object with activation_url and tokens

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    TOKEN recipients support IP access lists, unlike D2D recipients.

    """
    # Process IP access list
    ip_access = None
    if ip_access_list:
        if not isinstance(ip_access_list, list):
            print("✗ Error: ip_access_list must be a list of IP addresses")
            return None

        # Strip whitespace from each IP address
        cleaned_ips = [ip.strip() for ip in ip_access_list if ip.strip()]

        if cleaned_ips:
            ip_access = IpAccessList(allowed_ip_addresses=cleaned_ips)
            print(f"✓ IP access list configured with " f"{len(cleaned_ips)} entries")

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Create TOKEN recipient with optional IP access list
        response = w_client.recipients.create(
            name=recipient_name,
            comment=description,
            authentication_type=AuthenticationType.TOKEN,
            ip_access_list=ip_access,
        )

        return response

    except CustomError as e:
        print(f"✗ Authentication error: {e}")
        return None
    except ValueError as e:
        print(f"✗ Invalid parameter value: {e}")
        return None
    except Exception as ex:
        error_msg = str(ex)
        if "already exists" in error_msg.lower():
            print(f"✗ Recipient '{recipient_name}' already exists")
        else:
            print(f"✗ Unexpected error creating recipient: {ex}")
        return None


def rotate_recipient_token(recipient_name: str, expire_in_seconds: int = 0):
    """
    Rotate the token for a TOKEN-based recipient.

    Generates a new bearer token for an existing TOKEN recipient and
    optionally sets an expiration time for the old token.

    Parameters
    ----------
    recipient_name : str
        Name of the existing TOKEN recipient
    expire_in_seconds : int, optional
        Seconds until the old token expires.
        Default: 0 (expires immediately)
        Set to keep old token valid during transition period

    Returns
    -------
    RecipientInfo or None
        Updated recipient object with new token, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    Only works with TOKEN authentication type recipients.
    The new token will be available in response.tokens list.

    """
    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Rotate token for recipient
        response = w_client.recipients.rotate_token(
            name=recipient_name,
            existing_token_expire_in_seconds=expire_in_seconds,
        )

        return response

    except Exception as ex:
        print(f"✗ Unexpected error rotating token: {ex}")
        return None


def add_recipient_ip(recipient_name: str, ip_access_list: List[str]):
    """
    Update IP access list for a TOKEN-based recipient.

    Modifies the allowed IP addresses for an existing TOKEN recipient.
    Only works with TOKEN authentication type recipients.

    Parameters
    ----------
    recipient_name : str
        Name of the existing TOKEN recipient
    ip_access_list : list of str
        List of IP addresses/CIDR blocks to allow
        Example: ["10.0.0.0/8", "192.168.1.0/24"]
        Pass empty list [] to remove all IP restrictions

    Returns
    -------
    RecipientInfo or None
        Updated recipient object, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    Only works with TOKEN authentication type recipients.
    D2D recipients do not support IP access lists.

    """
    # Process new IP addresses
    cleaned_ips = [ip.strip() for ip in ip_access_list if ip.strip()]

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Get current recipient to retrieve existing IPs
        recipient = w_client.recipients.get(name=recipient_name)

        # Merge with existing IPs if they exist
        if recipient.ip_access_list and recipient.ip_access_list.allowed_ip_addresses:
            existing_ips = recipient.ip_access_list.allowed_ip_addresses
            # Combine and deduplicate IPs
            all_ips = list(set(cleaned_ips + existing_ips))
        else:
            all_ips = cleaned_ips

        # Create IP access list object
        ip_access = IpAccessList(allowed_ip_addresses=all_ips) if all_ips else None

        # Update recipient IP access list
        response = w_client.recipients.update(name=recipient_name, ip_access_list=ip_access)

        return response
    except Exception as ex:
        print(f"✗ Unexpected error updating IP access list: {ex}")
        return None


def revoke_recipient_ip(recipient_name: str, ip_access_list: List[str]):
    """
    Remove specific IP addresses from a TOKEN-based recipient's access list.

    Removes the specified IP addresses from an existing TOKEN recipient's
    allowed IP list. Only works with TOKEN authentication type recipients.

    Parameters
    ----------
    recipient_name : str
        Name of the existing TOKEN recipient
    ip_access_list : list of str
        List of IP addresses/CIDR blocks to remove
        Example: ["10.0.0.0/8", "192.168.1.0/24"]
        IPs not in the current list will be ignored

    Returns
    -------
    RecipientInfo or None
        Updated recipient object, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    Only works with TOKEN authentication type recipients.
    D2D recipients do not support IP access lists.
    If all IPs are removed, the recipient will have no IP restrictions.

    """
    # Validate required parameters

    if not isinstance(ip_access_list, list):
        print("✗ Error: ip_access_list must be a list of IP addresses")
        return None

    # Process IP addresses to remove
    ips_to_remove = set(ip.strip() for ip in ip_access_list if ip.strip())

    if not ips_to_remove:
        print("✗ Error: No valid IP addresses provided to remove")
        return None

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Get current recipient details
        recipient = w_client.recipients.get(name=recipient_name)

        # Check if recipient has IP restrictions
        if not recipient.ip_access_list or not recipient.ip_access_list.allowed_ip_addresses:
            print(f"✗ Recipient '{recipient_name}' has no IP " "restrictions to remove")
            return None

        existing_ips = set(recipient.ip_access_list.allowed_ip_addresses)

        # Remove specified IPs from existing list
        remaining_ips = list(existing_ips - ips_to_remove)

        # Check what was actually removed
        actually_removed = existing_ips & ips_to_remove
        not_found = ips_to_remove - existing_ips

        if not actually_removed:
            print("✗ None of the specified IPs were found in the access list")
            if not_found:
                print(f"  IPs not found: {', '.join(not_found)}")
            return None

        print(f"✓ Removing {len(actually_removed)} IP(s) from access list")
        if not_found:
            print(f"  Note: {len(not_found)} IP(s) were not found and skipped")

        if not remaining_ips:
            print("  Warning: All IPs removed - recipient will have no " "IP restrictions")

        # Create IP access list object (empty list if no IPs remaining)
        ip_access = IpAccessList(allowed_ip_addresses=remaining_ips)

        # Update recipient IP access list
        response = w_client.recipients.update(name=recipient_name, ip_access_list=ip_access)

        return response

    except Exception as ex:
        str(ex)
        print(f"✗ Unexpected error removing IP addresses: {ex}")
        return None


def update_recipient_description(recipient_name: str, description: str):
    """
    Update the description/comment for an existing recipient.

    Modifies the comment field for a recipient without affecting other
    properties like authentication type, tokens, or IP access lists.

    Parameters
    ----------
    recipient_name : str
        Name of the existing recipient to update
    description : str
        New description/comment text for the recipient

    Returns
    -------
    RecipientInfo or None
        Updated recipient object, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    Works with both TOKEN and DATABRICKS authentication types.

    """
    # Validate parameters

    if not description or not description.strip():
        print("✗ Error: description cannot be empty")
        return None

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Update recipient description
        response = w_client.recipients.update(name=recipient_name, comment=description)

        return response

    except Exception as ex:
        print(f"✗ Unexpected error updating recipient description: {ex}")
        raise


def update_recipient_expiration_time(recipient_name: str, expiration_time: int):
    """
    Update the expiration time for an existing recipient.

    Sets when the recipient will expire and no longer have access.
    The expiration time is provided in days from now and converted to
    epoch milliseconds for the API.

    Parameters
    ----------
    recipient_name : str
        Name of the existing recipient to update
    expiration_time : int
        Number of days from now until expiration
        Example: 30 = expire in 30 days, 0 = expire immediately

    Returns
    -------
    RecipientInfo or None
        Updated recipient object, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters (negative days)
    Exception
        API or network errors

    Notes
    -----
    Works with both TOKEN and DATABRICKS authentication types.
    Expiration time is converted to epoch milliseconds.

    """
    # Validate parameters
    if not recipient_name or not recipient_name.strip():
        print("✗ Error: recipient_name cannot be empty")
        return None

    if expiration_time < 0:
        print("✗ Error: expiration_time cannot be negative")
        return None

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Convert days to epoch milliseconds
        expiration_datetime = datetime.now(timezone.utc) + timedelta(days=expiration_time)
        expiration_epoch_ms = int(expiration_datetime.timestamp() * 1000)

        print(f"✓ Setting expiration to {expiration_time} days from now")
        print(f"  Expiration date: " f"{expiration_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Epoch milliseconds: {expiration_epoch_ms}")

        # Update recipient expiration time
        response = w_client.recipients.update(name=recipient_name, expiration_time=expiration_epoch_ms)

        print(f"✓ Successfully updated expiration time for: {recipient_name}")

        return response

    except CustomError as e:
        print(f"✗ Authentication error: {e}")
        return None
    except ValueError as e:
        print(f"✗ Invalid parameter value: {e}")
        return None
    except Exception as ex:
        error_msg = str(ex)
        if "not found" in error_msg.lower():
            print(f"✗ Recipient '{recipient_name}' not found")
        else:
            print(f"✗ Unexpected error updating recipient expiration: {ex}")
        return None


def delete_recipient(recipient_name: str):
    """
    Delete an existing recipient from the workspace.

    Permanently removes a recipient and revokes their access to all
    shared data. This action cannot be undone.

    Parameters
    ----------
    recipient_name : str
        Name of the recipient to delete

    Returns
    -------
    None
        None on success, or None if failed

    Raises
    ------
    CustomError
        Authentication failure
    ValueError
        Invalid parameters
    Exception
        API or network errors

    Notes
    -----
    Works with both TOKEN and DATABRICKS authentication types.
    Deletion is permanent and cannot be reversed.

    """
    # Validate parameters
    if not recipient_name or not recipient_name.strip():
        print("✗ Error: recipient_name cannot be empty")
        return None

    try:
        # Get authentication token
        session_token = get_auth_token(datetime.now(timezone.utc))[0]

        # Create workspace client
        w_client = WorkspaceClient(host=DLTSHR_WORKSPACE_URL, token=session_token)

        # Delete recipient
        response = w_client.recipients.delete(name=recipient_name)

        return response

    except Exception as ex:
        print(f"✗ Unexpected error deleting recipient: {ex}")
        raise


def main():
    """
    Test recipient retrieval and display results.

    Retrieves all recipients, prints count and details, and shows
    remaining token validity time.

    Returns
    -------
    list or None
        Recipient objects if successful, None on error

    Raises
    ------
    CustomError
        Authentication failure
    Exception
        Unexpected errors

    """
    response = rotate_recipient_token(recipient_name="testing_pam")
    print(type(response))

    # iterate recipients
    print(response)
    return response


if __name__ == "__main__":
    main()
