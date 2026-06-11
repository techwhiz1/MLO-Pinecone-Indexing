import os
from pinecone import Pinecone
from openai import OpenAI
from typing import List, Dict, Any
import json
from dotenv import load_dotenv
import logging
from env_config import required_env

# Load environment variables
load_dotenv()

# Configuration - same as index_company_data.py
PINECONE_API_KEY = required_env("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "company-chatbot")
EMBEDDING_DIM = 1536
OPENAI_API_KEY = required_env("OPENAI_API_KEY")

# Initialize clients
client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


class PineconeIndexTester:
    """Test the Pinecone index to ensure data is properly indexed"""
    
    def __init__(self):
        self.index = None
        self.initialize_index()
    
    def initialize_index(self):
        """Initialize connection to Pinecone index"""
        try:
            if INDEX_NAME not in pc.list_indexes().names():
                logging.error(f"Index '{INDEX_NAME}' does not exist!")
                logging.error("Please run index_company_data.py first to create the index.")
                return False
            
            self.index = pc.Index(INDEX_NAME)
            logging.info(f"✓ Connected to index: {INDEX_NAME}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Pinecone: {e}")
            return False
    
    def get_index_stats(self):
        """Get statistics about the index"""
        try:
            stats = self.index.describe_index_stats()
            print("\n" + "=" * 60)
            print("INDEX STATISTICS")
            print("=" * 60)
            print(f"Index name: {INDEX_NAME}")
            print(f"Total vectors: {stats.total_vector_count}")
            print(f"Dimension: {stats.dimension}")
            
            if hasattr(stats, 'namespaces') and stats.namespaces:
                print(f"Namespaces: {list(stats.namespaces.keys())}")
            
            print("=" * 60)
            return stats
        except Exception as e:
            logging.error(f"Failed to get index stats: {e}")
            return None
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for a query"""
        try:
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=[query]
            )
            return response.data[0].embedding[:EMBEDDING_DIM]
        except Exception as e:
            logging.error(f"Failed to generate query embedding: {e}")
            return None
    
    def search_index(self, query: str, top_k: int = 5, filter_dict: Dict[str, Any] = None):
        """Search the index with a query"""
        try:
            query_embedding = self.generate_query_embedding(query)
            if not query_embedding:
                return None
            
            # Search parameters
            search_params = {
                "vector": query_embedding,
                "top_k": top_k,
                "include_metadata": True
            }
            
            # Add filter if provided
            if filter_dict:
                search_params["filter"] = filter_dict
            
            results = self.index.query(**search_params)
            return results
        except Exception as e:
            logging.error(f"Search failed: {e}")
            return None
    
    def display_results(self, results, query: str):
        """Display search results in a readable format"""
        if not results or not results.matches:
            print(f"\n❌ No results found for query: '{query}'")
            return
        
        print(f"\n{'=' * 60}")
        print(f"SEARCH RESULTS FOR: '{query}'")
        print(f"Found {len(results.matches)} results")
        print(f"{'=' * 60}\n")
        
        for idx, match in enumerate(results.matches, 1):
            print(f"Result #{idx}")
            print(f"Score: {match.score:.4f}")
            print(f"ID: {match.id}")
            
            if match.metadata:
                print(f"Company: {match.metadata.get('company_name', 'N/A')}")
                print(f"Company ID: {match.metadata.get('company_id', 'N/A')}")
                print(f"Chunk Type: {match.metadata.get('chunk_type', 'N/A')}")
                
                # Display counts if available
                if 'job_count' in match.metadata:
                    print(f"Jobs: {match.metadata.get('job_count')}")
                if 'product_count' in match.metadata:
                    print(f"Products: {match.metadata.get('product_count')}")
                if 'news_count' in match.metadata:
                    print(f"News: {match.metadata.get('news_count')}")
                if 'service_count' in match.metadata:
                    print(f"Services: {match.metadata.get('service_count')}")
                
                # Display text content (truncated)
                if 'text' in match.metadata:
                    text = match.metadata['text']
                    max_length = 500
                    if len(text) > max_length:
                        text = text[:max_length] + "..."
                    print(f"\nContent Preview:\n{text}")
            
            print(f"\n{'-' * 60}\n")
    
    def test_query(self, query: str, top_k: int = 3, filter_dict: Dict[str, Any] = None):
        """Test a single query"""
        results = self.search_index(query, top_k=top_k, filter_dict=filter_dict)
        if results:
            self.display_results(results, query)
        return results
    
    def run_sample_tests(self):
        """Run a series of sample test queries"""
        print("\n" + "=" * 60)
        print("RUNNING SAMPLE TEST QUERIES")
        print("=" * 60)
        
        test_queries = [
            {
                "name": "Test 1: General company search",
                "query": "What companies are in the database?",
                "top_k": 3,
                "filter": None
            },
            {
                "name": "Test 2: Job search",
                "query": "What job openings are available?",
                "top_k": 3,
                "filter": {"chunk_type": "jobs"}
            },
            {
                "name": "Test 3: Product search",
                "query": "What products and services are offered?",
                "top_k": 3,
                "filter": {"chunk_type": "products"}
            },
            {
                "name": "Test 4: Company overview",
                "query": "Tell me about the companies",
                "top_k": 3,
                "filter": {"chunk_type": "overview"}
            },
            {
                "name": "Test 5: News search",
                "query": "What are the latest company news?",
                "top_k": 3,
                "filter": {"chunk_type": "news"}
            },
        ]
        
        for test in test_queries:
            print(f"\n{'*' * 60}")
            print(f"{test['name']}")
            print(f"{'*' * 60}")
            self.test_query(test['query'], top_k=test['top_k'], filter_dict=test['filter'])
            input("\nPress Enter to continue to next test...")
    
    def test_specific_company(self, company_name: str):
        """Test queries for a specific company"""
        print(f"\n{'=' * 60}")
        print(f"TESTING QUERIES FOR: {company_name}")
        print(f"{'=' * 60}")
        
        # Search for the company
        results = self.test_query(f"Tell me about {company_name}", top_k=5)
        
        if results and results.matches:
            company_id = results.matches[0].metadata.get('company_id')
            if company_id:
                print(f"\n--- Searching for all chunks of company_id: {company_id} ---")
                
                # Get all chunks for this company
                all_chunks = []
                for chunk_type in ['overview', 'jobs', 'products', 'news', 'services']:
                    filter_dict = {
                        "company_id": company_id,
                        "chunk_type": chunk_type
                    }
                    results = self.search_index(
                        query=f"{company_name}",
                        top_k=10,
                        filter_dict=filter_dict
                    )
                    if results and results.matches:
                        all_chunks.extend(results.matches)
                
                print(f"\nFound {len(all_chunks)} total chunks for this company:")
                for chunk in all_chunks:
                    print(f"  - {chunk.metadata.get('chunk_type', 'unknown')}")
    
    def validate_metadata_structure(self):
        """Validate that all vectors have the required metadata fields"""
        print(f"\n{'=' * 60}")
        print("VALIDATING METADATA STRUCTURE")
        print(f"{'=' * 60}")
        
        # Fetch a few random vectors
        results = self.search_index("test", top_k=10)
        
        if not results or not results.matches:
            print("❌ Could not fetch vectors for validation")
            return False
        
        required_fields = ['text', 'chunk_type', 'company_id', 'company_name']
        all_valid = True
        
        for match in results.matches:
            missing_fields = []
            for field in required_fields:
                if field not in match.metadata:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ Vector {match.id} missing fields: {missing_fields}")
                all_valid = False
            else:
                print(f"✓ Vector {match.id} has all required fields")
        
        if all_valid:
            print("\n✅ All vectors have valid metadata structure!")
        else:
            print("\n❌ Some vectors have incomplete metadata")
        
        return all_valid
    
    def chatbot_simulation(self, user_question: str):
        """Simulate how a chatbot would use this index"""
        print(f"\n{'=' * 60}")
        print("CHATBOT SIMULATION")
        print(f"{'=' * 60}")
        print(f"User Question: {user_question}")
        print(f"{'-' * 60}")
        
        # Step 1: Search the index
        print("\n[Step 1] Searching Pinecone index...")
        results = self.search_index(user_question, top_k=3)
        
        if not results or not results.matches:
            print("No relevant information found in the database.")
            return
        
        # Step 2: Extract context
        print(f"[Step 2] Found {len(results.matches)} relevant chunks")
        context_parts = []
        
        for idx, match in enumerate(results.matches, 1):
            company = match.metadata.get('company_name', 'Unknown')
            chunk_type = match.metadata.get('chunk_type', 'unknown')
            text = match.metadata.get('text', '')
            
            print(f"  - Chunk {idx}: {company} ({chunk_type}), Score: {match.score:.4f}")
            context_parts.append(f"From {company} ({chunk_type}):\n{text}")
        
        # Step 3: Build context for LLM
        context = "\n\n---\n\n".join(context_parts)
        
        print(f"\n[Step 3] Context built ({len(context)} characters)")
        print(f"\n[Step 4] Would send to LLM:")
        print(f"  System: You are a helpful assistant. Use the following context to answer.")
        print(f"  Context: {context[:500]}...")
        print(f"  User: {user_question}")
        
        print(f"\n{'=' * 60}")
        print("This is how your chatbot would retrieve and use the data!")
        print(f"{'=' * 60}")


def main():
    """Main test execution"""
    print("\n" + "=" * 60)
    print("PINECONE INDEX TESTING SCRIPT")
    print("=" * 60)
    
    tester = PineconeIndexTester()
    
    if not tester.index:
        print("\n❌ Failed to connect to index. Exiting.")
        return
    
    # Menu
    while True:
        print("\n" + "=" * 60)
        print("TEST MENU")
        print("=" * 60)
        print("1. View Index Statistics")
        print("2. Run Sample Test Queries")
        print("3. Custom Search Query")
        print("4. Test Specific Company")
        print("5. Validate Metadata Structure")
        print("6. Chatbot Simulation")
        print("7. Run All Tests")
        print("0. Exit")
        print("=" * 60)
        
        choice = input("\nEnter your choice (0-7): ").strip()
        
        if choice == "1":
            tester.get_index_stats()
        
        elif choice == "2":
            tester.run_sample_tests()
        
        elif choice == "3":
            query = input("\nEnter your search query: ").strip()
            if query:
                top_k = input("Number of results (default 5): ").strip()
                top_k = int(top_k) if top_k.isdigit() else 5
                
                use_filter = input("Filter by chunk type? (yes/no): ").strip().lower()
                filter_dict = None
                if use_filter == "yes":
                    chunk_type = input("Chunk type (overview/jobs/products/news/services): ").strip()
                    if chunk_type:
                        filter_dict = {"chunk_type": chunk_type}
                
                tester.test_query(query, top_k=top_k, filter_dict=filter_dict)
        
        elif choice == "4":
            company_name = input("\nEnter company name: ").strip()
            if company_name:
                tester.test_specific_company(company_name)
        
        elif choice == "5":
            tester.validate_metadata_structure()
        
        elif choice == "6":
            question = input("\nEnter a chatbot question: ").strip()
            if question:
                tester.chatbot_simulation(question)
        
        elif choice == "7":
            print("\nRunning all tests...")
            tester.get_index_stats()
            input("\nPress Enter to continue...")
            tester.validate_metadata_structure()
            input("\nPress Enter to continue...")
            tester.run_sample_tests()
        
        elif choice == "0":
            print("\n👋 Exiting test script. Goodbye!")
            break
        
        else:
            print("\n❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    main()

