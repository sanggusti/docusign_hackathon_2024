# create envelope
# define envelope
# envelope response
# view request
# recipient view

# docusign_utils.py
import base64
import webbrowser
from docusign_esign import EnvelopesApi, Document, Signer, EnvelopeDefinition, Recipients, ApiClient, UserInfo, UsersApi
from config import DS_CONFIG, DS_JWT
from os import path

class DocuSignManager:
    def __init__(self):
        self.api_client = None
        self.account_id = None
        self.access_token = None
        self.return_url = DS_CONFIG["app_url"] + "/ds/callback"
        self._authenticate()

    def _authenticate(self):
        """Authenticate with DocuSign using JWT grant with OAuth consent"""
        try:
            # Initialize API client
            api_client = ApiClient()
            api_client.set_base_path(DS_CONFIG["authorization_server"])
            
            private_key = self._get_private_key()
            
            try:
                # Request JWT token with OAuth context
                response = api_client.request_jwt_user_token(
                    client_id=DS_JWT["ds_client_id"],
                    user_id=DS_JWT["ds_impersonated_user_id"],
                    oauth_host_name=DS_JWT["authorization_server"],
                    private_key_bytes=private_key.encode("utf-8"),
                    expires_in=4000,
                    scopes=["signature", "impersonation"]
                )
                
                self.access_token = response.access_token
                
            except Exception as e:
                if "consent_required" in str(e):
                    consent_url = (
                        f"{DS_CONFIG['consent_url']}"
                        f"?response_type=code"
                        f"&scope=signature%20impersonation"
                        f"&client_id={DS_JWT['ds_client_id']}"
                        f"&redirect_uri={quote(DS_CONFIG['redirect_uri'])}"
                    )
                    print(f"\nConsent required. URL: {consent_url}")
                    webbrowser.open(consent_url)
                    raise Exception("consent_required")
                raise e
            
            # Set up API client with token
            self.api_client = ApiClient()
            self.api_client.set_base_path(DS_CONFIG["base_path"])
            self.api_client.set_default_header(
                "Authorization",
                f"Bearer {self.access_token}"
            )

            # Get user info and account ID
            user_info = self.api_client.get_user_info(self.access_token)
            self.account_id = user_info.accounts[0].account_id
            
            print(f"Successfully authenticated with account ID: {self.account_id}")
            
        except Exception as e:
            print(f"Authentication error: {str(e)}")
            raise

    def _get_private_key(self):
        """Get private key from file"""
        private_key_file = path.abspath(DS_JWT["private_key_file"])
        
        if not path.exists(private_key_file):
            raise Exception(f"Private key file not found at: {private_key_file}")
            
        with open(private_key_file) as key_file:
            return key_file.read()

    def refresh_token(self):
        """Refresh the authentication token"""
        self._authenticate()

    def create_envelope(self, pdf_bytes: bytes, signer_info: dict) -> dict:
        """Create a DocuSign envelope with embedded signing"""
        try:
            # Prepare document
            base64_pdf = base64.b64encode(pdf_bytes).decode("ascii")
            document = Document(
                document_base64=base64_pdf,
                name=signer_info.get("doc_name", "Healthcare Document"),
                file_extension="pdf",
                document_id="1"
            )

            # Create signer with embedded signing
            signer = Signer(
                email=signer_info["email"],
                name=signer_info["name"],
                recipient_id="1",
                routing_order="1",
                client_user_id=signer_info["client_id"]
            )

            # Create envelope definition
            envelope_definition = EnvelopeDefinition(
                email_subject=f"Please sign: {signer_info.get('doc_type', 'Medical Document')}",
                documents=[document],
                recipients=Recipients(signers=[signer]),
                status="sent"
            )

            # Create and send envelope
            envelope_api = EnvelopesApi(self.api_client)
            # Fix: Pass account_id as parameter to create_envelope
            envelope_response = envelope_api.create_envelope(
                account_id=self.account_id,
                envelope_definition=envelope_definition
            )

            # Create recipient view
            recipient_view = self._create_recipient_view(
                envelope_response.envelope_id,
                signer_info
            )

            return {
                "envelope_id": envelope_response.envelope_id,
                "redirect_url": recipient_view.url
            }

        except Exception as e:
            print(f"Detailed error: {str(e)}")  # Add detailed error logging
            raise Exception(f"DocuSign error: {str(e)}")

    def _create_recipient_view(self, envelope_id: str, signer_info: dict):
        """Create recipient view for embedded signing"""
        from docusign_esign import RecipientViewRequest
        
        view_request = RecipientViewRequest(
            authentication_method="none",
            client_user_id=signer_info["client_id"],
            return_url=self.return_url,
            user_name=signer_info["name"],
            email=signer_info["email"]
        )

        envelope_api = EnvelopesApi(self.api_client)
        return envelope_api.create_recipient_view(
            recipient_view_request=view_request,
            account_id=self.account_id,
            envelope_id=envelope_id
        )

    def get_envelope_status(self, envelope_id: str) -> dict:
        """Check envelope signing status"""
        try:
            envelope_api = EnvelopesApi(self.api_client)
            envelope = envelope_api.get_envelope(self.account_id, envelope_id)
            
            return {
                "status": envelope.status,
                "created": envelope.created_date_time,
                "sent": envelope.sent_date_time,
                "completed": envelope.completed_date_time
            }
            
        except Exception as e:
            return {"error": str(e)}


