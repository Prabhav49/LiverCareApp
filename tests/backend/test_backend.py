import pytest
from fastapi.testclient import TestClient
from backend.src.main import app  # Make sure this path aligns with your project structure

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}  # Adjust based on your endpoint
