# SmartICE Backend - API Reference

## Base URL
```
http://localhost:8001
```

## Endpoints

### 1. Root Endpoint
**GET /**

Simple hello message to verify server is running.

**Request:**
```bash
curl http://localhost:8001/
```

**Response:**
```
HTTP/1.1 200 OK
Content-Type: text/plain

Hello from C++ Backend
```

---

### 2. Health Check
**GET /api/health**

Returns server health status and metadata in JSON format.

**Request:**
```bash
curl http://localhost:8001/api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-27 20:00:00",
  "service": "SmartICE Backend",
  "version": "1.0.0"
}
```

**Response Fields:**
- `status` (string): Health status ("ok" if running)
- `timestamp` (string): Current server time
- `service` (string): Service name
- `version` (string): Server version

---

### 3. Server Statistics
**GET /api/stats**

Returns server runtime statistics including thread pool status.

**Request:**
```bash
curl http://localhost:8001/api/stats
```

**Response:**
```json
{
  "thread_pool": {
    "num_threads": 8,
    "pending_tasks": 0
  },
  "timestamp": "2025-12-27 20:00:00"
}
```

**Response Fields:**
- `thread_pool.num_threads` (number): Number of worker threads
- `thread_pool.pending_tasks` (number): Number of queued tasks
- `timestamp` (string): Current server time

---

## Testing with curl

### Basic Test
```bash
curl http://localhost:8001/
```

### JSON Pretty Print
```bash
curl -s http://localhost:8001/api/health | python3 -m json.tool
```

### Test All Endpoints
```bash
echo "Testing root endpoint..."
curl http://localhost:8001/
echo ""

echo "Testing health endpoint..."
curl http://localhost:8001/api/health
echo ""

echo "Testing stats endpoint..."
curl http://localhost:8001/api/stats
echo ""
```

### Test with Headers
```bash
curl -v http://localhost:8001/api/health
```

---

## Adding New Routes

To add a new route, edit `src/main.cpp`:

```cpp
server.add_route("GET", "/api/myroute", [](const smartice::HttpRequest& req) {
    json response_data = {
        {"message", "Hello from new route"},
        {"path", req.path}
    };

    smartice::HttpResponse response;
    response.status_code = 200;
    response.body = response_data.dump(2);
    response.content_type = "application/json";
    return response;
});
```

Then rebuild:
```bash
cd build
make
./smartice_server
```

Test new route:
```bash
curl http://localhost:8001/api/myroute
```

---

## Future Endpoints (Planned)

### Video Stream Management
```
POST /api/streams/start
POST /api/streams/stop
GET  /api/streams/status
```

### Inference
```
POST /api/inference/detect
GET  /api/inference/stats
```

### Configuration
```
GET  /api/config
POST /api/config
```

---

## Error Handling

### 404 Not Found

**Request:**
```bash
curl http://localhost:8001/nonexistent
```

**Response:**
```
HTTP/1.1 404 OK
Content-Type: text/plain

404 Not Found
```

---

## Server Configuration

### Change Port

Run server on different port:
```bash
./smartice_server 9000
```

Then test:
```bash
curl http://localhost:9000/
```

### Stop Server

Press `Ctrl+C` in terminal running the server. The server will shut down gracefully.

---

## Notes

- All JSON responses are formatted with 2-space indentation
- Server handles one request at a time (blocking I/O)
- Connection is closed after each request
- No authentication required (internal service)
- CORS not configured (same-origin only)
