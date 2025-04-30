import pytest
from fastapi.testclient import TestClient
from backend.src.main import app  # Ensure this is the correct path to your FastAPI app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}  # Adjust this based on your endpoint
