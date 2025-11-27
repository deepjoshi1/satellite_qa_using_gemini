import base64
import os
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel, Part, SafetySetting
from pydantic import BaseModel, Field

# --- 1. Define the Output Schema using Pydantic ---
# This ensures the AI returns exactly the JSON structure you asked for.

class IssueAssessment(BaseModel):
    """Assessment for a specific category of issue."""
    detected: bool = Field(..., description="Whether this specific issue is present.")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    reason: str = Field(..., description="A concise explanation of the visual evidence found.")

class SatelliteAnalysis(BaseModel):
    """The master JSON structure for the satellite image analysis."""
    has_clouds: IssueAssessment
    has_snow: IssueAssessment
    has_color_issues: IssueAssessment
    has_other_issues: IssueAssessment

# --- 2. The Agent Class ---

class SatelliteInspector:
    def __init__(self, project_id: str, location: str = "us-central1"):
        """
        Initialize the Vertex AI Gemini agent.
        """
        self.project_id = project_id
        self.location = location
        
        # Initialize Vertex AI SDK
        vertexai.init(project=project_id, location=location)

        # We use Gemini 1.5 Flash for speed and high-quality vision capabilities
        self.model = GenerativeModel("gemini-2.5-flash")

        # Define the system prompt to teach the AI about satellite imagery
        self.system_instruction = """
        You are an expert Remote Sensing Analyst AI. 
        Your job is to analyze satellite imagery (optical/RGB) and detect quality issues.
        
        Definitions for your analysis:
        1. CLOUDS: Look for white, puffy, opaque textures that obscure the ground. Distinguish from smoke or haze if possible.
        2. SNOW: Look for white, smooth textures on terrain, specifically on mountain peaks or covering large flat areas. Distinguish from clouds by looking for ground features (valleys, rivers) cut into the white.
        3. COLOR ISSUES: Look for unnatural color casts (e.g., whole image is purple/green), oversaturation, banding (colored stripes), or severe atmospheric haze that washes out color.
        4. OTHER ISSUES: Look for missing data (black pixels/voids), severe blurriness, stitching artifacts, or digital noise.
        
        Provide a confidence score (0.0 to 1.0) and specific visual reasoning for every assessment.
        """

    def analyze_from_uri(self, gcs_uri: str, mime_type: str = "image/jpeg") -> str:
        """
        Analyzes an image directly from Google Cloud Storage (gs://...).
        This is preferred for Cloud Agents as it avoids file upload overhead.
        """
        image_part = Part.from_uri(uri=gcs_uri, mime_type=mime_type)
        
        return self._generate(image_part)

    def analyze_image(self, image_path: str) -> str:
        """
        Reads a local image and sends it to Gemini for analysis.
        Returns a JSON string.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        # Load image data
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        return self._generate(image_part)

    def _generate(self, image_part: Part) -> str:
        """Internal helper to run the generation."""
        # Configure the generation to force JSON output based on our Pydantic schema
        generation_config = {
            "response_mime_type": "application/json",
            "response_schema": SatelliteAnalysis.model_json_schema()
        }

        # Send request
        response = self.model.generate_content(
            [self.system_instruction, image_part, "Analyze this satellite image for issues."],
            generation_config=generation_config,
            safety_settings=[
                SafetySetting(
                    category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
                )
            ]
        )

        return response.text

# --- 3. Example Usage (if run directly) ---
if __name__ == "__main__":
    # Configuration
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not PROJECT_ID:
        print("GOOGLE_CLOUD_PROJECT env var not set, attempting to find from gcloud config...")
        # This command reads the project ID from your active gcloud configuration.
        # You must be logged in to gcloud for this to work (`gcloud auth login`).
        PROJECT_ID = os.popen("gcloud config get-value project").read().strip()

    # Placeholder for testing - replace with a real path
    IMAGE_PATH = "test_satellite.jpg" 

    try:
        agent = SatelliteInspector(project_id=PROJECT_ID)
        print(f"Analyzing {IMAGE_PATH}...")
        
        # In a real run, ensure the file exists or this will throw
        if os.path.exists(IMAGE_PATH):
            result_json = agent.analyze_image(IMAGE_PATH)
            print("\nAnalysis Result:")
            print(result_json)
        else:
            print(f"Please place a test image at '{IMAGE_PATH}' to run this script.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")