"""
Test script for Chatbot API
Simple script to test the API endpoints
"""
import requests
import json
import sys

API_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n⚠️  Make sure the API server is running:")
        print("   python chatbot_api.py")
        return False


def test_chat(session_id, question):
    """Test chat endpoint"""
    print("\n" + "=" * 60)
    print(f"Testing Chat Endpoint")
    print("=" * 60)
    print(f"Session ID: {session_id}")
    print(f"Question: {question}")
    print("-" * 60)
    
    try:
        payload = {
            "sessionId": session_id,
            "action": "sendMessage",
            "chatInput": question
        }
        
        response = requests.post(
            f"{API_URL}/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success!")
            print(f"\nAnswer:\n{result['output']}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_multiple_questions():
    """Test multiple questions in conversation"""
    print("\n" + "=" * 60)
    print("Testing Conversation Flow")
    print("=" * 60)
    
    session_id = "test-conversation-001"
    
    questions = [
        "Which companies provide engineering services",
        "List all producing Mines",
        "List all mining equipment suppliers",
        "Which companies have job openings?",
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n--- Question {i}/{len(questions)} ---")
        success = test_chat(session_id, question)
        if not success:
            print("Stopping test due to error")
            break
        
        if i < len(questions):
            input("\nPress Enter to continue to next question...")


def test_api_format():
    """Test exact API format from user's request"""
    print("\n" + "=" * 60)
    print("Testing Exact API Format")
    print("=" * 60)
    
    # Exact request format from user
    request_body = {
        "sessionId": "2ed5f805a1ea49009465c329a0910d09",
        "action": "sendMessage",
        "chatInput": "Which companies provide engineering services"
    }
    
    print("Request Body:")
    print(json.dumps(request_body, indent=2))
    print("\nSending request...")
    
    try:
        response = requests.post(
            f"{API_URL}/chat",
            json=request_body,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Response Format:")
            print(json.dumps(result, indent=2))
            
            # Verify format
            if "output" in result:
                print("\n✅ Response format matches expected format!")
                print(f"\nOutput:\n{result['output']}")
                return True
            else:
                print("\n❌ Response missing 'output' field")
                return False
        else:
            print(f"\n❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def interactive_test():
    """Interactive testing mode"""
    print("\n" + "=" * 60)
    print("Interactive API Test")
    print("=" * 60)
    print("Type your questions or 'quit' to exit")
    print("=" * 60 + "\n")
    
    session_id = "interactive-test-session"
    
    while True:
        try:
            question = input("Your question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
            
            if not question:
                continue
            
            test_chat(session_id, question)
            print()
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break


def run_all_tests():
    """Run all automated tests"""
    print("\n" + "=" * 60)
    print("CHATBOT API - AUTOMATED TESTS")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health()))
    
    input("\nPress Enter to continue...")
    
    # Test 2: API format test
    results.append(("API Format", test_api_format()))
    
    input("\nPress Enter to continue...")
    
    # Test 3: Simple question
    results.append(("Simple Question", test_chat("test-001", "What companies are available?")))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("CHATBOT API TEST SCRIPT")
    print("=" * 60)
    print("\nMake sure the API is running first:")
    print("  python chatbot_api.py")
    print("\nOptions:")
    print("  1. Run all automated tests")
    print("  2. Test exact API format (from your example)")
    print("  3. Test conversation flow")
    print("  4. Interactive testing")
    print("  5. Quick health check")
    print("  0. Exit")
    print("=" * 60)
    
    choice = input("\nChoice: ").strip()
    
    if choice == "1":
        run_all_tests()
    elif choice == "2":
        test_api_format()
    elif choice == "3":
        test_multiple_questions()
    elif choice == "4":
        interactive_test()
    elif choice == "5":
        test_health()
    elif choice == "0":
        print("\nGoodbye!")
    else:
        print("\n❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\n\nError: {e}")

