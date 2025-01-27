import os
import sys
import logging
from datetime import datetime
import json
import base64
from typing import Union, Dict
from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, Document, Signer, Recipients

from cohere_utils import HealthcareCohereClient
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator
from jwt_helpers.jwt_helper import get_jwt_token, create_api_client, get_private_key
from config import DS_CONFIG, DS_JWT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_docusign():
    """Initialize DocuSign with JWT - no Flask dependency"""
    try:
        # Get private key
        private_key = get_private_key(DS_JWT["private_key_file"])
        
        # Get JWT token
        token = get_jwt_token(
            private_key=private_key,
            scopes=["signature", "impersonation"],
            auth_server=DS_JWT["authorization_server"],
            client_id=DS_JWT["ds_client_id"],
            impersonated_user_id=DS_JWT["ds_impersonated_user_id"]
        )
        
        # Create API client
        api_client = create_api_client(
            base_path=DS_CONFIG["base_path"],
            access_token=token.access_token
        )
        
        # Get account ID
        user_info = api_client.get_user_info(token.access_token)
        account_id = user_info.accounts[0].account_id
        
        return api_client, account_id
        
    except Exception as e:
        logger.error(f"DocuSign initialization error: {str(e)}")
        raise

def format_medical_content(content: Union[str, Dict]) -> str:
    """Format medical content for PDF generation"""
    if isinstance(content, dict):
        sections = []
        if 'title' in content:
            sections.append(f"# {content['title']}\n")
        if 'content' in content:
            if isinstance(content['content'], dict):
                for section, data in content['content'].items():
                    sections.append(f"\n## {section.replace('_', ' ').title()}")
                    if isinstance(data, dict):
                        for key, value in data.items():
                            sections.append(f"{key}: {value}")
                    elif isinstance(data, list):
                        for item in data:
                            sections.append(f"- {item}")
                    else:
                        sections.append(str(data))
            else:
                sections.append(str(content['content']))
        return "\n".join(sections)
    return str(content)

def test_document_workflow():
    """Run the document workflow test"""
    logger.info("Starting document workflow test...")
    
    try:
        # Initialize components
        cohere_client = HealthcareCohereClient()
        db_client = HealthcareVectorDB()
        pdf_gen = PDFGenerator()

        # Generate document with structured prompt
        sample_data = {
            "name": "John Doe",
            "id": "TEST_123",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": "medical_record"
        }

        structured_prompt = f"""Generate a detailed medical record with the following structure:
Title: Medical Record - {sample_data['name']}

Please include the following sections:
1. Patient Information
- Name: {sample_data['name']}
- ID: {sample_data['id']}
- Date: {sample_data['date']}

2. Medical History
- Past conditions
- Current medications
- Allergies

3. Current Assessment
- Vital signs
- Physical examination
- Current symptoms

4. Diagnosis and Plan
- Primary diagnosis
- Treatment plan
- Follow-up instructions

Format the response as a structured document with clear sections and proper medical terminology."""

        # Generate content
        logger.info("Generating document with Cohere...")
        doc_response = cohere_client.generate_document(structured_prompt)
        
        if not doc_response.get("success"):
            raise Exception(f"Cohere generation failed: {doc_response.get('error')}")

        # Format content for PDF
        formatted_content = format_medical_content(doc_response)
        
        # Create PDF with formatted content
        logger.info("Creating PDF...")
        pdf_content = {
            "title": f"Medical Record - {sample_data['name']}",
            "content": formatted_content
        }
        
        pdf_bytes = pdf_gen.generate_pdf(pdf_content).read()
        
        # Step 3: Store in LanceDB
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        store_success = db_client.store_document({
            "content": formatted_content,
            "metadata": {
                "doc_id": doc_id,
                "patient_id": "TEST_123",
                "doc_type": "medical_record",
                "status": "generated"
            }
        })
        
        if not store_success:
            raise Exception("Failed to store document in LanceDB")
        logger.info("Document stored in LanceDB")

        # Step 4: Initialize DocuSign and create envelope
        logger.info("Initializing DocuSign...")
        api_client, account_id = initialize_docusign()
        
        # Create envelope definition
        envelope_definition = EnvelopeDefinition(
            email_subject="Please sign your medical document",
            documents=[
                Document(
                    document_base64=base64.b64encode(pdf_bytes).decode("ascii"),
                    name="Medical Document.pdf",
                    file_extension="pdf",
                    document_id="1"
                )
            ],
            recipients=Recipients(signers=[
                Signer(
                    email=DS_CONFIG["signer_email"],
                    name=DS_CONFIG["signer_name"],
                    recipient_id="1",
                    routing_order="1"
                )
            ]),
            status="sent"
        )
        
        # Create and send envelope
        envelope_api = EnvelopesApi(api_client)
        envelope_response = envelope_api.create_envelope(
            envelope_definition=envelope_definition,
            account_id=account_id
        )
        logger.info(f"Envelope created successfully. ID: {envelope_response.envelope_id}")
        
        # Update document status
        db_client.update_document_status(
            doc_id,
            {
                "status": "sent_for_signing",
                "envelope_id": envelope_response.envelope_id
            }
        )
        
        logger.info("Test completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

def verify_credentials():
    """Verify required credentials"""
    logger.info("Verifying credentials...")
    
    try:
        # Check Cohere
        cohere_client = HealthcareCohereClient()
        logger.info("✓ Cohere client initialized")
        
        # Check DocuSign JWT configuration
        if not all([DS_JWT["ds_client_id"], 
                   DS_JWT["ds_impersonated_user_id"],
                   DS_JWT["private_key_file"]]):
            raise Exception("Missing required DocuSign JWT configuration")
        logger.info("✓ DocuSign configuration verified")
        
        return True
    except Exception as e:
        logger.error(f"Credential verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        if not verify_credentials():
            sys.exit(1)
        success = test_document_workflow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
