from docusign_rooms import ApiClient
from ..ds_config import DS_CONFIG

def create_rooms_api_client(access_token):
    """Create API client and construct API headers"""
    api_client = ApiClient(host=DS_CONFIG["rooms_api_client_host"])
    api_client.set_default_header(
        header_name="Authorization",
        header_value=f"Bearer {access_token}"
    )
    return api_client
