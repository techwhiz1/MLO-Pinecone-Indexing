# Chatbot API Guide

Complete guide for using the Company Chatbot REST API.

## Overview

The API provides a REST endpoint for querying company data using RAG (Retrieval-Augmented Generation). It searches Pinecone for relevant company information and uses OpenAI to generate intelligent responses.

## Quick Start

### 1. Start the API Server

```bash
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python chatbot_api.py
```

The API will start on `http://0.0.0.0:8000`

### 2. Test the API

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Send a Message:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "2ed5f805a1ea49009465c329a0910d09",
    "action": "sendMessage",
    "chatInput": "Which companies provide engineering services"
  }'
```

## API Endpoints

### 1. POST `/chat`

Main endpoint for chatbot interactions.

**Request:**
```json
{
    "sessionId": "2ed5f805a1ea49009465c329a0910d09",
    "action": "sendMessage",
    "chatInput": "Which companies provide engineering services"
}
```

**Response:**
```json
{
    "output": "Based on the company data, here are the companies that provide engineering services: [answer from AI]"
}
```

**Parameters:**
- `sessionId` (string, required): Unique identifier for the conversation session
- `action` (string, required): Must be "sendMessage"
- `chatInput` (string, required): User's question

**Status Codes:**
- `200`: Success
- `400`: Bad request (invalid action)
- `500`: Server error

---

### 2. GET `/`

Root endpoint for basic status check.

**Response:**
```json
{
    "status": "online",
    "service": "Company Chatbot API",
    "version": "1.0.0"
}
```

---

### 3. GET `/health`

Detailed health check including Pinecone connection status.

**Response:**
```json
{
    "status": "healthy",
    "pinecone": {
        "connected": true,
        "index_name": "company-chatbot",
        "vector_count": 150
    },
    "openai": {
        "connected": true
    }
}
```

---

### 4. POST `/chat/clear-session?session_id={sessionId}`

Clear conversation history for a specific session.

**Request:**
```bash
curl -X POST "http://localhost:8000/chat/clear-session?session_id=abc123"
```

**Response:**
```json
{
    "status": "success",
    "message": "Session abc123 cleared"
}
```

---

### 5. GET `/sessions`

List all active sessions (for debugging).

**Response:**
```json
{
    "active_sessions": ["session1", "session2"],
    "total": 2
}
```

---

### 6. POST `/test?query={your question}`

Simple test endpoint without session management.

**Request:**
```bash
curl -X POST "http://localhost:8000/test?query=What companies are available?"
```

**Response:**
```json
{
    "query": "What companies are available?",
    "answer": "Based on the data..."
}
```

## Usage Examples

### Python Example

```python
import requests

url = "http://localhost:8000/chat"

payload = {
    "sessionId": "user-123",
    "action": "sendMessage",
    "chatInput": "Which companies provide engineering services"
}

response = requests.post(url, json=payload)
result = response.json()

print(result["output"])
```

### JavaScript Example

```javascript
const url = 'http://localhost:8000/chat';

const payload = {
    sessionId: 'user-123',
    action: 'sendMessage',
    chatInput: 'Which companies provide engineering services'
};

fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => {
    console.log(data.output);
});
```

### cURL Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-1",
    "action": "sendMessage",
    "chatInput": "List all producing Mines"
  }'
```

## Session Management

The API maintains conversation history per session:

- Each `sessionId` has its own conversation history
- History is stored in memory (last 10 exchanges per session)
- History helps provide context-aware responses
- Sessions persist until server restart or manually cleared

**Example Multi-Turn Conversation:**

```bash
# First message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "conversation-1",
    "action": "sendMessage",
    "chatInput": "What companies are available?"
  }'

# Follow-up message (same session)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "conversation-1",
    "action": "sendMessage",
    "chatInput": "Tell me more about the first one"
  }'
```

The second message has context from the first!

## Configuration

### Environment Variables

Create a `.env` file:

```bash
PINECONE_API_KEY=your_pinecone_key
OPENAI_API_KEY=your_openai_key
INDEX_NAME=company-chatbot
```

### API Settings

In `chatbot_api.py`:

