import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DS_CONFIG = {
    "ds_client_id": os.getenv("DS_CLIENT_ID"),
    "ds_client_secret": os.getenv("DS_CLIENT_SECRET"),
    "organization_id": os.getenv("DS_ORGANIZATION_ID"),
    "signer_email": "gustiowinata0@gmail.com",
    "signer_name": "Gusti Winata",
    "app_url": os.getenv("APP_URL", "http://localhost:3000"),
    "authorization_server": "https://account-d.docusign.com",
    "click_api_client_host": "https://demo.docusign.net/clickapi",
    "rooms_api_client_host": "https://demo.rooms.docusign.com/restapi",
    "monitor_api_client_host": "https://lens-d.docusign.net",
    "admin_api_client_host": "https://api-d.docusign.net/management",
    "webforms_api_client_host": "https://apps-d.docusign.com/api/webforms/v1.1",
    "allow_silent_authentication": True,
    "target_account_id": None,
    "demo_doc_path": "demo_documents",
    "doc_salary_docx": "World_Wide_Corp_salary.docx",
    "doc_docx": "World_Wide_Corp_Battle_Plan_Trafalgar.docx",
    "doc_pdf": "World_Wide_Corp_lorem.pdf",
    "doc_terms_pdf": "Term_Of_Service.pdf",
    "doc_txt": "Welcome.txt",
    "doc_offer_letter": "Offer_Letter_Demo.docx",
    "doc_dynamic_table": "Offer_Letter_Dynamic_Table.docx",
    "gateway_account_id": os.getenv("DS_PAYMENT_GATEWAY_ID"),
    "gateway_name": "stripe",
    "gateway_display_name": "Stripe",
    "github_example_url": "https://github.com/docusign/code-examples-python/tree/master/app/eSignature/examples/",
    "monitor_github_url": "https://github.com/docusign/code-examples-python/tree/master/app/monitor/examples/",
    "admin_github_url": "https://github.com/docusign/code-examples-python/tree/master/app/admin/examples/",
    "click_github_url": "https://github.com/docusign/code-examples-python/tree/master/app/click/examples/",
    "connect_github_url": "https://github.com/docusign/code-examples-python/tree/master/app/connect/examples/",
    "example_manifest_url": "https://raw.githubusercontent.com/docusign/code-examples-csharp/master/manifest/CodeExamplesManifest.json",
    "documentation": "",
    "quickstart": "true",
    "base_path": "https://demo.docusign.net/restapi"
}

DS_CONFIG.update({
    "base_path": "https://demo.docusign.net/restapi",
    "app_url": "https://developers.docusign.com"
})

DS_JWT = {
    "ds_client_id": os.getenv("DS_CLIENT_ID"),
    "ds_impersonated_user_id": os.getenv("DS_IMPERSONATED_USER_ID"),
    "private_key_file": "private.key",  # Make sure this path is correct
    "authorization_server": "account-d.docusign.com",
    "oauth_host_name": "account-d.docusign.com",
    "auth_server": "account-d.docusign.com"
}

DS_JWT.update({
    "consent_required_scopes": ["signature", "impersonation"],
    "authorization_server": "https://account-d.docusign.com"
})

# Remove duplicate updates
DS_CONFIG.pop("auth_server", None)
DS_CONFIG.pop("redirect_uri", None)
DS_JWT.pop("private_key_path", None)

# API Keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
LANCEDB_PATH = os.getenv("LANCEDB_PATH", "data/healthcare_db")

# Validate required environment variables
required_vars = [
    "DS_CLIENT_ID",
    "DS_CLIENT_SECRET",
    "DS_IMPERSONATED_USER_ID",
    "COHERE_API_KEY"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")