from flask import Flask, render_template, request, jsonify, flash
import requests
from wtforms import Form, FloatField, SelectField, validators
import re
import os  # <-- Add this import
from urllib3.util.retry import Retry  # <-- For retry logic
from requests.adapters import HTTPAdapter  # <-- For retry logic

app = Flask(__name__)
app.secret_key = 'liver_disease_prediction_app'

# Configure retry strategy for requests
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[408, 429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("http://", adapter)

# ... (keep all your existing form classes and validation code) ...

def call_backend_api(payload):
    """Centralized function to call backend API"""
    backend_url = os.getenv('BACKEND_URL', 'http://backend-service:8000')
    try:
        response = http.post(
            f"{backend_url}/predict",
            json=payload,
            timeout=10  # 10 seconds timeout
        )
        response.raise_for_status()  # Raises exception for 4XX/5XX
        return response
    except requests.exceptions.RequestException as e:
        raise Exception(f"Backend connection failed: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def index():
    form = PredictionForm(request.form)
    prediction_result = None
    error_message = None
    
    if request.method == 'POST':
        if form.validate():
            try:
                # ... (keep your existing validation code) ...
                
                payload = {
                    'age': float(form.age.data),
                    'gender': int(form.gender.data),
                    # ... (rest of your payload construction) ...
                }
                
                response = call_backend_api(payload)  # <-- Use centralized function
                prediction_result = response.json()
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
    
    return render_template('index.html', form=form, result=prediction_result, error=error_message)

@app.route('/api/predict', methods=['POST'])
def api_predict():
    try:
        data = request.json
        # ... (keep your existing validation code) ...
        
        response = call_backend_api(data)  # <-- Use centralized function with 'data' not 'payload'
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500