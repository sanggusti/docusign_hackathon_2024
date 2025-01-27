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
            structured_prompt = f"""{prompt}

Please structure the response with clear sections:
1. Patient Information (if applicable)
2. Medical History (if applicable)
3. Current Assessment
4. Diagnosis and Plan
5. Follow-up Instructions

Format the response as a structured document with clear sections and proper medical terminology."""

            response = self.client.generate(
                model="command-r-plus",
                prompt=structured_prompt,
                max_tokens=2048,  # Increased for more detailed responses
                temperature=0.7,   # Slightly increased for more creative responses
                stop_sequences=["\n\n\n"],  # Stop on triple newline
                num_generations=1,
                presence_penalty=0.2,  # Add some variety
                frequency_penalty=0.3   # Reduce repetition
            )

            # Extract and clean the generated text
            generated_text = response.generations[0].text.strip()
            
            # Format the response for better structure
            formatted_text = self._format_medical_content(generated_text)
            
            return {
                "success": True,
                "content": formatted_text,
                "raw_text": generated_text
            }

        except Exception as e:
            return self._format_error(f"Document generation failed: {str(e)}")

    def _format_medical_content(self, content: str) -> str:
        """Format medical content with clear sections"""
        try:
            # Split content into sections
            sections = content.split('\n')
            formatted_sections = []
            current_section = ""
            
            for line in sections:
                if line.strip():
                    if any(header in line.lower() for header in ['patient information', 'medical history', 'assessment', 'diagnosis', 'plan', 'follow-up']):
                        # New section header
                        if current_section:
                            formatted_sections.append(current_section)
                        current_section = f"\n{line}\n{'=' * len(line)}\n"
                    else:
                        # Content line
                        current_section += f"{line}\n"
            
            # Add last section
            if current_section:
                formatted_sections.append(current_section)
                
            return "\n".join(formatted_sections)
            
        except Exception as e:
            print(f"Content formatting error: {str(e)}")
            return content

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

    def generate_insurance_comparison(self, criteria: str) -> List[Dict]:
        """Generate insurance comparison data"""
        try:
            prompt = f"""Generate a comparison of insurance plans based on these criteria:
{criteria}

Format the response as a JSON array of objects with these fields:
- insurance_plan (string): name of the plan
- monthly_premium (number): monthly cost
- coverage_level (string): basic, standard, or premium
- deductible (number): yearly deductible
- coverage_details (string): brief description of coverage
"""

            response = self.client.generate(
                model="command-r-plus",
                prompt=prompt,
                temperature=0.7,
                max_tokens=1000
            )

            # Parse the response
            try:
                content = response.generations[0].text
                # Extract JSON from the response
                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return []
            except Exception as e:
                print(f"Error parsing insurance comparison: {str(e)}")
                return []

        except Exception as e:
            print(f"Error generating insurance comparison: {str(e)}")
            return []

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