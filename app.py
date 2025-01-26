# Imports
import uuid
import base64
import json
from datetime import datetime
from io import BytesIO

from config import COHERE_API_KEY, LANCEDB_PATH
from cohere_utils import HealthcareCohereClient
from fasthtml.common import *
from lancedb_utils import HealthcareVectorDB
from pdf_utils import PDFGenerator

# Initiate fasthtml
# variables
app, rt = fast_app('data/healthcare.db')
cohere_client = HealthcareCohereClient()
db_client = HealthcareVectorDB()
pdf_gen = PDFGenerator()

ROLES = ['Administration', 'Insurance', 'Prescription']
DOC_TYPES = {
    'Insurance': ['identity', 'prognosis', 'items', 'procedure', 'costs'],
    'Prescription': ['medication', 'dosage', 'instructions']
}

css = Style('''
    #pdf-preview {
        width: 100%;
        height: 500px;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        margin-top: 1rem;
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
''')

def pdf_to_data_uri(pdf_bytes: bytes) -> str:
    """Convert PDF bytes to data URI for preview"""
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return f"data:application/pdf;base64,{base64_pdf}"

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
        H1("Healthcare Document Automation", cls="text-2xl font-bold mb-4"),
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
                    Button("Generate Document", 
                          type="submit",
                          hx_post="/generate", 
                          hx_target="#pdf-preview",
                          hx_swap="outerHTML",
                          hx_include="#config-form",  # Include all form data
                          cls="btn btn-primary mt-4"),
                    id="config-form"
                ),
                header=H2("Configuration", cls="card-title"),
                cls="card bg-base-100 shadow-md"
            ),
            Card(
                Div(id="pdf-preview", cls="htmx-indicator"),
                Div(id="signing-status", cls="mt-4"),
                header=H2("Document Preview", cls="card-title"),
                # footer=Button("Approve & Send", 
                #             hx_post="/approve", 
                #             hx_target="#signing-status",
                #             cls="btn btn-secondary"),
                cls="card bg-base-100 shadow-md"
            ),
            cls="grid grid-cols-1 md:grid-cols-2 gap-6"
        ),
        cls="container mx-auto p-4"
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
            patient_record = db_client.retrieve_documents(patient_data)[0]
        else:
            patient_record = {
                "id": f"PATIENT_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "data": patient_data
            }

        # Generate document content
        doc_content = cohere_client.generate_document(
            f"Generate {role} document for: {patient_data}"
        )

        # Create PDF
        pdf_bytes = pdf_gen.generate_pdf({
            "title": f"{role} Document - {patient_record['id']}",
            "content": doc_content
        }).read()

        # Store in vector DB
        db_client.store_document({
            "metadata": {
                "doc_id": f"DOC_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "patient_id": patient_record['id'],
                "doc_type": role
            },
            "content": json.dumps(doc_content)
        })

        # Return updated preview
        return Iframe(
            src=pdf_to_data_uri(pdf_bytes), 
            width="100%", 
            height="500",
            id="pdf-preview",
            # Add refresh trigger for parent element
            hx_trigger="load from:body"
        )

    except Exception as e:
        return Div(
            f"Error generating document: {str(e)}", 
            cls="text-red-500 p-2 rounded bg-red-50",
            id="pdf-preview"
        )

# Insurance comparison dashboard
# show chart

serve()