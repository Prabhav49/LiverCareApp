# Model Retraining Feature Documentation

## Overview

This feature implements an automated model retraining system with user feedback for the liver disease prediction application. Users can provide feedback on prediction accuracy, which triggers automatic model retraining with the new data.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│    Frontend     │    │     Backend      │    │  Model Retrain      │
│   (Flask App)   │    │   (FastAPI)      │    │   Service (Flask)   │
│                 │    │                  │    │                     │
│ ┌─────────────┐ │    │ ┌──────────────┐ │    │ ┌─────────────────┐ │
│ │  Feedback   │ │    │ │   Model      │ │    │ │   Training      │ │
│ │   Buttons   │ │───▶│ │  Prediction  │ │    │ │   Pipeline      │ │
│ │             │ │    │ │              │ │    │ │                 │ │
│ └─────────────┘ │    │ └──────────────┘ │    │ └─────────────────┘ │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
         │                       │                         │
         │                       │                         │
         └───────────────────────┼─────────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │   Shared Persistent     │
                    │     Volumes             │
                    │                         │
                    │ • Training Data (5GB)   │
                    │ • Model Storage (2GB)   │
                    │ • Shared Models (1GB)   │
                    └─────────────────────────┘
```

## Features

### 1. User Feedback System
- **Three feedback buttons** after each prediction:
  - ✅ **Prediction is Correct**: Adds data to training set with correct label
  - ❌ **Prediction is Wrong**: Adds data to training set with flipped label
  - ❓ **Don't Know**: Stores feedback but doesn't trigger retraining

### 2. Automatic Data Collection
- Feedback data is stored in CSV format with timestamps
- Original training data format is preserved
- Data includes all patient features plus actual outcomes

### 3. Background Model Retraining
- Triggered automatically when feedback is provided (correct/wrong)
- Combines original training data with new feedback data
- Uses the same ML pipeline as original training
- Thread-safe with locking mechanisms

### 4. Dynamic Model Updates
- Backend checks for updated models every 30 seconds
- Automatically loads new models without restart
- Fallback to original model if shared model unavailable

### 5. Persistent Storage
- **Training Data PVC**: Stores original and feedback data (5GB)
- **Model Storage PVC**: Stores versioned trained models (2GB)
- **Shared Model PVC**: Shared between backend and retrain service (1GB)

## Deployment

### Quick Start
```bash
# Deploy the complete retraining feature
./deploy-retrain-feature.sh
```

### Manual Deployment Steps

1. **Build the retrain service image:**
   ```bash
   cd model-retrain
   docker build -t model-retrain:latest .
   cd ..
   ```

2. **Create persistent volumes:**
   ```bash
   kubectl apply -f k8s-manifests/persistent-volumes.yaml
   ```

3. **Initialize data:**
   ```bash
   kubectl apply -f k8s-manifests/init-job.yaml
   kubectl wait --for=condition=complete job/model-data-init-job -n mlops-project --timeout=120s
   ```

4. **Deploy services:**
   ```bash
   kubectl apply -f k8s-manifests/model-retrain-deployment.yaml
   kubectl apply -f k8s-manifests/model-retrain-service.yaml
   kubectl apply -f k8s-manifests/backend-deployment.yaml
   kubectl apply -f k8s-manifests/frontend-deployment.yaml
   ```

## Usage Workflow

1. **Make a Prediction**
   - User enters patient data in the frontend
   - System provides prediction with probability

2. **Provide Feedback**
   - User clicks one of three feedback buttons
   - Frontend sends feedback data to backend
   - Backend forwards to retrain service (for correct/wrong feedback)

3. **Automatic Retraining**
   - Retrain service stores feedback data
   - Background thread combines original + feedback data
   - Model is retrained using same pipeline
   - New model is saved to shared volume

4. **Model Update**
   - Backend detects new model file
   - Automatically loads updated model
   - Future predictions use retrained model

## Monitoring

### Check Retraining Status
```bash
# View retrain service logs
kubectl logs -f deployment/model-retrain-deployment -n mlops-project

# Check service health
kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- curl http://localhost:8080/health

# View retraining status
kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- curl http://localhost:8080/retrain_status
```

### Inspect Data
```bash
# Check feedback data
kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- ls -la /data/

# View feedback CSV
kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- head /data/feedback_data.csv

# Check model versions
kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- ls -la /models/
```

### Monitor Backend Model Updates
```bash
# Check backend logs for model reloading
kubectl logs -f deployment/backend-deployment -n mlops-project
```

## API Endpoints

### Frontend (`frontend-service:5000`)
- `POST /feedback` - Submit user feedback

### Backend (`backend-service:8000`)
- `POST /predict` - Get prediction (automatically uses latest model)
- `GET /health` - Health check

### Retrain Service (`model-retrain-service:8080`)
- `POST /add_feedback_data` - Add feedback data and trigger retraining
- `GET /health` - Health check with retraining status
- `GET /retrain_status` - Detailed retraining status

## File Structure

```
model-retrain/
├── Dockerfile
├── requirements.txt
├── data/
│   └── raw/
│       └── Liver Patient Dataset (LPD)_train.csv
├── models/
│   └── logistic_model.pkl
└── src/
    └── retrain_service.py

k8s-manifests/
├── model-retrain-deployment.yaml
├── model-retrain-service.yaml
├── persistent-volumes.yaml
├── init-job.yaml
├── backend-deployment.yaml (updated)
└── frontend-deployment.yaml (updated)
```

## Configuration

### Environment Variables

**Model Retrain Service:**
- `DATA_PATH`: Path for training data storage (default: `/data`)
- `MODEL_PATH`: Path for model storage (default: `/models`)
- `SHARED_MODEL_PATH`: Path for shared models (default: `/shared-models`)

**Backend:**
- `SHARED_MODEL_PATH`: Path to shared model file (default: `/shared-models/logistic_model.pkl`)

**Frontend:**
- `RETRAIN_SERVICE_URL`: URL for retrain service (default: `http://model-retrain-service:8080`)

## Troubleshooting

### Common Issues

1. **PVC Not Binding**
   ```bash
   kubectl get pvc -n mlops-project
   kubectl describe pvc shared-model-pvc -n mlops-project
   ```

2. **Retrain Service Not Starting**
   ```bash
   kubectl logs deployment/model-retrain-deployment -n mlops-project
   kubectl describe pod <retrain-pod-name> -n mlops-project
   ```

3. **Model Not Updating**
   ```bash
   # Check if new model exists
   kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- ls -la /shared-models/
   
   # Check backend logs for reload messages
   kubectl logs deployment/backend-deployment -n mlops-project | grep -i "model"
   ```

4. **Feedback Data Not Saving**
   ```bash
   # Check retrain service logs
   kubectl logs deployment/model-retrain-deployment -n mlops-project | grep -i feedback
   
   # Verify volume mounts
   kubectl describe pod <retrain-pod-name> -n mlops-project
   ```

## Performance Considerations

- **Retraining Frequency**: Currently triggers on every feedback. Consider batching for production
- **Model Size**: L1-regularized logistic regression is lightweight for frequent retraining
- **Storage**: PVCs are sized for moderate data growth. Monitor usage
- **Resource Limits**: Retrain service limited to 2GB RAM, 1 CPU. Adjust based on data size

## Security Notes

- All services run with appropriate service accounts
- Inter-service communication uses cluster DNS
- Persistent volumes are mounted read-write only where needed
- No external exposure of retrain service (ClusterIP only)