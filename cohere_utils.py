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

    def generate_document(self, prompt: str, max_steps: int = 3) -> dict:
        """Generate healthcare document using Cohere's generate model"""
        try:
            response = self.client.generate(
                model="command-r-plus",
                prompt=prompt,
                max_tokens=2048,  # Increased for more detailed responses
                temperature=0.7,   # Slightly increased for more creative responses
                stop_sequences=["\n\n\n"],  # Stop on triple newline
                num_generations=1,
                presence_penalty=0.2,  # Add some variety
                frequency_penalty=0.3   # Reduce repetition
            )

            # Extract and clean the generated text
            generated_text = response.generations[0].text.strip()
            print(f"Received from Cohere: {generated_text}")

            return {
                "success": True,
                "content": generated_text,
                "raw_text": generated_text
            }

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
            
            # Attempt to parse JSON with more robust handling
            try:
                decoder = json.JSONDecoder()
                json_content, idx = decoder.raw_decode(cleaned)
                return {
                    "success": True,
                    "content": json_content,
                    "raw_text": response_text
                }
            except json.JSONDecodeError as e:
                # Try to extract JSON from partial response
                start_idx = cleaned.find('{')
                end_idx = cleaned.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    potential_json = cleaned[start_idx:end_idx+1]
                    try:
                        json_content = json.loads(potential_json)
                        return {
                            "success": True,
                            "content": json_content,
                            "raw_text": response_text,
                            "warning": "Extracted JSON from response"
                        }
                    except json.JSONDecodeError:
                        pass
                # If parsing fails, return the cleaned text
                return {
                    "success": True,
                    "content": cleaned,
                    "raw_text": response_text,
                    "warning": "Response contained non-JSON content"
                }
        except Exception as e:
            print(f"JSON parsing failed: {str(e)}")
            return {
                "success": False,
                "error": f"JSON parsing failed: {str(e)}",
                "content": None
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