from docusign_esign import ApiClient
from os import path

def get_jwt_token(private_key, scopes, auth_server, client_id, impersonated_user_id):
    """Get the jwt token"""
    try:
        api_client = ApiClient()
        # Remove any protocol prefix from auth_server
        auth_server = auth_server.replace("https://", "").replace("http://", "")
        
        # Configure base path for authentication
        api_client.set_base_path(f"https://{auth_server}")
        
        # Request JWT token
        response = api_client.request_jwt_user_token(
            client_id=client_id,
            user_id=impersonated_user_id,
            oauth_host_name=auth_server,  # Use clean domain name
            private_key_bytes=private_key,
            expires_in=4000,
            scopes=scopes
        )
        return response
    except Exception as e:
        print(f"JWT Token Error: {str(e)}")
        raise

def get_private_key(private_key_path):
    """
    Check that the private key present in the file and if it is, get it from the file.
    In the opposite way get it from config variable.
    """
    private_key_file = path.abspath(private_key_path)

    if path.isfile(private_key_file):
        with open(private_key_file) as private_key_file:
            private_key = private_key_file.read()
    else:
        private_key = private_key_path

    return private_key

def create_api_client(base_path, access_token):
    """Create api client and construct API headers"""
    try:
        api_client = ApiClient()
        # Ensure base_path has https://
        if not base_path.startswith("https://"):
            base_path = f"https://{base_path}"
        api_client.host = base_path
        api_client.set_default_header(header_name="Authorization", header_value=f"Bearer {access_token}")

        return api_client
    except Exception as e:
        print(f"API Client Error: {str(e)}")
        raise