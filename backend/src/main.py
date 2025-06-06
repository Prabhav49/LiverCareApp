from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import numpy as np
import pandas as pd
import pickle
import os
import threading
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

# Define Prometheus metrics
REQUESTS = Counter('backend_requests_total', 'Total number of requests to backend', ['method', 'endpoint', 'status'])
PREDICTIONS = Counter('backend_predictions_total', 'Total number of predictions made', ['result'])
PREDICTION_TIME = Histogram('backend_prediction_processing_seconds', 'Time spent processing prediction')

# Global variables for model management
model = None
model_lock = threading.Lock()
last_model_check = 0
MODEL_CHECK_INTERVAL = 30  # Check for new model every 30 seconds

# Model paths
SHARED_MODEL_PATH = os.getenv('SHARED_MODEL_PATH', '/shared-models/logistic_model.pkl')
FALLBACK_MODEL_PATH = os.path.join(os.path.dirname(__file__), "../models/logistic_model.pkl")

def load_model():
    """Load model from shared path or fallback to local path"""
    global model
    
    # Try shared model path first (for updated models from retraining)
    if os.path.exists(SHARED_MODEL_PATH):
        try:
            with open(SHARED_MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            print(f"Loaded model from shared path: {SHARED_MODEL_PATH}")
            return
        except Exception as e:
            print(f"Failed to load from shared path: {e}")
    
    # Fallback to local model
    try:
        with open(FALLBACK_MODEL_PATH, "rb") as f:
            model = pickle.load(f)
        print(f"Loaded model from fallback path: {FALLBACK_MODEL_PATH}")
    except Exception as e:
        raise RuntimeError(f"Failed to load model from both paths: {str(e)}")

def check_for_model_updates():
    """Check if model file has been updated and reload if necessary"""
    global last_model_check, model
    
    current_time = time.time()
    if current_time - last_model_check < MODEL_CHECK_INTERVAL:
        return
    
    last_model_check = current_time
    
    if os.path.exists(SHARED_MODEL_PATH):
        try:
            # Check if file was modified recently (within last check interval + buffer)
            file_mtime = os.path.getmtime(SHARED_MODEL_PATH)
            if current_time - file_mtime < MODEL_CHECK_INTERVAL + 10:
                with model_lock:
                    with open(SHARED_MODEL_PATH, "rb") as f:
                        new_model = pickle.load(f)
                    model = new_model
                    print(f"Model reloaded from shared path at {time.ctime()}")
        except Exception as e:
            print(f"Error checking/reloading model: {e}")

# Initialize model
load_model()

class PatientData(BaseModel):
    age: float
    gender: int 
    total_bilirubin: float
    direct_bilirubin: float
    alkaline_phosphotase: float
    alanine_aminotransferase: float
    aspartate_aminotransferase: float 
    total_proteins: float
    albumin: float
    albumin_globulin_ratio: float

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    REQUESTS.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict")
async def predict(data: PatientData):
    try:
        start_time = time.time()
        check_for_model_updates()
        
        input_values = [
            data.age,
            data.gender,
            data.total_bilirubin,
            data.direct_bilirubin,
            data.alkaline_phosphotase,
            data.alanine_aminotransferase,
            data.aspartate_aminotransferase,
            data.total_proteins,
            data.albumin,
            data.albumin_globulin_ratio
        ]
        
        input_array = np.array(input_values).reshape(1, -1)
        
        scaled_data = (input_array - model['mean']) / model['std']
        pca_data = np.dot(scaled_data, model['eigenvectors'])
        pca_with_bias = np.c_[np.ones((pca_data.shape[0], 1)), pca_data]
        probability = 1 / (1 + np.exp(-np.dot(pca_with_bias, model['weights'])))
        
        prediction_result = int(probability[0][0] >= 0.5)
        PREDICTIONS.labels(result=str(prediction_result)).inc()
        
        process_time = time.time() - start_time
        PREDICTION_TIME.observe(process_time)
        
        return {
            "probability": float(probability[0][0]),
            "prediction": prediction_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}