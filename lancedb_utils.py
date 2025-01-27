import lancedb
import numpy as np
import pyarrow as pa
from datetime import datetime
from typing import List, Dict, Optional
from config import COHERE_API_KEY, LANCEDB_PATH
from cohere_utils import HealthcareCohereClient

cohere_client = HealthcareCohereClient()

# store document metadata
# table add
# get insurance comparison
class HealthcareVectorDB:
    def __init__(self):
        self.db = lancedb.connect(LANCEDB_PATH)
        self.table = self._initialize_table()
        self.insurance_table = self._initialize_insurance_table()
        
    def _initialize_table(self):
        """Initialize table with complete schema"""
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), 1024)),
            pa.field("document_id", pa.string()),  # Primary ID field
            pa.field("patient_id", pa.string()),
            pa.field("doc_type", pa.string()),
            pa.field("content", pa.string()),
            pa.field("timestamp", pa.timestamp('ns')),
            pa.field("status", pa.string()),
            pa.field("envelope_id", pa.string()),
            pa.field("signature_status", pa.string())
        ])
        
        try:
            table = self.db.open_table("healthcare_docs")
            if set(table.schema.names) != set(schema.names):
                existing_data = table.to_pandas()
                self.db.drop_table("healthcare_docs")
                table = self.db.create_table("healthcare_docs", schema=schema)
                
                if not existing_data.empty:
                    # Map old column names to new ones if needed
                    if 'doc_id' in existing_data.columns:
                        existing_data['document_id'] = existing_data['doc_id']
                        existing_data.drop('doc_id', axis=1, inplace=True)
                    
                    # Add missing columns with default values
                    for col in schema.names:
                        if col not in existing_data.columns:
                            if col == "status":
                                existing_data[col] = "migrated"
                            elif col == "envelope_id":
                                existing_data[col] = ""
                            elif col == "signature_status":
                                existing_data[col] = "pending"
                            elif col == "vector":
                                # Generate dummy vectors if needed
                                existing_data[col] = [np.zeros(1024) for _ in range(len(existing_data))]
                    
                    table.add(existing_data)
            return table
        except Exception as e:
            print(f"Table initialization error: {str(e)}")
            return self.db.create_table("healthcare_docs", schema=schema)

    def _initialize_insurance_table(self):
        schema = pa.schema([
            pa.field("procedure", pa.string()),
            pa.field("cost", pa.float64()),
            pa.field("common_coverage", pa.string())
        ])
        
        try:
            return self.db.create_table("insurance_data", schema=schema)
        except Exception:
            return self.db.open_table("insurance_data")

    def store_document(self, document: Dict) -> bool:
        """Store document with all required fields"""
        try:
            embeddings = cohere_client.generate_embeddings(document["content"])
            if embeddings is None:
                return False

            vector = embeddings[0].tolist()
            doc_id = document["document_id"]  # Use only document_id
            
            print(f"Storing document with ID: {doc_id}")
            
            data = {
                "vector": vector,
                "document_id": doc_id,
                "patient_id": document["metadata"]["patient_id"],
                "doc_type": document["metadata"]["doc_type"],
                "content": document["content"],
                "timestamp": datetime.now(),  # Changed to datetime object
                "status": document["metadata"].get("status", "created"),
                "envelope_id": document["metadata"].get("envelope_id", ""),
                "signature_status": document["metadata"].get("signature_status", "pending")
            }
            
            print(f"Data fields to store: {list(data.keys())}")
            self.table.add([data])
            return True
            
        except Exception as e:
            print(f"Storage error: {str(e)}")
            return False

    def retrieve_documents(self, query: str, k: int = 5) -> List[Dict]:
        """Retrieve documents with improved query handling"""
        try:
            # Handle ID-based queries differently
            if "doc_id:" in query or "document_id:" in query:
                doc_id = query.split(":", 1)[1].strip()
                print(f"Searching for document ID: {doc_id}")
                
                # Use LanceDB's where clause to search by document_id
                results = self.table.search().where(f"document_id = '{doc_id}'").limit(1).to_pandas()
                
                print(f"Found documents: {len(results)}")
                if not results.empty:
                    print(f"First match: {results.iloc[0].to_dict()}")
                    return results.to_dict("records")
                
                print("No matching documents found")
                return []
            
            # For content-based searches, use embeddings
            query_embedding = cohere_client.generate_embeddings(query)
            if query_embedding is None:
                return []

            results = self.table.search(query_embedding[0]).limit(k).to_pandas()
            return results.to_dict("records")
            
        except Exception as e:
            print(f"Retrieval error: {str(e)}")
            return []

    def get_insurance_comparison(self, procedures: List[str]) -> List[Dict]:
        if not procedures:
            return []
            
        try:
            # LanceDB filtering and aggregation
            df = self.insurance_table.to_pandas()
            filtered_df = df[df['procedure'].isin(procedures)]
            result = filtered_df.groupby('procedure').agg({
                'cost': 'mean',
                'common_coverage': lambda x: x.mode().iloc[0] if not x.empty else None
            }).reset_index()
            
            result.columns = ['procedure', 'avg_cost', 'common_coverage']
            return result.to_dict('records')
            
        except Exception as e:
            print(f"Insurance comparison error: {str(e)}")
            return []

    def add_insurance_data(self, data: List[Dict]) -> bool:
        """Helper method to add insurance data"""
        try:
            self.insurance_table.add(data)
            return True
        except Exception as e:
            print(f"Error adding insurance data: {str(e)}")
            return False
        
    
    def update_document_status(self, doc_id: str, updates: Dict) -> bool:
        """Update document status with improved error handling and logging"""
        try:
            # Get current data
            print(f"Updating document {doc_id}")
            results = self.table.search().where(f"document_id = '{doc_id}'").to_pandas()
            
            if results.empty:
                print(f"Document {doc_id} not found in search results")
                return False
            
            # Create updated row
            updated_row = results.iloc[0].copy()
            for key, value in updates.items():
                print(f"Setting {key} = {value}")
                updated_row[key] = value
            
            # Delete existing record
            print("Deleting existing record...")
            self.table.delete(where=f"document_id = '{doc_id}'")
            
            # Add updated record
            print("Adding updated record...")
            self.table.add([updated_row.to_dict()])
            
            print(f"Successfully updated document {doc_id}")
            return True
            
        except Exception as e:
            print(f"Update error: {str(e)}")
            print(f"Update attempted on columns: {list(updates.keys())}")
            print(f"Current table schema: {self.table.schema.names}")
            return False
