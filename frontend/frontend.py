from flask import Flask, render_template, request, jsonify, flash, Response
import requests
from wtforms import Form, FloatField, SelectField, validators
import re
import os
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

app = Flask(__name__)
app.secret_key = 'liver_disease_prediction_app'  # Required for flash messages

# Define Prometheus metrics
REQUESTS = Counter('frontend_requests_total', 'Total number of requests to frontend', ['method', 'endpoint', 'status'])
BACKEND_REQUESTS = Counter('frontend_backend_requests_total', 'Total number of backend API calls', ['status'])
PREDICTIONS = Counter('frontend_predictions_total', 'Total number of predictions requested', ['result'])
REQUEST_TIME = Histogram('frontend_request_processing_seconds', 'Time spent processing request', ['endpoint'])

class FloatValidationError(ValueError):
    pass

def validate_float(form, field):
    if field.data is None:
        raise validators.ValidationError('This field is required.')
    
    try:
        value = float(field.data)
        if value < 0:
            raise validators.ValidationError(f'{field.label.text} cannot be negative.')
    except (ValueError, TypeError):
        raise validators.ValidationError(f'{field.label.text} must be a valid number.')

class PredictionForm(Form):
    age = FloatField('Age', [
        validators.InputRequired(message="Age is required"),
        validators.NumberRange(min=0.1, max=120, message="Age must be between 0.1 and 120")
    ])
    
    gender = SelectField('Gender', choices=[('1', 'Male'), ('0', 'Female')], 
                         validators=[validators.InputRequired(message="Gender is required")])
    
    total_bilirubin = FloatField('Total Bilirubin', [
        validators.InputRequired(message="Total Bilirubin is required"),
        validators.NumberRange(min=0, max=100, message="Total Bilirubin must be between 0 and 100")
    ])
    
    direct_bilirubin = FloatField('Direct Bilirubin', [
        validators.InputRequired(message="Direct Bilirubin is required"),
        validators.NumberRange(min=0, max=100, message="Direct Bilirubin must be between 0 and 100")
    ])
    
    alkaline_phosphotase = FloatField('Alkaline Phosphotase', [
        validators.InputRequired(message="Alkaline Phosphotase is required"),
        validators.NumberRange(min=0, max=2000, message="Alkaline Phosphotase must be between 0 and 2000")
    ])
    
    alanine_aminotransferase = FloatField('Alanine Aminotransferase', [
        validators.InputRequired(message="Alanine Aminotransferase is required"),
        validators.NumberRange(min=0, max=2000, message="Alanine Aminotransferase must be between 0 and 2000")
    ])
    
    aspartate_aminotransferase = FloatField('Aspartate Aminotransferase', [
        validators.InputRequired(message="Aspartate Aminotransferase is required"),
        validators.NumberRange(min=0, max=2000, message="Aspartate Aminotransferase must be between 0 and 2000")
    ])
    
    total_proteins = FloatField('Total Proteins', [
        validators.InputRequired(message="Total Proteins is required"),
        validators.NumberRange(min=0, max=20, message="Total Proteins must be between 0 and 20")
    ])
    
    albumin = FloatField('Albumin', [
        validators.InputRequired(message="Albumin is required"),
        validators.NumberRange(min=0, max=10, message="Albumin must be between 0 and 10")
    ])
    
    albumin_globulin_ratio = FloatField('Albumin Globulin Ratio', [
        validators.InputRequired(message="Albumin Globulin Ratio is required"),
        validators.NumberRange(min=0, max=10, message="Albumin Globulin Ratio must be between 0 and 10")
    ])

