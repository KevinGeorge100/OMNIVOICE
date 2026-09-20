from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from omnivoice.media_gateway import app


def test_public_ingress_hides_management_and_docs():
    with TestClient(app) as client:
        for path in ("/", "/api/status", "/api/tenants", "/docs", "/openapi.json"):
            assert client.get(path).status_code == 404


def test_public_ingress_rejects_invalid_line_before_connecting():
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/exotel/invalid/invalid"):
                raise AssertionError("Invalid line accepted")
        except WebSocketDisconnect as error:
            assert error.code == 1008
