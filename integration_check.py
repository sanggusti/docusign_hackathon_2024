import os
import sys
import time
import uuid
import base64
import webbrowser
from urllib.parse import quote
from datetime import datetime
from io import BytesIO
from docusign_utils import DocuSignManager
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator
from config import DS_CONFIG, DS_JWT
from cohere_utils import HealthcareCohereClient

# Set up environment for OAuth
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['DS_OAUTH_ENABLED'] = 'true'

def oauth_flow():
    """Initiate OAuth flow and handle consent"""
    try:
        print("\nStarting OAuth flow: opening DocuSign consent page...")
        scopes = quote("signature impersonation")
        auth_url = (
            f"{DS_CONFIG['authorization_server']}/oauth/auth"
            f"?response_type=code"
            f"&scope={scopes}"
            f"&client_id={DS_JWT['ds_client_id']}"
            f"&redirect_uri={quote(DS_CONFIG['app_url'] + '/ds/callback')}"
        )
        
        print(f"\nConsent URL: {auth_url}")
        webbrowser.open(auth_url)
        
        # Wait for user to complete consent
        input("\nAfter granting consent in the browser, press Enter to continue...")
        return True
        
    except Exception as e:
        print(f"\n❌ OAuth flow failed: {str(e)}")
        return False

def initialize_docusign():
    """Initialize DocuSign with proper OAuth handling"""
    max_retries = 3
    retry_delay = 10
    
    print("Initializing DocuSign connection...")
    
    for attempt in range(max_retries):
        try:
            # Ensure OAuth flow is completed first
            if not os.environ.get('DS_OAUTH_COMPLETED'):
                if oauth_flow():
                    os.environ['DS_OAUTH_COMPLETED'] = 'true'
                else:
                    raise Exception("OAuth flow failed")
            
            docusign = DocuSignManager()
            return docusign
            
        except Exception as e:
            if "consent_required" in str(e) and attempt < max_retries - 1:
                print(f"\nRetrying OAuth flow in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
            print(f"\n❌ DocuSign initialization failed: {str(e)}")
            sys.exit(1)
    
    raise Exception("Failed to initialize DocuSign after maximum retries")

def verify_credentials():
    """Verify all required credentials before starting"""
    print("Verifying credentials...")
    
    try:
        # Test Cohere client
        cohere_client = HealthcareCohereClient()
        print("✓ Cohere client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Credential verification failed: {str(e)}")
        return False

def test_document_workflow():
    print("Starting document workflow test...")
    
    # Initialize components
    db_client = HealthcareVectorDB()
    pdf_gen = PDFGenerator()
    
    try:
        # Initialize DocuSign with consent handling
        docusign = initialize_docusign()
        print("✓ DocuSign initialized successfully")
        
        # Step 1: Generate a sample PDF document
        print("\n1. Generating sample PDF...")
        sample_doc = {
            "title": "Test Prescription",
            "content": {
                "patient_info": "Patient ID: TEST_123",
                "medical_details": "Lorem ipsum dolor sit amet",
                "insurance": "BPJS",
                "diagnosis": "Test Condition",
                "prescription": ["Test Medication 100mg"],
            }
        }
        pdf_bytes = pdf_gen.generate_pdf(sample_doc).read()
        print("✓ PDF generated successfully")

        # Step 2: Store document in LanceDB
        print("\n2. Storing document in LanceDB...")
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        patient_id = "PATIENT_123"
        store_success = db_client.store_document({
            "content": str(sample_doc),
            "metadata": {
                "doc_id": doc_id,
                "patient_id": patient_id,
                "doc_type": "Prescription",
                "status": "generated",
                "signature_status": "pending"
            }
        })
        if not store_success:
            raise Exception("Failed to store document in LanceDB")
        print("✓ Document stored in LanceDB")

        # Step 3: Initiate DocuSign envelope
        print("\n3. Initiating DocuSign envelope...")
        envelope_info = docusign.create_envelope(
            pdf_bytes=pdf_bytes,
            signer_info={
                "email": DS_CONFIG["signer_email"],
                "name": DS_CONFIG["signer_name"],
                "client_id": patient_id,
                "doc_type": "Prescription",
                "doc_name": "Test Prescription"
            }
        )
        print("✓ DocuSign envelope created successfully")
        print(f"Envelope ID: {envelope_info['envelope_id']}")
        print(f"Signing URL: {envelope_info['redirect_url']}")

        # Step 4: Update document status
        print("\n4. Updating document status...")
        update_success = db_client.update_document_status(
            doc_id,
            {
                "signature_status": "sent_for_signing",
                "envelope_id": envelope_info['envelope_id']
            }
        )
        if not update_success:
            raise Exception("Failed to update document status")
        print("✓ Document status updated")

        # Step 5: Verify final state
        print("\n5. Verifying final state...")
        status = docusign.get_envelope_status(envelope_info['envelope_id'])
        
        if 'error' in status:
            raise Exception(f"Failed to get envelope status: {status['error']}")
            
        print("Document Status:")
        print(f"- Envelope Status: {status['status']}")
        print(f"- Created: {status['created']}")
        print("✓ Verification complete")

        print("\n✅ Integration test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        if not verify_credentials():
            sys.exit(1)
        success = test_document_workflow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
