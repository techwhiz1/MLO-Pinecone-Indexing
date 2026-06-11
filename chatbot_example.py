"""
Chatbot Example - Demonstrates how to use the indexed data in a real chatbot
This is a simple example showing the query pattern for chatbot integration
"""
import os
from pinecone import Pinecone
from openai import OpenAI
from typing import List, Dict, Any
from dotenv import load_dotenv
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


class CompanyChatbot:
    """Simple chatbot that uses Pinecone indexed company data"""
    
    def __init__(self):
        self.index = pc.Index(INDEX_NAME)
        print("✅ Chatbot initialized and connected to Pinecone")
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a user query"""
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[query]
        )
        return response.data[0].embedding[:EMBEDDING_DIM]
    
    def search_knowledge_base(
        self, 
        query: str, 
        top_k: int = 10,
        chunk_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search the indexed company data
        
        Args:
            query: User's question
            top_k: Number of results to retrieve
            chunk_type: Optional filter (overview/jobs/products/news/services)
        
        Returns:
            List of relevant documents with metadata
        """
        # Generate embedding
        query_embedding = self.generate_query_embedding(query)
        
        # Build search parameters
        search_params = {
            "vector": query_embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        
        # Add filter if specified
        if chunk_type:
            search_params["filter"] = {"chunk_type": chunk_type}
        
        # Search
        results = self.index.query(**search_params)
        
        # Format results
        documents = []
        for match in results.matches:
            documents.append({
                "score": match.score,
                "text": match.metadata.get("text", ""),
                "company_name": match.metadata.get("company_name", "Unknown"),
                "chunk_type": match.metadata.get("chunk_type", "unknown"),
                "company_id": match.metadata.get("company_id", "")
            })
        
        return documents
    
    def answer_question(self, question: str, verbose: bool = False) -> str:
        """
        Answer a user question using the indexed data
        
        Args:
            question: User's question
            verbose: If True, print debug information
        
        Returns:
            AI-generated answer based on the indexed data
        """
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Question: {question}")
            print(f"{'=' * 60}")
        
        # Step 1: Search for relevant information
        if verbose:
            print("\n[1] Searching knowledge base...")
        
        documents = self.search_knowledge_base(question, top_k=10)
        
        if not documents:
            return "I couldn't find any relevant information in the database to answer your question."
        
        if verbose:
            print(f"[2] Found {len(documents)} relevant documents:")
            for i, doc in enumerate(documents, 1):
                print(f"    {i}. {doc['company_name']} ({doc['chunk_type']}) - Score: {doc['score']:.3f}")
        
        # Step 2: Build context from retrieved documents
        context_parts = []
        for doc in documents:
            context_parts.append(
                f"Company: {doc['company_name']}\n"
                f"Type: {doc['chunk_type']}\n"
                f"Information:\n{doc['text']}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        if verbose:
            print(f"[3] Built context ({len(context)} characters)")
        
        # Step 3: Generate answer using GPT
        if verbose:
            print("[4] Generating answer...")
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that answers questions about companies. "
                    "Use the provided context to answer the user's question. "
                    "If the context doesn't contain enough information, say so. "
                    "Be concise and informative."
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}"
            }
        ]
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        
        if verbose:
            print(f"[5] Answer generated")
            print(f"{'=' * 60}\n")
        
        return answer
    
    def chat_loop(self):
        """Interactive chat loop"""
        print("\n" + "=" * 60)
        print("COMPANY CHATBOT")
        print("=" * 60)
        print("Ask questions about companies, jobs, products, news, or services.")
        print("Type 'quit' or 'exit' to end the conversation.")
        print("Type 'verbose' to toggle detailed output.")
        print("=" * 60 + "\n")
        
        verbose = False
        
        while True:
            try:
                question = input("You: ").strip()
                
                if not question:
                    continue
                
                if question.lower() in ['quit', 'exit', 'bye']:
                    print("\nChatbot: Goodbye! Have a great day!")
                    break
                
                if question.lower() == 'verbose':
                    verbose = not verbose
                    print(f"\nVerbose mode: {'ON' if verbose else 'OFF'}\n")
                    continue
                
                # Get answer
                answer = self.answer_question(question, verbose=verbose)
                
                print(f"\nChatbot: {answer}\n")
                print("-" * 60 + "\n")
                
            except KeyboardInterrupt:
                print("\n\nChatbot: Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


def demo_queries():
    """Run demo queries to show chatbot capabilities"""
    print("\n" + "=" * 60)
    print("CHATBOT DEMO - Sample Questions")
    print("=" * 60)
    
    chatbot = CompanyChatbot()
    
    demo_questions = [
        "Which companies provide engineering services",
        "List all producing Mines",
        "List all mining equipment suppliers",
        "List all Government & NGO",
        "Which companies has safety equipment?",
        "Which companies have job openings?",
    ]
    
    for i, question in enumerate(demo_questions, 1):
        print(f"\n{'*' * 60}")
        print(f"Demo Question {i}: {question}")
        print(f"{'*' * 60}")
        
        answer = chatbot.answer_question(question, verbose=True)
        print(f"\nAnswer:\n{answer}")
        
        if i < len(demo_questions):
            input("\nPress Enter for next demo question...")
    
    print(f"\n{'=' * 60}")
    print("Demo completed!")
    print(f"{'=' * 60}\n")


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("COMPANY CHATBOT EXAMPLE")
    print("=" * 60)
    print("\nThis example demonstrates how to use the indexed data")
    print("in a chatbot application.")
    print("\nOptions:")
    print("  1. Run demo queries (see examples)")
    print("  2. Interactive chat mode (ask your own questions)")
    print("  0. Exit")
    print("=" * 60)
    
    choice = input("\nEnter your choice (0-2): ").strip()
    
    if choice == "1":
        demo_queries()
    elif choice == "2":
        chatbot = CompanyChatbot()
        chatbot.chat_loop()
    elif choice == "0":
        print("\nGoodbye!")
    else:
        print("\nInvalid choice. Please run again and select 1, 2, or 0.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\nError: {e}")

