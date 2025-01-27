from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from datetime import datetime
import json
import base64

from cohere_utils import HealthcareCohereClient
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator
from docusign.ds_client import DSClient
from jwt_helpers.jwt_helper import get_jwt_token, create_api_client, get_private_key
from config import DS_CONFIG, DS_JWT

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pilot_test'

# Initialize components
cohere_client = HealthcareCohereClient()
db_client = HealthcareVectorDB()
pdf_gen = PDFGenerator()

def authenticate_docusign():
    """Handle DocuSign JWT authentication"""
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
        
        return api_client, token.access_token
        
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        raise

@app.route('/generate_and_sign', methods=['POST'])
def generate_and_sign():
    try:
        # Step 1: Generate document content with Cohere
        patient_data = request.json.get('patient_data', {})
        doc_type = request.json.get('doc_type', 'medical_record')

        # Validate input
        if not patient_data:
            return jsonify({"success": False, "error": "Missing patient_data"}), 400

        
        doc_content = cohere_client.generate_document(
            f"Generate {doc_type} document for patient: {json.dumps(patient_data)}"
        )

        # Step 2: Create PDF
        pdf_bytes = pdf_gen.generate_pdf({
            "title": f"{doc_type.title()} Document",
            "content": doc_content
        }).read()

        # Step 3: Store in LanceDB
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        store_success = db_client.store_document({
            "content": doc_content,
            "metadata": {
                "doc_id": doc_id,
                "patient_id": patient_data.get('id', 'UNKNOWN'),
                "doc_type": doc_type,
                "status": "generated"
            }
        })

        if not store_success:
            raise Exception("Failed to store document in database")

        # Step 4: Initialize DocuSign
        api_client, access_token = authenticate_docusign()
        
        # Get account ID
        user_info = api_client.get_user_info(access_token)
        account_id = user_info.accounts[0].account_id

        # Step 5: Create and send envelope
        from docusign_esign import EnvelopesApi, EnvelopeDefinition, Document, Signer, Recipients
        
        # Create envelope definition
        envelope_definition = EnvelopeDefinition(
            email_subject=f"Please sign your {doc_type} document",
            documents=[
                Document(
                    document_base64=base64.b64encode(pdf_bytes).decode("ascii"),
                    name=f"{doc_type.title()} Document.pdf",
                    file_extension="pdf",
                    document_id="1"
                )
            ],
            recipients=Recipients(
                signers=[
                    Signer(
                        email=DS_CONFIG["signer_email"],
                        name=DS_CONFIG["signer_name"],
                        recipient_id="1",
                        routing_order="1"
                    )
                ]
            ),
            status="sent"
        )

        # Create envelope
        envelope_api = EnvelopesApi(api_client)
        envelope_response = envelope_api.create_envelope(account_id, envelope_definition)

        # Step 6: Update document status
        db_client.update_document_status(
            doc_id,
            {
                "status": "sent_for_signing",
                "envelope_id": envelope_response.envelope_id
            }
        )

        return {
            "success": True,
            "doc_id": doc_id,
            "envelope_id": envelope_response.envelope_id
        }

    except Exception as e:
        print(f"Error in generate_and_sign: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }, 500

@app.route("/sign_via_email", methods=["POST"])
def sign_via_email():
    """Similar to eg002_signing_via_email: generate doc, store, send for signing."""
    try:
        patient_data = request.json.get("patient_data", {})
        doc_type = request.json.get("doc_type", "medical_record")

        # 1: Generate content via Cohere
        generated = cohere_client.generate_document(
            f"Generate {doc_type} document for patient: {json.dumps(patient_data)}"
        )

        # 2: Create PDF
        pdf_bytes = pdf_gen.generate_pdf({
            "title": f"{doc_type.title()} Document",
            "content": generated
        }).read()

        # 3: Store in LanceDB
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        db_client.store_document({
            "content": generated,
            "metadata": {
                "doc_id": doc_id,
                "patient_id": patient_data.get("id", "UNKNOWN"),
                "doc_type": doc_type,
                "status": "generated"
            }
        })

        # 4: Authenticate with DocuSign (JWT)
        api_client, access_token = authenticate_docusign()
        user_info = api_client.get_user_info(access_token)
        account_id = user_info.accounts[0].account_id

        # 5: Create envelope & send for signing
        from docusign_esign import EnvelopesApi, EnvelopeDefinition, Document, Signer, Recipients
        envelope_api = EnvelopesApi(api_client)
        envelope_definition = EnvelopeDefinition(
            email_subject=f"Please sign your {doc_type} document",
            documents=[
                Document(
                    document_base64=base64.b64encode(pdf_bytes).decode("ascii"),
                    name=f"{doc_type.title()} Document.pdf",
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
        envelope_response = envelope_api.create_envelope(account_id, envelope_definition)

        # 6: Update LanceDB
        db_client.update_document_status(doc_id, {
            "status": "sent_for_signing",
            "envelope_id": envelope_response.envelope_id
        })

        return jsonify({
            "success": True,
            "doc_id": doc_id,
            "envelope_id": envelope_response.envelope_id
        })

    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=3000)
