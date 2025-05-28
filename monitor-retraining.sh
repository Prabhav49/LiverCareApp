#!/bin/bash

# Model Retraining Monitoring Script
# This script helps monitor feedback data and model retraining status

NAMESPACE="mlops-project"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔍 Model Retraining System Monitor${NC}"
echo "=========================================="

# Check if model-retrain pod is running
echo -e "\n${YELLOW}📦 Model Retrain Pod Status:${NC}"
kubectl get pods -n $NAMESPACE -l app=model-retrain

# Check model-retrain service health
echo -e "\n${YELLOW}🏥 Model Retrain Service Health:${NC}"
RETRAIN_PORT=$(kubectl get svc model-retrain-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
if [ ! -z "$RETRAIN_PORT" ]; then
    MINIKUBE_IP=$(minikube ip)
    echo "Health endpoint: http://$MINIKUBE_IP:$RETRAIN_PORT/health"
    curl -s "http://$MINIKUBE_IP:$RETRAIN_PORT/health" | jq . 2>/dev/null || curl -s "http://$MINIKUBE_IP:$RETRAIN_PORT/health"
else
    echo "Service not available yet or NodePort not assigned"
fi

# Show recent logs
echo -e "\n${YELLOW}📋 Recent Model Retrain Logs (last 20 lines):${NC}"
kubectl logs -n $NAMESPACE -l app=model-retrain --tail=20

# Check for feedback data files in the pod
echo -e "\n${YELLOW}📁 Feedback Data Files:${NC}"
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=model-retrain -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ ! -z "$POD_NAME" ]; then
    echo "Checking feedback data in pod: $POD_NAME"
    kubectl exec -n $NAMESPACE $POD_NAME -- ls -la /app/feedback_data/ 2>/dev/null || echo "Feedback data directory not found or empty"
else
    echo "No model-retrain pod found"
fi

# Check for updated models
echo -e "\n${YELLOW}🤖 Model Files:${NC}"
if [ ! -z "$POD_NAME" ]; then
    kubectl exec -n $NAMESPACE $POD_NAME -- ls -la /app/models/ 2>/dev/null || echo "Models directory not found"
else
    echo "No model-retrain pod found"
fi

# Show retraining status
echo -e "\n${YELLOW}🔄 Retraining Status:${NC}"
if [ ! -z "$RETRAIN_PORT" ]; then
    curl -s "http://$MINIKUBE_IP:$RETRAIN_PORT/retrain_status" | jq . 2>/dev/null || curl -s "http://$MINIKUBE_IP:$RETRAIN_PORT/retrain_status"
else
    echo "Retrain service not available"
fi

echo -e "\n${GREEN}✅ Monitoring complete!${NC}"
echo ""
echo "To continuously monitor logs, run:"
echo "kubectl logs -f deployment/model-retrain-deployment -n $NAMESPACE"
echo ""
echo "To test feedback submission:"
echo "1. Go to frontend and make a prediction"
echo "2. Click 'Prediction is Wrong' or 'Prediction is Correct'"
echo "3. Check logs: kubectl logs -f deployment/model-retrain-deployment -n $NAMESPACE"