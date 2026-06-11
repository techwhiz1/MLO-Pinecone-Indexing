"""
FastAPI application for Company Chatbot
Provides REST API endpoints for querying company data via N8N RAG-style retrieval
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from pinecone import Pinecone
from openai import OpenAI
from dotenv import load_dotenv
import logging
from env_config import required_env

# Load environment variables
load_dotenv()

# Configuration
PINECONE_API_KEY = required_env("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "company-chatbot")
EMBEDDING_DIM = 1536
OPENAI_API_KEY = required_env("OPENAI_API_KEY")

# Initialize clients
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Company Chatbot API",
    description="API for querying company data using RAG (Retrieval-Augmented Generation)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    sessionId: str = Field(..., description="Unique session identifier for conversation tracking")
    action: str = Field(..., description="Action to perform (e.g., 'sendMessage')")
    chatInput: str = Field(..., description="User's question or message")

class ChatResponse(BaseModel):
    output: str = Field(..., description="Chatbot's response")

# Optional: Session storage (in-memory, can be replaced with Redis/Database)
session_store: Dict[str, list] = {}


class CompanyChatbotService:
    """Service class for handling chatbot operations"""
    
    def __init__(self):
        self.index = pc.Index(INDEX_NAME)
        logger.info("Chatbot service initialized")
    
    def generate_embedding(self, text: str):
        """Generate embedding for text"""
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[text]
        )
        return response.data[0].embedding[:EMBEDDING_DIM]
    
    def search_knowledge_base(self, query: str, top_k: int = 15):
        """Search Pinecone for relevant company data"""
        try:
            # Generate embedding
            query_embedding = self.generate_embedding(query)
            
            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            # Extract relevant documents
            documents = []
            for match in results.matches:
                documents.append({
                    "score": match.score,
                    "text": match.metadata.get("text", ""),
                    "company_name": match.metadata.get("company_name", "Unknown"),
                    "company_id": match.metadata.get("company_id", "")
                })
            
            return documents
        
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    def generate_answer(self, question: str, conversation_history: list = None) -> str:
        """Generate answer using RAG pattern"""
        try:
            # Step 1: Retrieve relevant documents
            documents = self.search_knowledge_base(question, top_k=15)
            
            if not documents:
                return "I couldn't find any relevant information in the database to answer your question. Please try rephrasing or ask about companies, jobs, products, or services."
            
            # Step 2: Build context from retrieved documents
            context_parts = []
            for doc in documents:
                if doc['text']:  # Only include if text exists
                    context_parts.append(
                        f"Company: {doc['company_name']}\n"
                        f"Information:\n{doc['text']}"
                    )
            
            context = "\n\n---\n\n".join(context_parts[:3])  # Limit to top 3 for token efficiency
            
            # Step 3: Build messages with conversation history
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that provides information about companies. "
                        "Use the provided context to answer questions accurately. "
                        "Be concise and informative. "
                        "If the context doesn't contain enough information, say so politely. "
                        "Always mention the company name when providing specific information."
                    )
                }
            ]
            
            # Add conversation history if available
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Last 3 exchanges (6 messages)
            
            # Add current query with context
            messages.append({
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}"
            })
            
            # Step 4: Generate response
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            return answer
        
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"I apologize, but I encountered an error while processing your question. Please try again."


# Initialize chatbot service
chatbot_service = CompanyChatbotService()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Company Chatbot API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test Pinecone connection
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        
        return {
            "status": "healthy",
            "pinecone": {
                "connected": True,
                "index_name": INDEX_NAME,
                "vector_count": stats.total_vector_count
            },
            "openai": {
                "connected": True
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint
    
    Request body:
    {
        "sessionId": "unique-session-id",
        "action": "sendMessage",
        "chatInput": "Your question here"
    }
    
    Response:
    {
        "output": "Answer to your question"
    }
    """
    try:
        logger.info(f"Session {request.sessionId}: {request.action} - {request.chatInput}")
        
        # Validate action
        if request.action != "sendMessage":
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid action: {request.action}. Only 'sendMessage' is supported."
            )
        
        # Get or create session history
        if request.sessionId not in session_store:
            session_store[request.sessionId] = []
        
        conversation_history = session_store[request.sessionId]
        
        # Generate answer
        answer = chatbot_service.generate_answer(
            request.chatInput,
            conversation_history=conversation_history
        )
        
        # Store conversation in session
        session_store[request.sessionId].append({
            "role": "user",
            "content": request.chatInput
        })
        session_store[request.sessionId].append({
            "role": "assistant",
            "content": answer
        })
        
        # Keep only last 10 exchanges (20 messages) to prevent memory issues
        if len(session_store[request.sessionId]) > 20:
            session_store[request.sessionId] = session_store[request.sessionId][-20:]
        
        logger.info(f"Session {request.sessionId}: Response generated successfully")
        
        return ChatResponse(output=answer)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/clear-session")
async def clear_session(session_id: str):
    """Clear conversation history for a specific session"""
    if session_id in session_store:
        del session_store[session_id]
        return {"status": "success", "message": f"Session {session_id} cleared"}
    return {"status": "info", "message": "Session not found"}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging)"""
    return {
        "active_sessions": list(session_store.keys()),
        "total": len(session_store)
    }


@app.post("/test")
async def test_query(query: str):
    """Simple test endpoint without session management"""
    try:
        answer = chatbot_service.generate_answer(query)
        return {"query": query, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
