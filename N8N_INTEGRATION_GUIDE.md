# N8N RAG Agent Integration Guide

This guide explains how to integrate your indexed Pinecone data with N8N's RAG Agent.

## Overview

The indexing script (`index_company_data.py`) has been optimized for N8N's RAG Agent workflow:
- ✅ **One document per company** (no chunking)
- ✅ **Comprehensive text** with all information in one place
- ✅ **Metadata optimized** for N8N's Retrieve Documents tool
- ✅ **Text field** contains the full searchable content

## Index Structure

Each company is stored as ONE document with:

```
ID: company_{company_id}
Values: [embedding vector - 1536 dimensions]
Metadata:
  - text: Full company information (this is what N8N retrieves)
  - company_id: Database company ID
  - company_name: Company name
  - job_count: Number of jobs (optional)
  - product_count: Number of products (optional)
  - news_count: Number of news articles (optional)
  - service_count: Number of services (optional)
  - industry: Company industry (optional)
  - location: Company location (optional)
  - website: Company website (optional)
```

## N8N Workflow Configuration

### 1. Pinecone Vector Store Node

**Configuration:**
```
Pinecone API Key: use your PINECONE_API_KEY environment value
Index Name: company-chatbot
Namespace: (leave empty)
```

### 2. OpenAI Embeddings Node

**Configuration:**
```
Model: text-embedding-ada-002
API Key: use your OPENAI_API_KEY environment value
```

### 3. Retrieve Documents Tool

**Configuration:**
```
Name: Retrieve Documents
Description: Retrieves information about companies, jobs, products, services, and news
Vector Store: [Connect to Pinecone Vector Store node]
Top K: 3-5 (adjust based on your needs)
```

**Recommended Description for Agent:**
```
Use this tool to search for information about companies. You can ask about:
- Company overview and details
- Job openings and positions
- Products and services offered
- Company news and updates
- Services provided by companies
```

### 4. RAG AI Agent Node

**Configuration:**
```
Chat Model: [Connect to OpenAI Chat Model]
Memory: [Connect to Postgres Chat Memory]
Tools: [Connect to Retrieve Documents tool]

System Message:
"You are a helpful assistant with access to a database of companies. 
Use the Retrieve Documents tool to search for information when users 
ask about companies, jobs, products, services, or news. Always cite 
the company name when providing information."
```

### 5. OpenAI Chat Model Node

**Configuration:**
```
Model: gpt-3.5-turbo (or gpt-4 for better quality)
Temperature: 0.7
Max Tokens: 500-1000
```

## Workflow Structure

Your workflow should look like this:

```
Webhook (Trigger)
   ↓
RAG AI Agent
   ↓ (uses tools)
   ├── OpenAI Chat Model
   ├── Postgres Chat Memory
   └── Retrieve Documents → Pinecone Vector Store → Embeddings OpenAI
   ↓
Response to Webhook
```

## Testing Your Integration

### Test Queries

Try these queries in your N8N chat interface:

1. **General company search:**
   - "What companies are in the database?"
   - "Tell me about [company name]"

2. **Job queries:**
   - "What job openings are available?"
   - "Are there any software developer positions?"
   - "Show me jobs at [company name]"

3. **Product queries:**
   - "What products does [company name] offer?"
   - "Show me all available products"

4. **News queries:**
   - "What's the latest news about [company name]?"
   - "Show me recent company updates"

5. **Service queries:**
   - "What services are offered?"
   - "Tell me about the services at [company name]"

### Expected Behavior

1. User asks a question
2. RAG Agent determines it needs company information
3. Calls "Retrieve Documents" tool
4. Tool searches Pinecone with embedded query
5. Returns top 3-5 most relevant company documents
6. RAG Agent uses the retrieved text to answer
7. Provides answer citing company names

## Optimization Tips

### 1. Adjust Top K Value

- **Top K = 1-2**: Fast, but might miss relevant info
- **Top K = 3-5**: **Recommended** - Good balance
- **Top K = 6-10**: More context, but slower and more tokens

### 2. Use Metadata Filters

In N8N's Retrieve Documents tool, you can add filters:

**Filter by company (if you know the company name):**
```json
{
  "company_name": "CompanyName"
}
```

**Filter by job count (companies with jobs):**
```json
{
  "job_count": {"$gt": 0}
}
```

**Filter by industry:**
```json
{
  "industry": "Technology"
}
```

### 3. Improve Query Quality

Configure your RAG Agent to reformulate queries:

**System Message Example:**
```
You are a company information assistant. When users ask questions:
1. Use the Retrieve Documents tool to search for relevant information
2. Always provide specific company names in your answers
3. If information is not found, say so clearly
4. Summarize information concisely but completely
```

### 4. Handle No Results

Add logic to handle cases when no relevant documents are found:

```
If the tool returns no results, inform the user that the 
information is not available in the database and suggest 
they rephrase their question or ask about something else.
```

## Common Issues & Solutions

### Issue 1: Tool not being called
**Solution:** Make your tool description more explicit:
```
"Search the company database. Use this tool whenever the user asks 
about companies, jobs, products, services, news, or any business 
information. This is your primary source of data."
```

### Issue 2: Irrelevant results
**Solution:** 
- Reduce Top K to 2-3
- Add metadata filters
- Improve your embeddings by re-indexing with better descriptions

### Issue 3: Response too long
**Solution:**
- Reduce Top K
- Adjust max tokens in Chat Model
- Add instruction to summarize: "Provide concise answers"

### Issue 4: Information outdated
**Solution:**
- Re-run `index_company_data.py` to refresh the index
- Set up automated re-indexing on a schedule

## Monitoring & Maintenance

### Check Index Status

Use `quick_test.py` to verify your index:
```bash
python quick_test.py
```

### Verify Data Quality

Use `test_index.py` to test queries:
```bash
python test_index.py
```

### Re-index Data

When company data changes:
```bash
python index_company_data.py
```

This will:
1. Fetch fresh data from PostgreSQL
2. Clear the old index
3. Create new embeddings
4. Upload to Pinecone

## Advanced Features

### 1. Multi-Query Retrieval

Enable the agent to make multiple searches:
```
System Message: "If the user asks about multiple things, 
use the Retrieve Documents tool multiple times to gather 
all necessary information before answering."
```

### 2. Source Attribution

Have the agent cite sources:
```
System Message: "Always mention which company the information 
comes from. Format: 'According to [Company Name]'s profile...'"
```

### 3. Fallback Responses

Handle uncertainty gracefully:
```
System Message: "If you're not certain about information, 
say so. If the database doesn't contain specific details, 
acknowledge this limitation."
```

## Performance Expectations

With the optimized indexing:

- **Query Response Time:** 2-4 seconds
- **Accuracy:** High (semantic search)
- **Context Quality:** Comprehensive (full company data)
- **Token Usage:** ~1000-2000 tokens per query (with Top K=3)

## Next Steps

1. ✅ Run `python index_company_data.py` to index your data
2. ✅ Configure N8N nodes with the settings above
3. ✅ Test with sample queries
4. ✅ Adjust Top K and system message based on results
5. ✅ Deploy your RAG Agent!

## Need Help?

- Test queries: Use `test_index.py`
- Verify setup: Use `quick_test.py`
- See examples: Use `chatbot_example.py`

Your N8N RAG Agent is now ready to provide intelligent responses about your company data! 🚀

