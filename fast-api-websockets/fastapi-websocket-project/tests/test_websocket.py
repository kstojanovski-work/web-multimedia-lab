from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_connect_and_echo() -> None:
    with client.websocket_connect("/ws/alice") as websocket:
        connected_message = websocket.receive_text()
        assert connected_message == "connected:alice"

        websocket.send_text("hello")
        echoed_message = websocket.receive_text()
        assert echoed_message == "echo:alice:hello"


def test_websocket_multiple_messages() -> None:
    with client.websocket_connect("/ws/bob") as websocket:
        _ = websocket.receive_text()

        websocket.send_text("first")
        assert websocket.receive_text() == "echo:bob:first"

        websocket.send_text("second")
        assert websocket.receive_text() == "echo:bob:second"
