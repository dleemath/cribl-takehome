import os
import uuid

import pytest
import tempfile
import json
from log_server import app

TEST_LOG_SIZE = 10000
# Temporary log directory and file for testing
@pytest.fixture
def temp_log_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_log_file(temp_log_dir):
    log_file_path = os.path.join(temp_log_dir, "test.log")
    with open(log_file_path, 'w') as f:
        for i in range(1, TEST_LOG_SIZE):  # Write TEST_LOG_SIZE lines
            f.write(f"Log line {i} + {uuid.uuid4()}\n")
    return log_file_path


# Configure the Flask app for testing
@pytest.fixture
def client(temp_log_file):
    app.config['TESTING'] = True
    app.config['LOG_DIR'] = os.path.dirname(temp_log_file)
    with app.test_client() as client:
        yield client


# Test cases
def test_get_log_file_no_filename(client):
    response = client.post('/logs', json={})
    assert response.status_code == 422
    assert b"Field required" in response.data


def test_get_log_file_not_found(client):
    response = client.post('/logs', json={"logpath": "nonexistent.log"})
    assert response.status_code == 404
    assert b"Log file not found." in response.data


def test_get_log_file_success(client):
    payload = {
        "logpath": "test.log",
        "num_lines": 50,
        "offset": 0,
        "page_size": 250,
        "regex": None
    }
    response = client.post('/logs', json=payload)
    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert len(response_data['data']) == 50
    assert f"Log line {TEST_LOG_SIZE-1}" in response_data['data'][0]
    assert response_data['metadata']['lines_retrieved'] == 50
    assert response_data['metadata']['next_request'] is None


def test_get_log_file_with_regex(client):
    payload = {
        "logpath": "test.log",
        "num_lines": 10,
        "offset": 0,
        "page_size": 250,
        "regex": "Log line 9"
    }
    response = client.post('/logs', json=payload)
    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert len(response_data['data']) == 10
    assert all("Log line 9" in line for line in response_data['data'])
    assert response_data['metadata']['lines_retrieved'] == 10
    assert response_data['metadata']['next_request'] is None


def test_get_log_file_with_next_request(client):
    payload = {
        "logpath": "test.log",
        "num_lines": 200,
        "offset": 0,
        "page_size": 50,
        "regex": None
    }
    response = client.post('/logs', json=payload)
    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert len(response_data['data']) == 50
    assert f"Log line {TEST_LOG_SIZE-1}" in response_data['data'][0]
    assert response_data['metadata']['lines_retrieved'] == 50
    assert response_data['metadata']['next_request'] is not None

    response_next = client.post('/logs', json=response_data['metadata']['next_request'])
    assert response_next.status_code == 200
    response_data = json.loads(response_next.data)
    assert f"Log line {TEST_LOG_SIZE - 51}" in response_data['data'][0]
    assert len(response_data['data']) == 50


def test_get_log_file_with_gzip(client):
    payload = {
        "logpath": "test.log",
        "num_lines": 50,
        "offset": 0,
        "page_size": 250,
        "regex": None
    }
    headers = {
        'Accept-Encoding': 'gzip'
    }
    response = client.post('/logs', headers=headers, json=payload)
    assert response.status_code == 200
    assert response.headers['Content-Encoding'] == 'gzip'

    # Decompress the response content
    import gzip
    from io import BytesIO

    compressed_content = response.data
    with gzip.GzipFile(fileobj=BytesIO(compressed_content)) as f:
        decompressed_content = f.read().decode('utf-8')
    response_data = json.loads(decompressed_content)

    assert len(response_data['data']) == 50
    assert f"Log line {TEST_LOG_SIZE-1}" in response_data['data'][0]
    assert response_data['metadata']['lines_retrieved'] == 50
    assert response_data['metadata']['next_request'] is None
