from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="FastAPI WebSocket Example")
active_connections: set[WebSocket] = set()


def log_active_connections() -> None:
    print(f"Open WebSocket connections: {len(active_connections)}")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    await websocket.accept()
    active_connections.add(websocket)
    log_active_connections()
    await websocket.send_text(f"connected:{client_id}")

    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"echo:{client_id}:{message}")
    except WebSocketDisconnect:
        return
    finally:
        active_connections.discard(websocket)
        log_active_connections()
