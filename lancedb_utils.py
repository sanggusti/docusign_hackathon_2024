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
            pa.field("document_id", pa.string()),
            pa.field("patient_id", pa.string()),
            pa.field("doc_type", pa.string()),
            pa.field("content", pa.string()),
            pa.field("timestamp", pa.timestamp('ns')),
            pa.field("status", pa.string()),
            pa.field("envelope_id", pa.string()),
            pa.field("signature_status", pa.string())
        ])
        
        try:
            # Try to open existing table
            table = self.db.open_table("healthcare_docs")
            
            # If schema needs update, create new table with updated schema
            if set(table.schema.names) != set(schema.names):
                # Backup existing data if needed
                existing_data = table.to_pandas()
                
                # Drop existing table
                self.db.drop_table("healthcare_docs")
                
                # Create new table with updated schema
                table = self.db.create_table("healthcare_docs", schema=schema)
                
                # Migrate existing data if any
                if not existing_data.empty:
                    # Add missing columns with default values
                    for col in schema.names:
                        if col not in existing_data.columns:
                            if col == "status":
                                existing_data[col] = "migrated"
                            elif col == "envelope_id":
                                existing_data[col] = ""
                            elif col == "signature_status":
                                existing_data[col] = "pending"
                    
                    # Add data back to table
                    table.add(existing_data)
                
            return table
            
        except Exception:
            # Create new table if doesn't exist
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
            
            self.table.add([{
                "vector": vector,
                "document_id": document["metadata"]["doc_id"],
                "patient_id": document["metadata"]["patient_id"],
                "doc_type": document["metadata"]["doc_type"],
                "content": document["content"],
                "timestamp": datetime.now().isoformat(),
                "status": document["metadata"].get("status", "created"),
                "envelope_id": document["metadata"].get("envelope_id", ""),
                "signature_status": document["metadata"].get("signature_status", "pending")
            }])
            return True
        except Exception as e:
            print(f"Storage error: {str(e)}")
            return False

    def retrieve_documents(self, query: str, k: int = 5) -> List[Dict]:
        try:
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
        """Update document status"""
        try:
            df = self.table.to_pandas()
            mask = df['document_id'] == doc_id
            
            if not mask.any():
                print(f"Document {doc_id} not found")
                return False
                
            # Update fields
            for key, value in updates.items():
                df.loc[mask, key] = value
                
            # Replace table contents
            self.table.delete(where="true")  # Delete all records
            self.table.add(df)
            
            return True
        except Exception as e:
            print(f"Update error: {str(e)}")
            return False
