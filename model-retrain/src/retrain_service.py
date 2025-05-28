from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import os
import pickle
import csv
from datetime import datetime
import threading
import time
import shutil

app = Flask(__name__)

# Global variables for thread safety
retraining_lock = threading.Lock()
is_retraining = False

# Paths for persistent volumes
DATA_PATH = os.getenv('DATA_PATH', '/data')
MODEL_PATH = os.getenv('MODEL_PATH', '/models')
SHARED_MODEL_PATH = os.getenv('SHARED_MODEL_PATH', '/shared-models')  # Shared with backend

# Ensure directories exist
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(os.path.join(DATA_PATH, 'raw'), exist_ok=True)
os.makedirs(MODEL_PATH, exist_ok=True)
os.makedirs(SHARED_MODEL_PATH, exist_ok=True)

FEEDBACK_CSV_PATH = os.path.join(DATA_PATH, 'feedback_data.csv')
TRAINING_CSV_PATH = os.path.join(DATA_PATH, 'raw', 'Liver Patient Dataset (LPD)_train.csv')

# Local training data path (from container)
LOCAL_TRAINING_DATA = '/app/src/../data/raw/Liver Patient Dataset (LPD)_train.csv'
LOCAL_MODEL_PATH = '/app/src/../models/logistic_model.pkl'

def initialize_data():
    """Initialize persistent volumes with training data and model if they don't exist"""
    
    # Copy training data to persistent volume if it doesn't exist
    if not os.path.exists(TRAINING_CSV_PATH) and os.path.exists(LOCAL_TRAINING_DATA):
        try:
            shutil.copy2(LOCAL_TRAINING_DATA, TRAINING_CSV_PATH)
            print(f"Copied training data to persistent volume: {TRAINING_CSV_PATH}")
        except Exception as e:
            print(f"Failed to copy training data: {e}")
    
    # Copy initial model to shared volume if it doesn't exist
    shared_model_file = os.path.join(SHARED_MODEL_PATH, 'logistic_model.pkl')
    if not os.path.exists(shared_model_file) and os.path.exists(LOCAL_MODEL_PATH):
        try:
            shutil.copy2(LOCAL_MODEL_PATH, shared_model_file)
            print(f"Copied initial model to shared volume: {shared_model_file}")
        except Exception as e:
            print(f"Failed to copy initial model: {e}")

# Initialize data on startup
initialize_data()

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "is_retraining": is_retraining})

