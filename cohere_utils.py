# cohere_utils.py
import cohere
import json
import re
import numpy as np
from typing import List, Dict, Union, Optional
from config import COHERE_API_KEY

class HealthcareCohereClient:
    def __init__(self):
        if not COHERE_API_KEY:
            raise ValueError("Cohere API key not found in environment variables")
        try:
            self.client = cohere.Client(COHERE_API_KEY)
            # Verify the key works
            self.client.tokenize(model="command", text="test")
        except Exception as e:
            raise ValueError(f"Failed to initialize Cohere client: {str(e)}")
        self.tools = self._setup_healthcare_tools()

    def _setup_healthcare_tools(self) -> List[dict]:
        """Define healthcare-specific tools for document generation."""
        # Each tool must have top-level "name", "description", and "parameters".
        return [
            {
                "name": "extract_patient_info",
                "description": "Extract structured patient information from raw text",
                "parameters": {
                    "raw_text": {
                        "description": "Unstructured text containing patient information",
                        "type": "string",
                        "required": True
                    }
                }
            },
            {
                "name": "generate_insurance_approval",
                "description": "Generate insurance approval documentation",
                "parameters": {
                    "insurance_provider": {
                        "description": "Name of insurance provider",
                        "type": "string",
                        "required": True
                    },
                    "procedures": {
                        "description": "List of procedures requiring approval",
                        "type": "array",
                        "required": True
                    }
                }
            }
        ]

    def generate_document(self, prompt: str, max_steps: int = 3) -> dict:
        """Generate healthcare document using tool-enabled Cohere model"""
        try:
            response = self.client.chat(
                model="command-r-plus",
                message=prompt,
                force_single_step=False,
                tools=self.tools,
                temperature=0.3
            )

            tool_results = []
            step_count = 0

            while response.tool_calls and step_count < max_steps:
                for tool_call in response.tool_calls:
                    try:
                        params = json.loads(tool_call.parameters)
                        if tool_call.name == "extract_patient_info":
                            output = self._handle_patient_info(params['raw_text'])
                        elif tool_call.name == "generate_insurance_approval":
                            output = self._handle_insurance_approval(
                                params['insurance_provider'],
                                params['procedures']
                            )
                        else:
                            continue
                        
                        tool_results.append({
                            "call": tool_call,
                            "outputs": [output]
                        })
                    except (KeyError, json.JSONDecodeError) as e:
                        print(f"Error processing tool call: {str(e)}")
                        continue

                response = self.client.chat(
                    model="command-r-plus",
                    message="",
                    tools=self.tools,
                    chat_history=response.chat_history,
                    tool_results=tool_results
                )
                step_count += 1

            return self._format_final_response(response.text)

        except Exception as e:
            return self._format_error(f"Unexpected Error: {str(e)}")

    def generate_embeddings(self, texts: Union[str, List[str]]) -> Optional[np.ndarray]:
        """Generate embeddings for medical text"""
        try:
            if isinstance(texts, str):
                texts = [texts]

            response = self.client.embed(
                texts=texts,
                model="embed-english-v3.0",
                input_type="search_document"
            )
            return np.array(response.embeddings)
        except Exception as e:
            print(f"Embedding Error: {str(e)}")
            return None

    def _handle_patient_info(self, raw_text: str) -> dict:
        """Process patient information extraction (mock implementation)"""
        return {
            "section": "patient_information",
            "content": {
                "name": "John Doe",
                "id": "12345",
                "source_text": raw_text
            }
        }

    def _handle_insurance_approval(self, provider: str, procedures: List[str]) -> dict:
        """Generate insurance approval documentation (mock implementation)"""
        return {
            "section": "insurance_approval",
            "content": {
                "provider": provider,
                "approved_procedures": procedures,
                "effective_date": "2024-05-01"
            }
        }

    def _format_final_response(self, response_text: str) -> dict:
        """Format and validate final response with robust JSON extraction"""
        try:
            # Clean markdown and non-breaking spaces
            cleaned = re.sub(r'```(?:json)?\s*', '', response_text, flags=re.DOTALL)
            cleaned = cleaned.replace('\xa0', ' ').strip()
            
            # Attempt to find JSON structure
            json_str = None
            try:
                # Try parsing entire response
                return {
                    "success": True,
                    "content": json.loads(cleaned),
                    "raw_text": response_text
                }
            except json.JSONDecodeError:
                # Try extracting JSON substring
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    return {
                        "success": True,
                        "content": json.loads(json_str),
                        "raw_text": response_text
                    }
                else:
                    raise
                    
        except Exception as e:
            print(f"JSON parsing failed: {str(e)}")
            return {
                "success": True,
                "content": cleaned,
                "warning": "Response contained non-JSON content"
            }

    def _format_error(self, message: str) -> dict:
        """Standard error response format"""
        return {
            "success": False,
            "error": message,
            "content": None
        }

# Usage Example
if __name__ == "__main__":
    client = HealthcareCohereClient()
    
    # Generate insurance approval document
    result = client.generate_document(
        "Generate insurance approval for MRI scan and physical therapy with Aetna"
    )
    print("Document Result:", json.dumps(result, indent=2))
    
    # Generate embeddings
    embeddings = client.generate_embeddings("Patient diagnosis: chronic migraines")
    print("\nEmbeddings Shape:", embeddings.shape if embeddings is not None else "Error")