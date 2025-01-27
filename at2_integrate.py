from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import re

from cohere_utils import HealthcareCohereClient
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator
from docusign.ds_client import DSClient
from jwt_helpers.jwt_helper import get_jwt_token, create_api_client, get_private_key
from config import DS_CONFIG, DS_JWT

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'

# Initialize components
cohere_client = HealthcareCohereClient()
db_client = HealthcareVectorDB()
pdf_gen = PDFGenerator()

def bootstrap_lancedb():
    """Initialize LanceDB with sample data if needed"""
    try:
        # Create healthcare_docs table if not exists
        sample_doc = {
            "content": "Sample document content",
            "metadata": {
                "doc_id": "SAMPLE_DOC_001",
                "patient_id": "SAMPLE_PATIENT_001",
                "doc_type": "sample",
                "status": "initialized"
            }
        }
        db_client.store_document(sample_doc)
        print("✓ LanceDB initialized successfully")
    except Exception as e:
        print(f"LanceDB initialization error: {str(e)}")

def format_patient_data(data: dict) -> str:
    """Format patient data into a structured prompt"""
    sections = [
        f"Patient Name: {data.get('name', 'N/A')}",
        f"Patient ID: {data.get('id', 'N/A')}"
    ]
    
    # Add any additional fields
    for key, value in data.items():
        if key not in ['name', 'id']:
            sections.append(f"{key.title()}: {value}")
    
    return "\n".join(sections)

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

def clean_json_content(content: str) -> str:
    """Clean and format JSON content from Cohere response"""
    # Remove markdown code blocks
    content = re.sub(r'```(?:json)?\n?(.*?)```', r'\1', content, flags=re.DOTALL)
    # Remove non-breaking spaces
    content = content.replace('\xa0', ' ')
    # Convert to pretty format
    try:
        json_obj = json.loads(content)
        return json.dumps(json_obj, indent=2)
    except:
        return content
    

def format_medical_record(cohere_response: dict) -> str:
    """Convert Cohere response to formatted text with robust type handling"""
    try:
        content = cohere_response.get('content', cohere_response) if isinstance(cohere_response, dict) else cohere_response

        # Normalize content to list of records
        records = []
        if isinstance(content, dict):
            records = [content]
        elif isinstance(content, list):
            records = content
        elif isinstance(content, str):
            try:
                parsed = json.loads(content)
                records = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                return content  # Return raw text if not JSON
        else:
            records = [content]

        sections = []
        
        for record in records:
            if not isinstance(record, dict):
                sections.append(str(record))
                continue

            # Patient Information
            sections.append("\nPatient Information\n------------------")
            patient_info = record.get("patient_information", {})
            if isinstance(patient_info, dict):
                name = patient_info.get('name', 'N/A')
                patient_id = patient_info.get('id', 'N/A')
                sections.extend([f"Name: {name}", f"ID: {patient_id}"])
            else:
                sections.append(f"Patient Info: {str(patient_info)}")

            # Medical History (FIXED KEYS HERE)
            sections.append("\nMedical History\n--------------")
            medical_history = record.get("medical_history", [])
            if isinstance(medical_history, list):
                for entry in medical_history:
                    if isinstance(entry, dict):
                        condition = entry.get('condition', 'N/A')
                        date = entry.get('date', 'N/A')
                        treatment = entry.get('treatment', 'N/A')
                        sections.append(f"- {date}: {condition} - {treatment}")
                    else:
                        sections.append(f"- {str(entry)}")
            else:
                sections.append(f"Medical History: {str(medical_history)}")

            # Current Condition
            sections.append("\nCurrent Condition\n----------------")
            current_condition = record.get("current_condition", "N/A")
            sections.append(str(current_condition))

            # Recommendations
            sections.append("\nRecommendations\n--------------")
            recommendations = record.get("recommendations", [])
            if isinstance(recommendations, list):
                for rec in recommendations:
                    sections.append(f"- {rec}")
            else:
                sections.append(f"Recommendations: {str(recommendations)}")

        return "\n".join(sections)
        
    except Exception as e:
        return f"Error formatting document: {str(e)}\nRaw content: {str(cohere_response)}"
    

@app.route('/generate_and_sign', methods=['POST'])
def generate_and_sign():
    try:
        # Validate input data
        data = request.get_json()
        if not data:
            raise ValueError("No JSON data provided")
            
        patient_data = data.get('patient_data')
        doc_type = data.get('doc_type', 'medical_record')
        
        if not patient_data:
            raise ValueError("No patient data provided")

        # Format patient data for Cohere
        formatted_data = format_patient_data(patient_data)
        
        # Generate document with Cohere
        generation_prompt = (
            f"Generate a {doc_type} document with the following patient information:\n"
            f"{formatted_data}\n\n"
            "Structure the document as a JSON array with exactly one element containing these sections:\n"
            "- patient_information (object with name and id)\n"
            "- medical_history (array of entries)\n"
            "- current_condition (string)\n"
            "- recommendations (array of strings)\n\n"
            "Return ONLY valid JSON without any additional text or markdown formatting."
        )
        
        print(f"Sending prompt to Cohere: {generation_prompt}")
        cohere_response = cohere_client.generate_document(generation_prompt)
        print(f"Received from Cohere: {cohere_response}")

        # Check if Cohere generation failed
        if not cohere_response.get('success', False):
            return jsonify({
                "success": False,
                "error": f"Document generation failed: {cohere_response.get('error', 'Unknown error')}",
                "details": cohere_response
            }), 500
        
        # Format the medical record directly from Cohere response
        formatted_content = format_medical_record(cohere_response)
        
        # Create PDF with formatted content
        pdf_content = {
            "title": f"{doc_type.title()} - {patient_data.get('name', 'Unknown Patient')}",
            "content": formatted_content,
            "metadata": {
                "patient_id": patient_data.get('id', 'UNKNOWN'),
                "doc_type": doc_type,
                "generated_date": datetime.now().isoformat()
            }
        }
        
        pdf_bytes = pdf_gen.generate_pdf(pdf_content).read()

        # Store in LanceDB
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        store_success = db_client.store_document({
            "content": formatted_content,  # Store the text content
            "metadata": {
                "doc_id": doc_id,
                "patient_id": patient_data.get('id', 'UNKNOWN'),
                "patient_name": patient_data.get('name', 'Unknown'),
                "doc_type": doc_type,
                "status": "generated",
                "created_at": datetime.now().isoformat()
            }
        })

        if not store_success:
            app.logger.error(f"Failed to store document {doc_id}")
            raise Exception("Failed to store document in database")

        # Initialize DocuSign components here...
        api_client, access_token = authenticate_docusign()
        
        # Get user info
        user_info = api_client.get_user_info(access_token)
        account_id = user_info.accounts[0].account_id

        # Create envelope
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
        
        envelope_response = envelope_api.create_envelope(
            account_id=account_id,
            envelope_definition=envelope_definition
        )

        return jsonify({
            "success": True,
            "doc_id": doc_id,
            "envelope_id": envelope_response.envelope_id,
            "message": "Document generated and sent for signing"
        })

    except ValueError as e:
        print(f"Validation error: {str(e)}")  # Debug log
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except Exception as e:
        print(f"Processing error: {str(e)}")  # Debug log
        return jsonify({
            "success": False,
            "error": str(e),
            "details": {
                "raw_content": raw_content if 'raw_content' in locals() else None,
                "formatted_content": formatted_content if 'formatted_content' in locals() else None
            }
        }), 500

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
    # Bootstrap LanceDB on startup
    bootstrap_lancedb()
    app.run(debug=True, port=3000)
