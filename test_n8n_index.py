"""
Test script for N8N RAG Agent index
Validates that data is properly indexed for N8N's Retrieve Documents tool
"""
import os
from pinecone import Pinecone
from openai import OpenAI
from typing import List
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


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for query"""
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=[text]
    )
    return response.data[0].embedding[:EMBEDDING_DIM]


def test_n8n_index():
    """Test the index as N8N would use it"""
    print("\n" + "=" * 60)
    print("N8N RAG AGENT INDEX TEST")
    print("=" * 60)
    
    # Check index exists
    print("\n[Test 1] Checking index...")
    if INDEX_NAME not in pc.list_indexes().names():
        print(f"❌ FAIL: Index '{INDEX_NAME}' does not exist!")
        print("   Run: python index_company_data.py")
        return False
    print(f"✅ PASS: Index exists")
    
    # Get index stats
    index = pc.Index(INDEX_NAME)
    stats = index.describe_index_stats()
    
    print(f"\n[Test 2] Index statistics")
    print(f"✓ Total vectors: {stats.total_vector_count}")
    print(f"✓ Dimension: {stats.dimension}")
    
    if stats.total_vector_count == 0:
        print("❌ FAIL: Index is empty")
        return False
    
    # Test N8N retrieval pattern
    print(f"\n[Test 3] Simulating N8N Retrieve Documents")
    print("-" * 60)
    
    test_queries = [
        "What companies are available?",
        "Show me job openings",
        "What products are offered?",
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        
        # Generate embedding (like N8N does)
        query_embedding = generate_embedding(query)
        
        # Search (like N8N's Retrieve Documents tool)
        results = index.query(
            vector=query_embedding,
            top_k=3,
            include_metadata=True
        )
        
        if not results.matches:
            print(f"  ⚠️  No results found")
            continue
        
        print(f"  ✓ Found {len(results.matches)} documents")
        
        for i, match in enumerate(results.matches, 1):
            company_name = match.metadata.get('company_name', 'Unknown')
            text_length = len(match.metadata.get('text', ''))
            print(f"  {i}. {company_name} (score: {match.score:.3f}, text: {text_length} chars)")
            
            # Validate critical fields for N8N
            if 'text' not in match.metadata:
                print(f"     ❌ Missing 'text' field!")
            if 'company_name' not in match.metadata:
                print(f"     ❌ Missing 'company_name' field!")
    
    # Test metadata structure
    print(f"\n[Test 4] Validating metadata structure for N8N")
    print("-" * 60)
    
    # Get a sample document
    sample_query = generate_embedding("test query")
    results = index.query(
        vector=sample_query,
        top_k=1,
        include_metadata=True
    )
    
    if not results.matches:
        print("❌ Could not fetch sample document")
        return False
    
    sample = results.matches[0]
    required_fields = ['text', 'company_name', 'company_id']
    optional_fields = ['job_count', 'product_count', 'news_count', 'service_count', 
                      'industry', 'location', 'website']
    
    print(f"\nSample Document: {sample.id}")
    print("\nRequired fields:")
    all_required_present = True
    for field in required_fields:
        if field in sample.metadata:
            value_length = len(str(sample.metadata[field]))
            print(f"  ✓ {field} (length: {value_length})")
        else:
            print(f"  ❌ {field} - MISSING!")
            all_required_present = False
    
    print("\nOptional fields:")
    for field in optional_fields:
        if field in sample.metadata:
            print(f"  ✓ {field}: {sample.metadata[field]}")
    
    # Show text preview
    if 'text' in sample.metadata:
        text = sample.metadata['text']
        print(f"\nText field preview (first 500 chars):")
        print("-" * 60)
        print(text[:500] + "...")
        print("-" * 60)
    
    # Test filtering (N8N can use this)
    print(f"\n[Test 5] Testing metadata filters")
    print("-" * 60)
    
    # Test filter by job count
    results_with_jobs = index.query(
        vector=sample_query,
        top_k=10,
        include_metadata=True,
        filter={"job_count": {"$gt": 0}}
    )
    print(f"✓ Companies with jobs: {len(results_with_jobs.matches)}")
    
    # Test filter by company name
    if sample.metadata.get('company_name'):
        company_name = sample.metadata['company_name']
        results_specific = index.query(
            vector=sample_query,
            top_k=5,
            include_metadata=True,
            filter={"company_name": company_name}
        )
        print(f"✓ Documents for '{company_name}': {len(results_specific.matches)}")
    
    # Final validation
    print(f"\n{'=' * 60}")
    if all_required_present and stats.total_vector_count > 0:
        print("✅ ALL TESTS PASSED - INDEX READY FOR N8N!")
        print("=" * 60)
        print(f"\n✨ N8N Configuration:")
        print(f"   Index Name: {INDEX_NAME}")
        print(f"   Vector Store: Pinecone")
        print(f"   Embeddings: OpenAI (text-embedding-ada-002)")
        print(f"   Documents: {stats.total_vector_count} companies")
        print(f"\n📋 Next steps:")
        print(f"   1. Configure N8N Pinecone Vector Store node")
        print(f"   2. Set up Retrieve Documents tool")
        print(f"   3. Connect to RAG AI Agent")
        print(f"   4. Test with queries!")
        print(f"\n📖 See N8N_INTEGRATION_GUIDE.md for detailed setup")
        print("=" * 60)
        return True
    else:
        print("❌ TESTS FAILED - CHECK ERRORS ABOVE")
        print("=" * 60)
        return False


def interactive_test():
    """Interactive testing mode"""
    print("\n" + "=" * 60)
    print("INTERACTIVE TEST MODE")
    print("=" * 60)
    print("Test queries as your N8N agent would see them")
    print("Type 'quit' to exit\n")
    
    index = pc.Index(INDEX_NAME)
    
    while True:
        query = input("Enter query: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
        
        if not query:
            continue
        
        print("\n🔍 Searching...")
        embedding = generate_embedding(query)
        results = index.query(
            vector=embedding,
            top_k=3,
            include_metadata=True
        )
        
        if not results.matches:
            print("No results found\n")
            continue
        
        print(f"\n📄 Found {len(results.matches)} documents:\n")
        
        for i, match in enumerate(results.matches, 1):
            print(f"{'-' * 60}")
            print(f"Result #{i} - Score: {match.score:.4f}")
            print(f"Company: {match.metadata.get('company_name', 'Unknown')}")
            print(f"ID: {match.id}")
            
            # Show what N8N would retrieve
            text = match.metadata.get('text', '')
            if text:
                print(f"\nRetrieved text ({len(text)} chars):")
                print(text[:300] + "...\n")
        
        print(f"{'=' * 60}\n")


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("N8N INDEX TESTING TOOL")
    print("=" * 60)
    print("\n1. Run automated tests")
    print("2. Interactive testing")
    print("0. Exit")
    
    choice = input("\nChoice: ").strip()
    
    if choice == "1":
        test_n8n_index()
    elif choice == "2":
        interactive_test()
    elif choice == "0":
        print("\nGoodbye!")
    else:
        print("\nInvalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")