@app.route('/add_feedback_data', methods=['POST'])
def add_feedback_data():
    global is_retraining
    
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['Age of the patient', 'Gender of the patient', 'Total Bilirubin', 
                          'Direct Bilirubin', 'Result']
        
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Store feedback data
        store_feedback_data(data)
        
        # Trigger retraining in background if not already running
        if not is_retraining:
            threading.Thread(target=retrain_model_background, daemon=True).start()
            return jsonify({"success": True, "message": "Feedback data added, retraining initiated"})
        else:
            return jsonify({"success": True, "message": "Feedback data added, retraining already in progress"})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def store_feedback_data(data):
    """Store feedback data to CSV file"""
    # Prepare CSV row
    csv_row = {
        'Age of the patient': data['Age of the patient'],
        'Gender of the patient': data['Gender of the patient'],
        'Total Bilirubin': data['Total Bilirubin'],
        'Direct Bilirubin': data['Direct Bilirubin'],
        '\u00a0Alkphos Alkaline Phosphotase': data['\u00a0Alkphos Alkaline Phosphotase'],
        '\u00a0Sgpt Alamine Aminotransferase': data['\u00a0Sgpt Alamine Aminotransferase'],
        'Sgot Aspartate Aminotransferase': data['Sgot Aspartate Aminotransferase'],
        'Total Protiens': data['Total Protiens'],
        '\u00a0ALB Albumin': data['\u00a0ALB Albumin'],
        'A/G Ratio Albumin and Globulin Ratio': data['A/G Ratio Albumin and Globulin Ratio'],
        'Result': data['Result'],
        'feedback_timestamp': data.get('timestamp', datetime.now().isoformat())
    }
    
    # Check if feedback CSV exists, create with headers if not
    file_exists = os.path.exists(FEEDBACK_CSV_PATH)
    
    with open(FEEDBACK_CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        fieldnames = list(csv_row.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(csv_row)

def retrain_model_background():
    """Background task to retrain the model"""
    global is_retraining
    
    with retraining_lock:
        if is_retraining:
            return
        is_retraining = True
    
    try:
        print(f"[{datetime.now()}] Starting model retraining...")
        
        # Load original training data
        if not os.path.exists(TRAINING_CSV_PATH):
            print(f"Original training data not found at {TRAINING_CSV_PATH}")
            return
        
        df_original = pd.read_csv(TRAINING_CSV_PATH, encoding='latin1')
        print(f"Loaded {len(df_original)} original training samples")
        
        # Load feedback data if it exists
        feedback_data = []
        if os.path.exists(FEEDBACK_CSV_PATH):
            df_feedback = pd.read_csv(FEEDBACK_CSV_PATH, encoding='utf-8')
            # Remove timestamp column for training
            if 'feedback_timestamp' in df_feedback.columns:
                df_feedback = df_feedback.drop('feedback_timestamp', axis=1)
            feedback_data = df_feedback.to_dict('records')
            print(f"Loaded {len(feedback_data)} feedback samples")
        
        # Combine original and feedback data
        combined_data = []
        
        # Add original data
        for _, row in df_original.iterrows():
            combined_data.append(row.to_dict())
        
        # Add feedback data
        combined_data.extend(feedback_data)
        
        # Create combined DataFrame
        df_combined = pd.DataFrame(combined_data)
        print(f"Total combined samples: {len(df_combined)}")
        
        # Train the model with combined data
        model_dict = train_model(df_combined)
        
        # Save the new model
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_model_path = os.path.join(MODEL_PATH, f"logistic_model_{timestamp}.pkl")
        
        with open(new_model_path, 'wb') as f:
            pickle.dump(model_dict, f)
        
        # Copy to shared location for backend to use
        shared_model_path = os.path.join(SHARED_MODEL_PATH, "logistic_model.pkl")
        shutil.copy2(new_model_path, shared_model_path)
        
        print(f"[{datetime.now()}] Model retraining completed. New model saved to {shared_model_path}")
        
    except Exception as e:
        print(f"Error during retraining: {str(e)}")
    finally:
        is_retraining = False

def train_model(df):
    """Train the logistic regression model using the same process as original training"""
    
    # Data preprocessing (same as original)
    df = df.dropna()
    df['Result'] = df['Result'].map({1: 1, 2: 0, 0: 0})  # Handle both original and feedback formats
    df['Gender of the patient'] = df['Gender of the patient'].map({'Male': 0, 'Female': 1})
    
    numerical_features = ['Age of the patient', 'Total Bilirubin', 'Direct Bilirubin', 
                         '\u00a0Alkphos Alkaline Phosphotase',
                         '\u00a0Sgpt Alamine Aminotransferase', 'Sgot Aspartate Aminotransferase', 
                         'Total Protiens', '\u00a0ALB Albumin', 'A/G Ratio Albumin and Globulin Ratio',
                         'Gender of the patient']
    
    X = df[numerical_features]
    y = df['Result']
    
    # Outlier handling
    for column in X.columns:
        X[column] = impute_outliers_with_median(X[column].tolist())
    
    # Z-score scaling
    train_mean = X.mean()
    train_std = X.std()
    X_scaled = (X - train_mean) / train_std
    
    # PCA
    data_array = X_scaled.to_numpy()
    cov_matrix = np.cov(data_array, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
    
    sorted_indices = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[sorted_indices]
    eigenvectors = eigenvectors[:, sorted_indices]
    
    explained_variance_ratio = eigenvalues / np.sum(eigenvalues)
    cumulative_variance = np.cumsum(explained_variance_ratio)
    n_components = np.argmax(cumulative_variance >= 0.95) + 1
    
    principal_components = np.dot(data_array, eigenvectors[:, :n_components])
    
    # Logistic regression training
    X_train = principal_components
    y_train = y.values
    
    weights, _ = logistic_regression_l1(X_train, y_train, learning_rate=0.01, iterations=1000, lambda_=0.009)
    
    # Return model dictionary (same format as original)
    numerical_features_api = [
        'age', 'gender', 'total_bilirubin', 'direct_bilirubin',
        'alkaline_phosphotase', 'alanine_aminotransferase', 'aspartate_aminotransferase',
        'total_proteins', 'albumin', 'albumin_globulin_ratio'
    ]
    
    return {
        'weights': weights,
        'mean': train_mean.values,
        'std': train_std.values,
        'eigenvectors': eigenvectors[:len(numerical_features), :n_components],
        'n_components': n_components,
        'feature_names': numerical_features_api,
        'original_feature_names': numerical_features
    }

def impute_outliers_with_median(data):
    """Impute outliers with median (same as original implementation)"""
    data_sorted = sorted(data)
    n = len(data)
    
    if n % 2 == 0:
        median = (data_sorted[n // 2 - 1] + data_sorted[n // 2]) / 2
    else:
        median = data_sorted[n // 2]
    
    q1_index = (n + 1) // 4
    q3_index = 3 * (n + 1) // 4
    
    if q1_index % 1 != 0:
        q1 = (data_sorted[int(q1_index) - 1] + data_sorted[int(q1_index)]) / 2
    else:
        q1 = data_sorted[int(q1_index) - 1]
    
    if q3_index % 1 != 0:
        q3 = (data_sorted[int(q3_index) - 1] + data_sorted[int(q3_index)]) / 2
    else:
        q3 = data_sorted[int(q3_index) - 1]
    
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    return [x if lower_bound <= x <= upper_bound else median for x in data]

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def compute_cost_l1(X, y, weights, lambda_):
    m = len(y)
    h = sigmoid(X @ weights)
    epsilon = 1e-5
    cost = -(1 / m) * (y.T @ np.log(h + epsilon) + (1 - y).T @ np.log(1 - h + epsilon))
    l1_penalty = lambda_ * np.sum(np.abs(weights[1:]))
    return cost + l1_penalty

def gradient_descent_l1(X, y, weights, learning_rate, iterations, lambda_):
    m = len(y)
    cost_history = []
    
    for _ in range(iterations):
        predictions = sigmoid(X @ weights)
        gradient = (1 / m) * X.T @ (predictions - y)
        l1_gradient = lambda_ * np.sign(weights)
        l1_gradient[0] = 0
        weights -= learning_rate * (gradient + l1_gradient)
        cost = compute_cost_l1(X, y, weights, lambda_)
        cost_history.append(cost)
    
    return weights, cost_history

def logistic_regression_l1(X, y, learning_rate=0.01, iterations=1000, lambda_=0.01):
    X = np.c_[np.ones((X.shape[0], 1)), X]
    weights = np.zeros((X.shape[1], 1))
    y = y.reshape(-1, 1)
    weights, cost_history = gradient_descent_l1(X, y, weights, learning_rate, iterations, lambda_)
    return weights, cost_history

@app.route('/retrain_status')
def retrain_status():
    return jsonify({
        "is_retraining": is_retraining,
        "feedback_data_exists": os.path.exists(FEEDBACK_CSV_PATH),
        "training_data_exists": os.path.exists(TRAINING_CSV_PATH)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)