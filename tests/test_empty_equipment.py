from fastapi.testclient import TestClient
from app.main import app
from app.models.config_model import GlobalConfig


def test_empty_equipment_defaults_and_validation():
    config = GlobalConfig()
    assert config.critical_equipment == {}
    assert config.validate_config()[0]
    client = TestClient(app)
    assert client.get('/api/config/default').json()['data']['critical_equipment'] == {}
    assert client.post('/api/config/validate', json={'critical_equipment': {}}).json()['success']
    assert not client.post('/api/config/validate', json={'critical_equipment': {'test': 0}}).json()['success']


def test_equipment_defaults_are_independent():
    first, second = GlobalConfig(), GlobalConfig()
    first.critical_equipment['test'] = 1
    assert second.critical_equipment == {}
