# Quick Start Guide

Get your Company Chatbot API up and running in 5 minutes!

## Prerequisites

- ✅ Virtual environment created and activated
- ✅ Data indexed in Pinecone (run `index_company_data.py` if not done)

## Step 1: Start the API

```bash
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python chatbot_api.py
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 2: Test the API

Open a new terminal and run:

```bash
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python test_api.py
```

Choose option **2** to test the exact API format.

## Step 3: Use the API

### Using cURL

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "2ed5f805a1ea49009465c329a0910d09",
    "action": "sendMessage",
    "chatInput": "Which companies provide engineering services"
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/chat",
    json={
        "sessionId": "user-123",
        "action": "sendMessage",
        "chatInput": "Which companies provide engineering services"
    }
)

print(response.json()["output"])
```

### Using JavaScript/Node.js

```javascript
fetch('http://localhost:8000/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        sessionId: 'user-123',
        action: 'sendMessage',
        chatInput: 'Which companies provide engineering services'
    })
})
.then(res => res.json())
.then(data => console.log(data.output));
```

## API Request Format

**Request:**
```json
{
    "sessionId": "unique-session-id",
    "action": "sendMessage",
    "chatInput": "your question here"
}
```

**Response:**
```json
{
    "output": "AI-generated answer based on company data"
}
```

## Quick Commands

```bash
# Start API
python chatbot_api.py

# Test API (in another terminal)
python test_api.py

# Check health
curl http://localhost:8000/health

# View API docs (open in browser)
http://localhost:8000/docs
```

## Common Issues

### Issue: "Connection refused"
**Solution:** Make sure the API is running (`python chatbot_api.py`)

### Issue: "Index does not exist"
**Solution:** Run `python index_company_data.py` first to index your data

### Issue: "Port 8000 already in use"
**Solution:** 
```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>
```

## Interactive API Docs

Once the API is running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

These provide interactive testing and complete API documentation.

## Example Questions

Try these questions:
- "Which companies provide engineering services"
- "List all producing Mines"
- "List all mining equipment suppliers"
- "List all Government & NGO"
- "Which companies has safety equipment?"
- "Which companies have job openings?"
- "Tell me about [Company Name]"

## What's Next?

- **Production Deployment:** See `API_GUIDE.md`
- **N8N Integration:** See `N8N_INTEGRATION_GUIDE.md`
- **Testing:** See `TESTING_GUIDE.md`
- **Complete API Docs:** See `API_GUIDE.md`

## File Structure

```
chatbot_api.py          # Main API server
test_api.py             # API test script
API_GUIDE.md            # Complete API documentation
index_company_data.py   # Data indexing script
```

## Support

Need help? Check these files:
- `API_GUIDE.md` - Complete API documentation
- `README.md` - Project overview
- `N8N_INTEGRATION_GUIDE.md` - N8N setup

---

Your API is now ready to serve intelligent responses about company data! 🚀

**API Endpoint:** `POST http://localhost:8000/chat`

**Request Format:**
```json
{
  "sessionId": "unique-id",
  "action": "sendMessage", 
  "chatInput": "your question"
}
```

**Response Format:**
```json
{
  "output": "answer"
}
```

