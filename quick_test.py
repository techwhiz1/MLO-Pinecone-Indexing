"""
Quick Test Script - Simple automated validation of indexed data
Run this after indexing to quickly verify everything worked correctly
"""
import os
from pinecone import Pinecone
from openai import OpenAI
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


def quick_test():
    """Run quick validation tests"""
    print("\n" + "=" * 60)
    print("QUICK VALIDATION TEST")
    print("=" * 60)
    
    # Test 1: Check if index exists
    print("\n[Test 1] Checking if index exists...")
    try:
        if INDEX_NAME not in pc.list_indexes().names():
            print(f"❌ FAIL: Index '{INDEX_NAME}' does not exist!")
            print("   Please run index_company_data.py first.")
            return False
        print(f"✅ PASS: Index '{INDEX_NAME}' exists")
    except Exception as e:
        print(f"❌ FAIL: Error connecting to Pinecone: {e}")
        return False
    
    # Test 2: Get index stats
    print("\n[Test 2] Getting index statistics...")
    try:
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        vector_count = stats.total_vector_count
        
        if vector_count == 0:
            print(f"❌ FAIL: Index is empty (0 vectors)")
            return False
        
        print(f"✅ PASS: Index contains {vector_count} vectors")
        print(f"   Dimension: {stats.dimension}")
    except Exception as e:
        print(f"❌ FAIL: Error getting stats: {e}")
        return False
    
    # Test 3: Test query functionality
    print("\n[Test 3] Testing search functionality...")
    try:
        test_query = "What companies are available?"
        
        # Generate embedding
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[test_query]
        )
        query_embedding = response.data[0].embedding[:EMBEDDING_DIM]
        
        # Search
        results = index.query(
            vector=query_embedding,
            top_k=3,
            include_metadata=True
        )
        
        if not results.matches:
            print(f"❌ FAIL: Search returned no results")
            return False
        
        print(f"✅ PASS: Search returned {len(results.matches)} results")
        
        # Test 4: Validate metadata structure
        print("\n[Test 4] Validating metadata structure...")
        required_fields = ['text', 'chunk_type', 'company_id', 'company_name']
        
        first_match = results.matches[0]
        missing_fields = []
        
        for field in required_fields:
            if field not in first_match.metadata:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ FAIL: Missing required fields: {missing_fields}")
            return False
        
        print(f"✅ PASS: All required metadata fields present")
        
        # Test 5: Validate text content
        print("\n[Test 5] Validating text content...")
        text_content = first_match.metadata.get('text', '')
        
        if not text_content or len(text_content) < 10:
            print(f"❌ FAIL: Text content is empty or too short")
            return False
        
        print(f"✅ PASS: Text content is valid ({len(text_content)} characters)")
        
        # Display sample result
        print("\n" + "-" * 60)
        print("SAMPLE RESULT:")
        print("-" * 60)
        print(f"Company: {first_match.metadata.get('company_name')}")
        print(f"Chunk Type: {first_match.metadata.get('chunk_type')}")
        print(f"Score: {first_match.score:.4f}")
        print(f"\nText Preview (first 300 chars):")
        print(text_content[:300] + "...")
        print("-" * 60)
        
        # Test 6: Test filtering by chunk type
        print("\n[Test 6] Testing chunk type filtering...")
        chunk_types = ['overview', 'jobs', 'products', 'news', 'services']
        found_types = set()
        
        for chunk_type in chunk_types:
            results = index.query(
                vector=query_embedding,
                top_k=10,
                include_metadata=True,
                filter={"chunk_type": chunk_type}
            )
            if results.matches:
                found_types.add(chunk_type)
        
        if not found_types:
            print(f"⚠️  WARNING: No chunk type filters returned results")
        else:
            print(f"✅ PASS: Found chunks of types: {', '.join(found_types)}")
        
    except Exception as e:
        print(f"❌ FAIL: Error during testing: {e}")
        return False
    
    # All tests passed
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print(f"\nYour Pinecone index is ready for chatbot use!")
    print(f"Index: {INDEX_NAME}")
    print(f"Vectors: {vector_count}")
    print(f"Available chunk types: {', '.join(found_types)}")
    print("\nNext steps:")
    print("  1. Use test_index.py for detailed testing")
    print("  2. Integrate with your chatbot using the query pattern shown above")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = quick_test()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        exit(1)