```python
# Number of documents to retrieve
top_k = 5  # Adjust for more/less context

# OpenAI model
model = "gpt-3.5-turbo"  # or "gpt-4"

# Token limit
max_tokens = 500  # Adjust for longer/shorter responses

# Temperature
temperature = 0.7  # Lower = more focused, Higher = more creative
```

## Running in Production

### Using Uvicorn Directly

```bash
uvicorn chatbot_api:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Gunicorn with Uvicorn Workers

```bash
gunicorn chatbot_api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Using systemd Service

Create `/etc/systemd/system/chatbot-api.service`:

```ini
[Unit]
Description=Company Chatbot API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pinecone_indexing
Environment="PATH=/home/ubuntu/pinecone_indexing/venv/bin"
ExecStart=/home/ubuntu/pinecone_indexing/venv/bin/uvicorn chatbot_api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable chatbot-api
sudo systemctl start chatbot-api
sudo systemctl status chatbot-api
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chatbot_api.py .

EXPOSE 8000

CMD ["uvicorn", "chatbot_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t chatbot-api .
docker run -p 8000:8000 chatbot-api
```

## API Documentation

The API includes auto-generated documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide interactive API testing and full documentation.

## Performance Optimization

### 1. Adjust Top K

```python
# In chatbot_api.py, line ~95
documents = self.search_knowledge_base(question, top_k=3)  # Reduce for speed
```

- `top_k=3`: Fast, less context
- `top_k=5`: Balanced (default)
- `top_k=10`: Comprehensive, slower

### 2. Caching

Add Redis for caching frequent queries:

```python
import redis
r = redis.Redis()

# Check cache before searching
cached = r.get(f"query:{query_hash}")
if cached:
    return cached
```

### 3. Connection Pooling

Clients are initialized once at startup for efficiency.

### 4. Rate Limiting

Add rate limiting for production:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    # ...
```

## Error Handling

The API returns appropriate error messages:

**Invalid Action:**
```json
{
    "detail": "Invalid action: invalidAction. Only 'sendMessage' is supported."
}
```

**No Results Found:**
```json
{
    "output": "I couldn't find any relevant information in the database to answer your question. Please try rephrasing or ask about companies, jobs, products, or services."
}
```

**Server Error:**
```json
{
    "detail": "Error message here"
}
```

## Monitoring

### Logging

Logs are written to stdout. View with:

```bash
# If running directly
python chatbot_api.py

# If using systemd
sudo journalctl -u chatbot-api -f
```

### Health Monitoring

Check health endpoint regularly:

```bash
curl http://localhost:8000/health
```

### Metrics (Optional)

Add Prometheus metrics:

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

## Security Best Practices

1. **Use Environment Variables**: Don't hardcode API keys
2. **Enable CORS Properly**: Specify allowed origins in production
3. **Add Authentication**: Use API keys or OAuth
4. **Rate Limiting**: Prevent abuse
5. **HTTPS**: Use reverse proxy (nginx) with SSL
6. **Input Validation**: Already included via Pydantic

## Testing the API

### Unit Tests

Create `test_api.py`:

```python
from fastapi.testclient import TestClient
from chatbot_api import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_chat():
    response = client.post("/chat", json={
        "sessionId": "test",
        "action": "sendMessage",
        "chatInput": "test question"
    })
    assert response.status_code == 200
    assert "output" in response.json()
```

Run tests:
```bash
pytest test_api.py
```

### Load Testing

Using Apache Bench:
```bash
ab -n 100 -c 10 -p payload.json -T application/json http://localhost:8000/chat
```

Using wrk:
```bash
wrk -t4 -c100 -d30s -s post.lua http://localhost:8000/chat
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Connection Refused

- Check if server is running: `curl http://localhost:8000`
- Check firewall settings
- Verify host and port configuration

### Slow Responses

- Reduce `top_k` value
- Use GPT-3.5-turbo instead of GPT-4
- Enable caching
- Check Pinecone index performance

### Memory Issues

- Clear old sessions regularly
- Reduce session history length
- Use Redis for session storage instead of in-memory

## Next Steps

1. ✅ Start the API: `python chatbot_api.py`
2. ✅ Test with curl or Postman
3. ✅ Integrate with your frontend
4. ✅ Configure for production
5. ✅ Add monitoring and logging

## Support

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Test Endpoint: http://localhost:8000/test

Your chatbot API is ready to serve intelligent responses! 🚀

