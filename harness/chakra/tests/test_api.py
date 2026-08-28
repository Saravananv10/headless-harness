import io
import json
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_health():
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.json() == {'status': 'ok'}

def test_analyze_text_endpoint():
    # Use simple txt payload
    resume_text = 'Worked on scaling systems for 3 years.'
    jd_text = 'Looking for senior engineer with scaling experience.'
    files = {
        'file': ('resume.txt', resume_text.encode('utf-8'), 'text/plain'),
        'jd_text': (None, jd_text)
    }
    # FastAPI expects multipart with file field and jd_text as form field
    resp = client.post('/api/analyze', files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert 'analysis_id' in data
    assert 'match_score' in data
