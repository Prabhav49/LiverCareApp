from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import numpy as np
import pandas as pd
import pickle
import os
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import time

app = FastAPI()

# Define Prometheus metrics
REQUESTS = Counter('backend_requests_total', 'Total number of requests to backend', ['method', 'endpoint', 'status'])
PREDICTIONS = Counter('backend_predictions_total', 'Total number of predictions made', ['result'])
PREDICTION_TIME = Histogram('backend_prediction_processing_seconds', 'Time spent processing prediction')

# Load model
try:
    current_dir = os.path.dirname(__file__)  # /home/prabhav/SPE_Project/backend/src
    model_path = os.path.join(current_dir, "../models/logistic_model.pkl")  # resolves correctly
    with open(model_path, "rb") as f:
        model = pickle.load(f)
except Exception as e:
    raise RuntimeError(f"Failed to load model: {str(e)}")


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