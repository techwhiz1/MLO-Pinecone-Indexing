# Testing Guide for Company Data Indexing

This guide explains how to test your indexed data in Pinecone.

## Overview

After running `index_company_data.py`, you should test the indexed data to ensure:
1. Data was properly indexed
2. Embeddings were generated correctly
3. Metadata is structured properly
4. Search/query functionality works
5. The data is ready for chatbot integration

## Test Scripts

### 1. `quick_test.py` - Automated Quick Validation

**Purpose**: Fast automated validation that everything works

**What it tests**:
- ✅ Index exists
- ✅ Contains vectors
- ✅ Search functionality works
- ✅ Metadata structure is correct
- ✅ Text content is present
- ✅ Chunk type filtering works

**How to run**:
```bash
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python quick_test.py
```

**Expected output**: All tests should pass with ✅

---

### 2. `test_index.py` - Interactive Testing Tool

**Purpose**: Comprehensive interactive testing with detailed results

**Features**:
1. **View Index Statistics** - See how many vectors are indexed
2. **Run Sample Test Queries** - Pre-configured test queries
3. **Custom Search Query** - Test your own queries
4. **Test Specific Company** - Deep dive into one company's data
5. **Validate Metadata Structure** - Check data integrity
6. **Chatbot Simulation** - See how a chatbot would use the data
7. **Run All Tests** - Execute everything

**How to run**:
```bash
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python test_index.py
```

Then follow the interactive menu.

## Testing Workflow

### Step 1: Quick Validation
After running `index_company_data.py`, immediately run:
```bash
python quick_test.py
```

If all tests pass ✅, proceed to Step 2.

### Step 2: Interactive Testing
Run the interactive test tool:
```bash
python test_index.py
```

Recommended test sequence:
1. Choose option **1** - View Index Statistics
2. Choose option **5** - Validate Metadata Structure
3. Choose option **2** - Run Sample Test Queries
4. Choose option **6** - Chatbot Simulation (try different questions)

### Step 3: Test Your Use Cases
Use option **3** (Custom Search Query) to test queries relevant to your chatbot:
- "What companies offer software development services?"
- "Are there any job openings for Python developers?"
- "Tell me about [company name]"
- "What products does [company name] offer?"

## Understanding Test Results

### Search Results Format

Each result includes:
- **Score** (0.0 - 1.0): How relevant the result is (higher = more relevant)
- **Company Name**: Which company the data is about
- **Chunk Type**: Type of information (overview, jobs, products, news, services)
- **Text Content**: The actual searchable text (this is what your chatbot will use)

### Good Score Ranges
- **0.8 - 1.0**: Highly relevant (excellent match)
- **0.6 - 0.8**: Relevant (good match)
- **0.4 - 0.6**: Somewhat relevant (may be useful)
- **< 0.4**: Low relevance (might not be useful)

### Chunk Types
Your data is organized into 5 types:

1. **overview** - Company basic information, location, contact details
2. **jobs** - Job listings and openings
3. **products** - Products and services offered
4. **news** - Company news and updates
5. **services** - Detailed service information

## Troubleshooting

### Problem: "Index does not exist"
**Solution**: Run `index_company_data.py` first to create and populate the index.

### Problem: "Index is empty (0 vectors)"
**Solution**: The indexing process didn't complete. Check for errors in `index_company_data.py` output.

### Problem: "No results found"
**Possible causes**:
1. Query is too specific - try broader queries
2. Data doesn't contain relevant information
3. Check if you're using the correct filters

### Problem: "Missing required fields"
**Solution**: Re-run `index_company_data.py` - the indexing may have been interrupted.

### Problem: "Embedding Error"
**Possible causes**:
1. OpenAI API key is invalid or expired
2. Rate limit exceeded
3. Network connection issue

**Solution**: Check your OpenAI API key and wait a moment before retrying.

## Chatbot Integration Example

Here's how your chatbot would use the indexed data:

```python
from pinecone import Pinecone
from openai import OpenAI
from env_config import required_env

# Initialize
pc = Pinecone(api_key=required_env("PINECONE_API_KEY"))
client = OpenAI(api_key=required_env("OPENAI_API_KEY"))
index = pc.Index("company-chatbot")

# User asks a question
user_question = "What companies offer software development?"

# 1. Generate embedding for the question
response = client.embeddings.create(
    model="text-embedding-ada-002",
    input=[user_question]
)
query_embedding = response.data[0].embedding

# 2. Search Pinecone
results = index.query(
    vector=query_embedding,
    top_k=3,
    include_metadata=True
)

# 3. Extract context
context_parts = []
for match in results.matches:
    text = match.metadata['text']
    context_parts.append(text)

context = "\n\n".join(context_parts)

# 4. Send to LLM with context
messages = [
    {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer questions."},
    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_question}"}
]

# 5. Get response
answer = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=messages
)

print(answer.choices[0].message.content)
```

## Performance Tips

1. **Use Filters**: When searching for specific types of information, use chunk_type filters:
   ```python
   filter={"chunk_type": "jobs"}  # Only search job listings
   ```

2. **Adjust top_k**: For chatbot use, typically `top_k=3-5` is sufficient
   - Too few: Might miss relevant info
   - Too many: Adds noise and costs more tokens

3. **Filter by Company**: If you know which company, filter by company_id:
   ```python
   filter={"company_id": "123"}
   ```

## Next Steps

After successful testing:
1. ✅ Your data is ready for chatbot use
2. Integrate the query pattern into your chatbot
3. Test with real user questions
4. Monitor response quality and adjust top_k or filters as needed

## Need Help?

Common test scenarios are included in `test_index.py`. Run option **2** (Sample Test Queries) to see examples of different query types and filtering options.

