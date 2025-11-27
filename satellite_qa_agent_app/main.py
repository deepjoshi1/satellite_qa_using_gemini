import os
import uuid
import requests
import json
from flask import Flask, request, render_template_string
from google.cloud import storage

app = Flask(__name__)

# --- Configuration ---
# The URL of your existing Cloud Run QA service.
CLOUD_RUN_URL = "https://satellite-inspector-tool-90805393985.us-central1.run.app/analyze"

# TODO: Create a new GCS bucket and replace this placeholder.
# This bucket must be in the same project and be accessible by your App Engine service account.
GCS_BUCKET_NAME = "your-unique-bucket-name"

# Initialize the GCS client
storage_client = storage.Client()

# --- HTML Template ---
# A simple UI with a file upload form and a results section.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Satellite Image QA</title>
    <style>
        body { font-family: sans-serif; margin: 2em; background-color: #f4f4f9; color: #333; }
        h1, h2 { color: #333; }
        .container { max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .upload-form { margin-bottom: 2em; }
        .result { display: flex; align-items: flex-start; margin-bottom: 1.5em; border-bottom: 1px solid #ddd; padding-bottom: 1.5em; }
        .result img { max-width: 250px; max-height: 250px; margin-right: 20px; border-radius: 4px; border: 1px solid #ccc; }
        .result pre { background-color: #eee; padding: 15px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; flex-grow: 1; font-size: 0.9em; }
        input[type="submit"] { font-size: 1em; padding: 10px 15px; cursor: pointer; background-color: #4285F4; color: white; border: none; border-radius: 4px; }
        input[type="submit"]:hover { background-color: #357ae8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Satellite Image Quality Assurance</h1>
        <form class="upload-form" action="/upload" method="post" enctype="multipart/form-data">
            <p>Select one or more satellite images to analyze:</p>
            <input type="file" name="files" multiple required>
            <br><br>
            <input type="submit" value="Run QA">
        </form>

        {% if results %}
            <h2>Analysis Results</h2>
            {% for result in results %}
                <div class="result">
                    <img src="{{ result.image_url }}" alt="Satellite Image">
                    <pre>{{ result.analysis }}</pre>
                </div>
            {% endfor %}
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    """Renders the main upload page."""
    return render_template_string(HTML_TEMPLATE)

@app.route("/upload", methods=["POST"])
def upload():
    """Handles file uploads, calls the QA service, and displays results."""
    uploaded_files = request.files.getlist("files")
    results = []

    if not uploaded_files or uploaded_files[0].filename == '':
        return "No files selected", 400

    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    for file in uploaded_files:
        filename = f"uploads/{uuid.uuid4()}-{file.filename}"
        blob = bucket.blob(filename)

        blob.upload_from_file(file.stream, content_type=file.content_type)
        blob.make_public()

        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{filename}"
        response = requests.post(CLOUD_RUN_URL, json={"gcs_uri": gcs_uri})

        results.append({
            "image_url": blob.public_url,
            "analysis": json.dumps(response.json(), indent=2)
        })

    return render_template_string(HTML_TEMPLATE, results=results)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)