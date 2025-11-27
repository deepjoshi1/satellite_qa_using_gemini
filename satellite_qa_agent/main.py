import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from satellite_qa_agent import SatelliteInspector, SatelliteAnalysis

app = FastAPI(title="Satellite Image Inspector Tool")

# Initialize the agent globally
# We get the Project ID from the environment variable (automatically set in Cloud Run)
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") # This is set automatically in Cloud Run
if not PROJECT_ID:
    # Fallback for local development, requires `gcloud auth application-default login`
    print("GOOGLE_CLOUD_PROJECT not set, attempting to find from gcloud config")
    PROJECT_ID = os.popen("gcloud config get-value project").read().strip()
agent = SatelliteInspector(project_id=PROJECT_ID)

@app.get("/")
def read_root():
    """A default root endpoint to let users know the service is running."""
    return {
        "message": "Satellite Inspector Tool is running.",
        "documentation": "/docs",
        "openapi_schema": "/openapi.json"
    }

class AnalysisRequest(BaseModel):
    gcs_uri: str

@app.post("/analyze", response_model=SatelliteAnalysis)
async def analyze_endpoint(request: AnalysisRequest):
    """
    Endpoint for Vertex AI Agents to call. 
    Accepts a GS URI (gs://bucket/image.jpg) and returns the analysis.
    """
    try:
        print(f"Received request for: {request.gcs_uri}")
        
        # Call the agent
        result_json_str = agent.analyze_from_uri(request.gcs_uri)
        
        # Parse the JSON string back to a dictionary for FastAPI
        result_data = json.loads(result_json_str)
        
        return result_data
    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}