import sys
import os
import pytest

# Add the frontend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend')))

from frontend import app  # This should now work

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello, World!" in response.data  # Adjust based on your frontend's response
