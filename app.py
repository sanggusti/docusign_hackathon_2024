# Imports
import uuid
import base64
import json
from datetime import datetime
from io import BytesIO
import pandas as pd
import plotly.express as px
import plotly.utils

from config import COHERE_API_KEY, LANCEDB_PATH, DS_CONFIG, DS_JWT
from cohere_utils import HealthcareCohereClient
from fasthtml.common import *
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator
from docusign.ds_client import DSClient
from jwt_helpers.jwt_helper import get_jwt_token, create_api_client, get_private_key
from docusign_esign import EnvelopesApi, EnvelopeDefinition, Document, Signer, Recipients

# Initiate fasthtml
# variables
app, rt = fast_app('data/healthcare.db')
cohere_client = HealthcareCohereClient()
db_client = HealthcareVectorDB()
pdf_gen = PDFGenerator()

ROLES = ['Administration', 'Insurance', 'Prescription', 'Insurance Comparison']
DOC_TYPES = {
    'Insurance': ['identity', 'prognosis', 'items', 'procedure', 'costs'],
    'Prescription': ['medication', 'dosage', 'instructions'],
    'Insurance Comparison': ['plans', 'coverage', 'costs', 'benefits']
}

css = Style('''
    .container {
        scroll-behavior: smooth;
    }
    #intro-section {
        min-height: 40vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        padding: 2rem;
        background: linear-gradient(to bottom, #ffffff, #f3f4f6);
    }
    #features-section {
        padding: 2rem 0;
    }
    #workspace-section {
        min-height: 60vh;
        padding: 2rem 0;
    }
    #pdf-preview {
        width: 100%;
        height: 600px;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
    }
    .results-placeholder {
        height: 600px;
        border: 2px dashed #e5e7eb;
        border-radius: 0.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #6b7280;
        background: #f9fafb;
    }
    .htmx-indicator {
        opacity: 0;
        transition: opacity 500ms ease-in;
    }
    .htmx-request .htmx-indicator {
        opacity: 1;
    }
    .htmx-request.htmx-indicator {
        opacity: 1;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-radius: 50%;
        border-top: 4px solid #3498db;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .loading-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.9);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border-radius: 0.5rem;
    }
    
    .spinner-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.8);
        display: none;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }
    
    .htmx-request .spinner-overlay {
        display: flex;
    }
    
    .button-content {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .htmx-request .button-content {
        display: none;
    }
    
    .loading-text {
        display: none;
    }
    
    .htmx-request .loading-text {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
''')

