# Healthcare Document Automation System

An AI-powered healthcare document automation system with DocuSign integration, built for the DocuSign Hackathon 2024.

## Features

- 🤖 AI-powered document generation using Cohere
- 📄 Dynamic PDF creation with formatted medical records
- ✍️ Secure digital signatures via DocuSign
- 📊 Insurance plan comparison and analysis
- 🗄️ Vector database storage with LanceDB
- 🎯 Role-based document workflows
- 📱 Responsive web interface

## Prerequisites

- Python 3.8+
- DocuSign Developer Account
- Cohere API Key
- LanceDB (local installation)

## Setup

1. Clone the repository:

    ```bash
    git clone https://github.com/your-username/docusign_hackathon_2024.git
    cd docusign_hackathon_2024
    ```

2. Install Dependencies

    ```bash
    pip install -r requirements.txt
    ```

3. Set up environment variables in `.env`, most of them you will get when creating a docusign project. Cohere is by register and get the api key yourself.

    ```bash
    DS_CLIENT_ID=your_docusign_client_id
    DS_CLIENT_SECRET=your_docusign_client_secret
    DS_IMPERSONATED_USER_ID=your_docusign_user_id
    COHERE_API_KEY=your_cohere_api_key
    APP_URL=http://localhost:3000
    LANCEDB_PATH=data/healthcare_db
    ```

4. Create DocuSign JWT configuration:
    a. Generate RSA keypair:

    ```bash
    openssl genrsa -out private.key 2048
    openssl rsa -pubout -in private.key -out public.key
    ```

    b. Upload public.key to DocuSign Admin console and note the Integration Key

5. Add session key:

    ```bash
    # Generate random session key
    python -c "import os; print(os.urandom(24).hex())" > .sesskey
    ```

6. Update docusign configuration
    - put your `private.key` in project root
    - Configure `DS_JWT` in `config.py` with your integration key
    - Set `signer_email` and `signer_name` in `DS_CONFIG`

Case:

Insurance, healthcare, apotechary and administration auto contract agent.

Keywords: Remote Signing, Embedded Signing, Contract agents, Agreement Workflow, Optimize Cost.

## Running the Application

1. Start the FastHTML server:

    ```bash
    // For a FastHTML app
    python app.py

    // Integration test
    python integration_check.py
    ```

2. Access the application at <http://localhost:3000>

## API Routes

- `/` - Main interface
- `/generate` - Generate medical documents
- `/sign/{doc_id}` - Send document for signing
- `/insurance-comparison` - Compare insurance plans

## Environment Setup Details

DocuSign Configuration

1. Create a DocuSign developer account
2. Create an Integration Key in Admin console
3. Enable JWT Grant
4. Upload your public key
5. Note your Integration Key and User ID

Required Files

1. `.env` - Environment variables

    ```text
    DS_CLIENT_ID=your_integration_key
    DS_CLIENT_SECRET=your_secret
    DS_IMPERSONATED_USER_ID=your_user_id
    COHERE_API_KEY=your_cohere_key
    ```

2. private.key - RSA private key for DocuSign JWT
    - Generate using OpenSSL
    - Keep secure and never commit
    - Required for JWT authentication
3. .sesskey - Session key for Flask
    - Generate random key
    - Keep secure and never commit

Security Notes

- Never commit .env, private.key, or .sesskey
- Add them to .gitignore
- Keep backup copies secure
- Rotate keys periodically