@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/', methods=['GET', 'POST'])
def index():
    start_time = time.time()
    form = PredictionForm(request.form)
    prediction_result = None
    error_message = None
    
    if request.method == 'POST':
        if form.validate():
            try:
                # Additional custom validation to ensure all fields are valid float values
                for field_name, field in form._fields.items():
                    if field_name != 'gender':
                        try:
                            value = float(field.data)
                            if not isinstance(value, float):
                                form.errors.setdefault(field_name, []).append(f"{field.label.text} must be a valid number.")
                                return render_template('index.html', form=form, result=None, error="Please fix form errors.")
                        except (ValueError, TypeError):
                            form.errors.setdefault(field_name, []).append(f"{field.label.text} must be a valid number.")
                            return render_template('index.html', form=form, result=None, error="Please fix form errors.")
                
                # Prepare data for API request
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
                
                # Make API request to the backend using the environment variable
                backend_url = os.getenv('BACKEND_URL', 'http://backend-service:8000')
                response = requests.post(f'{backend_url}/predict', json=payload)
                
                if response.status_code == 200:
                    prediction_result = response.json()
                    BACKEND_REQUESTS.labels(status='success').inc()
                    # Record prediction result
                    if 'prediction' in prediction_result:
                        PREDICTIONS.labels(result=str(prediction_result['prediction'])).inc()
                else:
                    BACKEND_REQUESTS.labels(status='error').inc()
                    error_message = f"API Error: {response.status_code}"
                    try:
                        error_details = response.json().get('detail', 'Unknown error')
                        error_message += f" - {error_details}"
                    except:
                        pass
            except Exception as e:
                BACKEND_REQUESTS.labels(status='exception').inc()
                error_message = f"Error: {str(e)}"
        else:
            # Form validation failed
            error_message = "Please fix the errors in the form."
    
    # Record metrics
    process_time = time.time() - start_time
    REQUEST_TIME.labels(endpoint='/').observe(process_time)
    status = "200" if error_message is None else "400"
    REQUESTS.labels(method=request.method, endpoint='/', status=status).inc()
    
    return render_template('index.html', form=form, result=prediction_result, error=error_message)

# Create a simple API endpoint for testing
@app.route('/api/predict', methods=['POST'])
def api_predict():
    start_time = time.time()
    try:
        data = request.json
        
        # Validate that all required fields are present and valid
        required_fields = [
            'age', 'gender', 'total_bilirubin', 'direct_bilirubin', 
            'alkaline_phosphotase', 'alanine_aminotransferase', 'aspartate_aminotransferase',
            'total_proteins', 'albumin', 'albumin_globulin_ratio'
        ]
        
        for field in required_fields:
            if field not in data:
                REQUESTS.labels(method=request.method, endpoint='/api/predict', status='400').inc()
                return jsonify({"error": f"Missing required field: {field}"}), 400
            
            # Validate numeric fields (except gender)
            if field != 'gender':
                try:
                    value = float(data[field])
                    if value < 0:
                        REQUESTS.labels(method=request.method, endpoint='/api/predict', status='400').inc()
                        return jsonify({"error": f"{field} cannot be negative"}), 400
                except (ValueError, TypeError):
                    REQUESTS.labels(method=request.method, endpoint='/api/predict', status='400').inc()
                    return jsonify({"error": f"{field} must be a valid number"}), 400
        
        # Validate gender specifically
        if data['gender'] not in [0, 1, '0', '1']:
            REQUESTS.labels(method=request.method, endpoint='/api/predict', status='400').inc()
            return jsonify({"error": "Gender must be 0 (Female) or 1 (Male)"}), 400
            
        # Convert gender to int if it's a string
        if isinstance(data['gender'], str):
            data['gender'] = int(data['gender'])
            
        backend_url = os.getenv('BACKEND_URL', 'http://backend-service:8000')
        response = requests.post(f'{backend_url}/predict', json=data)
        
        status_code = response.status_code
        if status_code == 200:
            BACKEND_REQUESTS.labels(status='success').inc()
            result = response.json()
            if 'prediction' in result:
                PREDICTIONS.labels(result=str(result['prediction'])).inc()
        else:
            BACKEND_REQUESTS.labels(status='error').inc()
            
        # Record metrics
        process_time = time.time() - start_time
        REQUEST_TIME.labels(endpoint='/api/predict').observe(process_time)
        REQUESTS.labels(method=request.method, endpoint='/api/predict', status=str(status_code)).inc()
            
        return jsonify(response.json()), response.status_code
    except Exception as e:
        REQUESTS.labels(method=request.method, endpoint='/api/predict', status='500').inc()
        BACKEND_REQUESTS.labels(status='exception').inc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)