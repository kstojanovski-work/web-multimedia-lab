# JSON Contracts

## Inbound (frontend -> backend)

### `session.start`

```json
{
  "type": "session.start",
  "sessionId": "abc-123",
  "fps": 10,
  "language": "de"
}
```

### `frame.chunk`

```json
{
  "type": "frame.chunk",
  "sessionId": "abc-123",
  "seq": 42,
  "ts": 1730000000.123,
  "encoding": "image/jpeg;base64",
  "payload": "...base64..."
}
```

## Outbound (backend -> frontend)

### `caption.partial` / `caption.final`

```json
{
  "type": "caption.partial",
  "sessionId": "abc-123",
  "text": "Hallo",
  "confidence": 0.77,
  "isFinal": false,
  "ts": 1730000000.456
}
```

### `error`

```json
{
  "type": "error",
  "code": "invalid_payload",
  "message": "Missing field: sessionId",
  "ts": 1730000000.567
}
```
