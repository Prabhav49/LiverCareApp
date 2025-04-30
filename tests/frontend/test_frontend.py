import pytest
from frontend import app  # This should align with your folder structure for Flask app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello, World!" in response.data  # Adjust based on your frontend's response