def pdf_to_data_uri(pdf_bytes: bytes) -> str:
    """Convert PDF bytes to data URI for preview"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return f"data:application/pdf;base64,{base64_pdf}"

def format_medical_content(content: dict) -> str:
    """Format medical content for PDF generation based on integration_check.py success"""
    sections = []
    if isinstance(content, dict):
        if 'content' in content:
            content = content['content']
            if isinstance(content, dict):
                for section, data in content.items():
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
                sections.append(str(content))
    return "\n".join(sections)

# Root route
# Role selector, Model selector, document check
@rt("/")
def home():
    role_selector = Select(
        name="role", 
        id="role-select",
        cls="select select-bordered w-full",
        hx_get="/update_form",
        hx_target="#doc-form",
        hx_trigger="change"
    )(
        *[Option(role, value=role) for role in ROLES]
    )
    
    model_selector = Select(
        name="model",
        id="model-select",
        cls="select select-bordered w-full",
        hx_trigger="change"
    )(
        *[Option(model, value=model) for model in ['command-r-plus', 'command']]
    )
    doc_check = CheckboxX(
        label="Use existing patient records",
        name="use_existing",
        id="existing-check",
        hx_get="/toggle_search",
        hx_target="#patient-search",
        hx_trigger="click"
    )

    return Main(
        # Intro Section
        Section(
            H1("Healthcare Document Automation", cls="text-4xl font-bold mb-4"),
            P("""
                Streamline your healthcare documentation process with AI-powered generation 
                and secure digital signatures.
            """, cls="text-xl text-gray-600 max-w-2xl mx-auto"),
            id="intro-section",
            cls="text-center"
        ),
        
        # Features Section
        Section(
            Div(
                H2("Available Features", cls="text-2xl font-semibold mb-6 text-center"),
                Div(
                    Div(
                        H3("Document Generation", cls="text-lg font-semibold"),
                        P("Generate medical documents with AI assistance", cls="text-gray-600")
                    ),
                    Div(
                        H3("Insurance Comparison", cls="text-lg font-semibold"),
                        P("Compare insurance plans and coverage", cls="text-gray-600")
                    ),
                    Div(
                        H3("Digital Signatures", cls="text-lg font-semibold"),
                        P("Secure document signing with DocuSign", cls="text-gray-600")
                    ),
                    Div(
                        H3("Patient Records", cls="text-lg font-semibold"),
                        P("Efficient patient record management", cls="text-gray-600")
                    ),
                    cls="grid grid-cols-2 md:grid-cols-4 gap-6"
                ),
                cls="max-w-6xl mx-auto px-4"
            ),
            id="features-section",
            cls="bg-gray-50 py-12"
        ),
        
        # Workspace Section
        Section(
            Div(
                Div(
                    Card(
                        Form(
                            Group(
                                Label("Document Type:", cls="label"),
                                role_selector,
                                cls="form-control"
                            ),
                            Group(
                                Label("AI Model:", cls="label"),
                                model_selector,
                                cls="form-control"
                            ),
                            Group(
                                doc_check,
                                cls="form-control"
                            ),
                            Div(id="patient-search", cls="mt-2"),
                            Div(id="doc-form", cls="mt-4"),
                            Button(
                                Div(
                                    Span("Generate Document", cls="button-content"),
                                    Div(
                                        Div(cls="spinner"),
                                        Span("Generating...", cls="ml-2"),
                                        cls="loading-text"
                                    ),
                                    cls="flex items-center justify-center"
                                ),
                                type="submit",
                                hx_post="/generate", 
                                hx_target="#results-container",
                                hx_swap="innerHTML",
                                hx_include="#config-form",
                                cls="btn btn-primary mt-4 w-full relative"
                            ),
                            id="config-form"
                        ),
                        header=H2("Configuration", cls="card-title"),
                        cls="card bg-base-100 shadow-md"
                    ),
                    cls="w-full md:w-1/3"
                ),
                Div(
                    Card(
                        Div(
                            P("Your generated document and signing options will appear here.", 
                              cls="text-gray-500 text-center"),
                            # Add loading indicator
                            Div(
                                Div(cls="spinner"),
                                P("Generating document...", cls="text-gray-600 mt-2"),
                                cls="loading-overlay",
                                id="loading-indicator"
                            ),
                            cls="results-placeholder"
                        ),
                        id="results-container",
                        header=H2("Results", cls="card-title"),
                        cls="card bg-base-100 shadow-md relative"  # Add relative positioning
                    ),
                    cls="w-full md:w-2/3"
                ),
                cls="flex flex-col md:flex-row gap-6 max-w-7xl mx-auto px-4"
            ),
            id="workspace-section"
        ),
        cls="container mx-auto"
    )

@rt("/generate-document")
async def generate_document(request: Request):
    data = await request.json()
    doc_content = cohere_client.generate_document(data["prompt"])
    pdf_bytes = pdf_gen.generate_pdf(doc_content).read()
    db_client.store_document({
        "content": doc_content,
        "metadata": {
            "doc_id": str(uuid.uuid4()),
            "patient_id": data["patient_id"],
            "doc_type": data["doc_type"]
        }
    })

# Update from route
# doc fields
@rt("/update_form")
def update_form(role: str):
    if role == "Insurance Comparison":
        return Div(
            Group(
                Label("Comparison Criteria:", cls="label"),
                Textarea(
                    name="comparison_criteria",
                    placeholder="Enter specific requirements for insurance comparison...",
                    cls="textarea textarea-bordered h-24"
                ),
                cls="form-control"
            ),
            Button(
                "Compare Plans",
                hx_post="/insurance-comparison",
                hx_target="#comparison-results",
                cls="btn btn-primary mt-4"
            ),
            Div(id="comparison-results", cls="mt-4"),
            id="doc-form"
        )
    
    # Original form update logic
    checkboxes = [
        CheckboxX(
            label=doc.replace('_', ' ').title(),  # Convert snake_case to Title Case
            name=doc,
            id=f"check-{doc}",
            cls="form-checkbox",
            hx_get="/toggle_section",  # Optional: Add HTMX interaction if needed
            hx_target=f"#section-{doc}"
        )
        for doc in DOC_TYPES.get(role, [])
    ]
    
    return Div(
        H3(f"Select {role} Document Sections", cls="subhead"),
        Div(*checkboxes, cls="checkbox-group"),
        id="doc-form"
    )

@rt("/toggle_search")
def toggle_search(use_existing: bool):
    if use_existing:
        return Div(
            Input(type="text", name="patient_query", placeholder="Search patient records..."),
            Button("Search", hx_post="/search_patients", hx_target="#search-results"),
            Div(id="search-results"),
            id="patient-search"
        )
    return Div(id="patient-search")


# Upload button
# upload button view and action

# Generate route
# process input, generate document using cohere
# create pdf
# create docusign envelope
# return iframe(?)
@rt("/generate")
async def generate(request: Request):
    form = await request.form()
    role = form.get("role")
    model = form.get("model")
    patient_data = form.get("patient_query", "")
    use_existing = form.get("use_existing") == "true"

    try:
        # Retrieve or generate patient info
        if use_existing:
            query = str(patient_data) if patient_data else ""
            patient_record = db_client.retrieve_documents(query)[0]
        else:
            patient_record = {
                "id": f"PATIENT_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "data": patient_data
            }

        # Generate document content
        doc_content = cohere_client.generate_document(
            f"Generate {role} document for: {patient_data}"
        )

        # Format content for PDF
        if isinstance(doc_content, dict) and 'content' in doc_content:
            formatted_content = doc_content['content']
        else:
            formatted_content = doc_content

        # Format content properly before storing
        formatted_content = format_medical_content(doc_content)
        
        # Store in vector DB with proper content format
        doc_id = f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"Creating document with ID: {doc_id}")
        
        store_success = db_client.store_document({
            "document_id": doc_id,
            "content": formatted_content,
            "metadata": {
                "patient_id": patient_record['id'],
                "doc_type": role,
                "status": "generated"
            }
        })

        if not store_success:
            print(f"Failed to store document: {doc_id}")
            raise Exception("Failed to store document in database")

        print(f"Document stored successfully with ID: {doc_id}")
        
        # Create PDF with formatted content
        pdf_bytes = pdf_gen.generate_pdf({
            "title": f"{role} Document - {patient_record['id']}",
            "content": formatted_content
        }).read()

        # Return updated preview with signing button
        return Div(
            Iframe(
                src=pdf_to_data_uri(pdf_bytes), 
                width="100%", 
                height="500",
                id="pdf-preview"
            ),
            Button(
                "Send for Signature",
                hx_post=f"/sign/{doc_id}",
                hx_target="#signing-status",
                cls="btn btn-secondary mt-4"
            ),
            Div(id="signing-status", cls="mt-4"),  # Add container for signing status
            id="pdf-container"
        )

    except Exception as e:
        return Div(
            f"Error generating document: {str(e)}", 
            cls="text-red-500 p-2 rounded bg-red-50",
            id="pdf-preview"
        )

@rt("/insurance-comparison")
async def insurance_comparison(request: Request):
    form = await request.form()
    try:
        # Get insurance data
        insurance_data = cohere_client.generate_insurance_comparison(
            form.getlist("comparison_criteria")[0] if form.getlist("comparison_criteria") else ""
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(insurance_data)
        
        # Create comparison chart
        fig = px.bar(
            df,
            x='insurance_plan',
            y='monthly_premium',
            color='coverage_level',
            title='Insurance Plan Comparison'
        )
        
        # Convert to JSON for frontend
        chart_json = json.dumps(fig.to_dict())
        
        return Div(
            Div(
                id="chart-container",
                hx_vals=chart_json,
                cls="w-full h-96"
            ),
            Table(
                Thead(
                    Tr(
                        *[Th(col) for col in df.columns]
                    )
                ),
                Tbody(
                    *[
                        Tr(*[Td(row[col]) for col in df.columns])
                        for _, row in df.iterrows()
                    ]
                ),
                cls="table table-compact w-full"
            ),
            id="comparison-results"
        )
    except Exception as e:
        return Div(
            f"Error generating comparison: {str(e)}",
            cls="text-red-500 p-2 rounded bg-red-50",
            id="comparison-results"
        )

def authenticate_docusign():
    """Helper function to authenticate with DocuSign"""
    try:
        # Get private key
        private_key = get_private_key(DS_JWT["private_key_file"])
        
        # Get JWT token
        token = get_jwt_token(  # Store the token response
            private_key=private_key,
            scopes=["signature", "impersonation"],
            auth_server=DS_JWT["authorization_server"],
            client_id=DS_JWT["ds_client_id"],
            impersonated_user_id=DS_JWT["ds_impersonated_user_id"]
        )
        
        # Create API client
        api_client = create_api_client(
            base_path=DS_CONFIG["base_path"],
            access_token=token.access_token  # Use token.access_token
        )
        
        # Get user info for verification
        user_info = api_client.get_user_info(token.access_token)  # Use token.access_token
        account_id = user_info.accounts[0].account_id
        
        return api_client, account_id
        
    except Exception as e:
        print(f"DocuSign authentication error: {str(e)}")
        raise

@rt("/sign/{doc_id}")
async def sign_document(doc_id: str):
    try:
        print(f"Starting signing process for document: {doc_id}")
        
        # Get document from DB with exact document_id match
        print(f"Retrieving document from database...")
        docs = db_client.retrieve_documents(f"document_id:{doc_id}")
        
        if not docs:
            print(f"Document not found: {doc_id}")
            raise ValueError(f"Document {doc_id} not found")
        
        doc = docs[0]
        print(f"Document retrieved with ID: {doc_id}")

        # Initialize DocuSign with JWT auth
        api_client, account_id = authenticate_docusign()
        
        try:
            # Generate fresh PDF with formatted content
            print("Generating PDF for signing...")
            pdf_content = {
                "title": f"{doc['doc_type']} Document",
                "content": doc['content']
            }
            pdf_bytes = pdf_gen.generate_pdf(pdf_content).read()
            print("PDF generated successfully")

            # Create envelope
            envelope_api = EnvelopesApi(api_client)
            envelope_definition = EnvelopeDefinition(
                email_subject=f"Please sign your {doc['doc_type']} document",
                documents=[
                    Document(
                        document_base64=base64.b64encode(pdf_bytes).decode("ascii"),
                        name=f"{doc['doc_type']} Document.pdf",
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
            
            # Send envelope
            envelope_response = envelope_api.create_envelope(
                account_id=account_id,
                envelope_definition=envelope_definition
            )
            
            # Try to update document status
            update_result = db_client.update_document_status(
                doc_id=doc_id,
                updates={
                    "status": "sent_for_signing",
                    "envelope_id": envelope_response.envelope_id,
                    "signature_status": "pending"
                }
            )
            
            if not update_result:
                print(f"Warning: Failed to update document status in database")
                # Continue anyway since envelope was sent
            
            return Div(
                P("✓ Document sent for signing successfully!", cls="text-green-600 font-semibold"),
                P(f"Envelope ID: {envelope_response.envelope_id}", cls="text-sm text-gray-600"),
                P("Note: Document has been sent but status update may have failed.", 
                  cls="text-yellow-600 text-sm" if not update_result else "hidden"),
                id="signing-status"
            )

        except Exception as e:
            print(f"DocuSign or database error: {str(e)}")
            raise

    except Exception as e:
        print(f"Signing error: {str(e)}")
        return Div(
            P(f"Error sending document for signature: {str(e)}", 
              cls="text-red-500"),
            id="signing-status"
        )

# Insurance comparison dashboard
# show chart

serve()