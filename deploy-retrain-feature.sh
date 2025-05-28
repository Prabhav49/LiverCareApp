#!/bin/bash

# Model Retraining Feature Deployment Script
# This script deploys the complete model retraining feature with feedback functionality

set -e

echo "🚀 Deploying Model Retraining Feature..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed or not in PATH"
    exit 1
fi

# Check if we're connected to a cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Not connected to a Kubernetes cluster"
    exit 1
fi

echo "✅ Kubernetes cluster connection verified"

# Build and tag the model-retrain Docker image
echo "📦 Building model-retrain Docker image..."
cd model-retrain
docker build -t model-retrain:latest .
cd ..

echo "✅ Model-retrain image built successfully"

# Apply persistent volumes first
echo "💾 Creating persistent volumes..."
kubectl apply -f k8s-manifests/persistent-volumes.yaml

# Wait for PVCs to be bound
echo "⏳ Waiting for persistent volume claims to be bound..."
kubectl wait --for=condition=Bound pvc/training-data-pvc -n mlops-project --timeout=60s
kubectl wait --for=condition=Bound pvc/model-storage-pvc -n mlops-project --timeout=60s
kubectl wait --for=condition=Bound pvc/shared-model-pvc -n mlops-project --timeout=60s

echo "✅ Persistent volumes are ready"

# Run initialization job
echo "🔧 Running data initialization job..."
kubectl apply -f k8s-manifests/init-job.yaml

# Wait for init job to complete
echo "⏳ Waiting for initialization job to complete..."
kubectl wait --for=condition=complete job/model-data-init-job -n mlops-project --timeout=120s

echo "✅ Data initialization completed"

# Deploy model-retrain service
echo "🤖 Deploying model retraining service..."
kubectl apply -f k8s-manifests/model-retrain-deployment.yaml
kubectl apply -f k8s-manifests/model-retrain-service.yaml

# Update backend deployment with shared volume
echo "🔄 Updating backend deployment..."
kubectl apply -f k8s-manifests/backend-deployment.yaml

# Update frontend deployment with retrain service URL
echo "🌐 Updating frontend deployment..."
kubectl apply -f k8s-manifests/frontend-deployment.yaml

# Wait for deployments to be ready
echo "⏳ Waiting for deployments to be ready..."
kubectl rollout status deployment/model-retrain-deployment -n mlops-project --timeout=300s
kubectl rollout status deployment/backend-deployment -n mlops-project --timeout=300s
kubectl rollout status deployment/frontend-deployment -n mlops-project --timeout=300s

echo "✅ All deployments are ready"

# Show deployment status
echo "📊 Deployment Status:"
kubectl get pods -n mlops-project -l app=model-retrain
kubectl get pods -n mlops-project -l app=backend
kubectl get pods -n mlops-project -l app=frontend

echo ""
echo "🎉 Model Retraining Feature Deployment Complete!"
echo ""
echo "Features enabled:"
echo "  ✓ User feedback buttons (Correct/Wrong/Don't Know)"
echo "  ✓ Automatic data collection from feedback"
echo "  ✓ Background model retraining"
echo "  ✓ Dynamic model updates in backend"
echo "  ✓ Persistent storage for data and models"
echo ""
echo "📝 How to use:"
echo "  1. Make predictions via the frontend"
echo "  2. Use feedback buttons to provide accuracy feedback"
echo "  3. Model will automatically retrain with new data"
echo "  4. Backend will use the latest trained model"
echo ""
echo "🔍 Monitor retraining status:"
echo "  kubectl logs -f deployment/model-retrain-deployment -n mlops-project"
echo ""
echo "🔧 Check feedback data:"
echo "  kubectl exec -it deployment/model-retrain-deployment -n mlops-project -- ls -la /data/"