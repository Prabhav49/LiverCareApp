from flask import Flask, render_template, request, jsonify, flash
import requests
from wtforms import Form, FloatField, SelectField, validators
import os
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

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

class PredictionForm(Form):
    age = FloatField('Age', [validators.InputRequired()])
    gender = SelectField('Gender', choices=[('1', 'Male'), ('0', 'Female')], 
                        validators=[validators.InputRequired()])
    total_bilirubin = FloatField('Total Bilirubin', [validators.InputRequired()])
    direct_bilirubin = FloatField('Direct Bilirubin', [validators.InputRequired()])
    alkaline_phosphotase = FloatField('Alkaline Phosphotase', [validators.InputRequired()])
    alanine_aminotransferase = FloatField('Alanine Aminotransferase', [validators.InputRequired()])
    aspartate_aminotransferase = FloatField('Aspartate Aminotransferase', [validators.InputRequired()])
    total_proteins = FloatField('Total Proteins', [validators.InputRequired()])
    albumin = FloatField('Albumin', [validators.InputRequired()])
    albumin_globulin_ratio = FloatField('Albumin Globulin Ratio', [validators.InputRequired()])

def call_backend_api(payload):
    """Centralized function to call backend API"""
    backend_url = os.getenv('BACKEND_URL', 'http://backend-service:8000')
    try:
        response = http.post(
            f"{backend_url}/predict",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
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
                payload = {
                    'age': float(form.age.data),
                    'gender': int(form.gender.data),
                    'total_bilirubin': float(form.total_bilirubin.data),
                    'direct_bilirubin': float(form.direct_bilirubin.data),
                    'alkaline_phosphotase': float(form.alkaline_phosphotase.data),
                    'alanine_aminotransferase': float(form.alanine_aminotransferase.data),
                    'aspartate_aminotransferase': float(form.aspartate_aminotransferase.data),
                    'total_proteins': float(form.total_proteins.data),
                    'albumin': float(form.albumin.data),
                    'albumin_globulin_ratio': float(form.albumin_globulin_ratio.data)
                }
                
                response = call_backend_api(payload)
                prediction_result = response.json()
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
    
    return render_template('index.html', form=form, result=prediction_result, error=error_message)

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/predict', methods=['POST'])
def api_predict():
    try:
        data = request.json
        
        required_fields = [
            'age', 'gender', 'total_bilirubin', 'direct_bilirubin',
            'alkaline_phosphotase', 'alanine_aminotransferase', 'aspartate_aminotransferase',
            'total_proteins', 'albumin', 'albumin_globulin_ratio'
        ]
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
            
        response = call_backend_api(data)
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)