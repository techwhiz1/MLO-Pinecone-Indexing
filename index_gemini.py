import requests
import json
import hashlib
import logging
import os
from tqdm import tqdm
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from pinecone import Pinecone, ServerlessSpec
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import google.generativeai as genai
from env_config import required_env

# === CONFIG ===
INDEX_NAME = os.getenv("GEMINI_INDEX_NAME", "lg-index-gemini")
EMBEDDING_MODEL = "models/text-embedding-004"  # Google's 768D model
EMBEDDING_DIM = 768  # Now matches Pinecone index
BATCH_SIZE = 50
MAX_WORKERS = 8
TEXT_CHUNK_SIZE = 1000
TEXT_CHUNK_OVERLAP = 200

PINECONE_API_KEY = os.getenv("GEMINI_PINECONE_API_KEY") or required_env("PINECONE_API_KEY")
GOOGLE_API_KEY = required_env("GOOGLE_API_KEY")

# Initialize clients
genai.configure(api_key=GOOGLE_API_KEY)
embedding_client = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL,
    google_api_key=GOOGLE_API_KEY
)
pc = Pinecone(api_key=PINECONE_API_KEY)

class EnhancedWebsiteProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=TEXT_CHUNK_SIZE,
            chunk_overlap=TEXT_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " "]
        )

    def generate_id(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def format_bonus_info(self, bonus_data: Dict) -> str:
        if not bonus_data:
            return "No bonus information available"
        return (
            f"Bonus Terms: {bonus_data.get('terms', 'N/A')}\n"
            f"Advantages: {', '.join(bonus_data.get('advantages', [])) or 'N/A'}"
        )

    def get_tracker_url(self, website: Dict[str, Any]) -> str:
        """Extracts the TOP category URL from website data"""
        for category in website.get("categories", []):
            if isinstance(category, dict) and category.get("category") == "TOP":
                return category.get("url", "")
        return ""

    def process_website(self, website: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            tracker_url = self.get_tracker_url(website)
            
            # Enhanced metadata with all relevant fields
            metadata = {
                "name": website.get("name", "Unknown"),
                "license": website.get("license", []),
                "status": website.get("status", "Unknown"),
                "products": website.get("products", []),
                "categories": [f"{c.get('category', '')} (Rating: {c.get('rating', 'N/A')})" 
                              for c in website.get("categories", [])],
                "min_deposit": website.get("min_deposit", "Unknown"),
                "withdrawal_limit": website.get("monthly_withdrawal_limit", "Unknown"),
                "visitors": website.get("monthly_visitors", "Unknown"),
                "owned_by": website.get("owned_by", "Unknown"),
                "headquarters": website.get("headquarters", "Unknown"),
                "founded": website.get("founded", "Unknown"),
                "accepted_countries": website.get("countries", {}).get("accepted", []),
                "restricted_countries": website.get("countries", {}).get("restricted", []),
                "crypto_payments": website.get("payments", {}).get("crypto", []),
                "traditional_payments": website.get("payments", {}).get("traditional", []),
                "providers": website.get("providers", []),
                "bonus_terms": self.format_bonus_info(website.get("bonus", {})),
                "customer_support_languages": website.get("languages", {}).get("customer_support", []),
                "website_languages": website.get("languages", {}).get("website", []),
                "tracker_url": tracker_url  # NEW: Added tracker URL
            }

            # Build comprehensive text for embedding
            text_parts = [
                f"## {metadata['name']}",
                f"- Tracker Url: {metadata['tracker_url']}",
                f"**Description**: {website.get('about', 'No description available')}",
                f"**License**: {', '.join(metadata['license'])}",
                f"**Products Offered**: {', '.join(metadata['products'])}",
                f"**Key Features**:",
                f"- Founded: {metadata['founded']}",
                f"- Minimum Deposit: {metadata['min_deposit']}",
                f"- Withdrawal Limit: {metadata['withdrawal_limit']}",
                f"- Monthly Visitors: {metadata['visitors']}",
                "",
                f"**Payment Methods**:",
                f"- Cryptocurrencies: {', '.join(metadata['crypto_payments'][:15])}",
                f"- Traditional: {', '.join(metadata['traditional_payments'][:15])}",
                "",
                f"**Game Providers**: {', '.join(metadata['providers'][:20])}",
                "",
                f"**Bonus Information**:\n{metadata['bonus_terms']}",
                "",
                f"**Country Restrictions**:",
                f"- Accepts players from: {', '.join(metadata['accepted_countries'][:10])} [...]",
                f"- Restricted in: {', '.join(metadata['restricted_countries'][:10])} [...]",
                "",
                f"**Language Support**:",
                f"- Customer Support: {', '.join(metadata['customer_support_languages'])}",
               
                f"- Website: {', '.join(metadata['website_languages'])}"
            ]

            full_text = "\n".join([p for p in text_parts if p])
            chunks = self.text_splitter.split_text(full_text)

            return [{
                "id": f"{self.generate_id(metadata['name'])}-chunk{i}",
                "text": chunk,
                "metadata": metadata
            } for i, chunk in enumerate(chunks)]

        except Exception as e:
            logging.error(f"Error processing website {website.get('name', 'unknown')}: {str(e)}")
            return []

class OptimizedPineconeIndexer:
    def __init__(self):
        self.index = self.initialize_index()

    def initialize_index(self):
        if INDEX_NAME not in pc.list_indexes().names():
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        return pc.Index(INDEX_NAME)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        try:
            return embedding_client.embed_documents(texts)
        except Exception as e:
            logging.error(f"Embedding generation failed: {str(e)}")
            return []

    def process_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return

        try:
            texts = [item["text"] for item in batch]
            embeddings = self.generate_embeddings(texts)
            
            if not embeddings:
                logging.error("No embeddings generated for batch")
                return

            vectors = [{
                "id": item["id"],
                "values": emb,
                "metadata": {
                    **item["metadata"],
                    "text": item["text"],
                    "source": item["metadata"]["name"],
                    "tracker_url": item["metadata"].get("tracker_url", "")  # Ensure URL is included
                }
            } for item, emb in zip(batch, embeddings)]

            # Upsert with error handling
            for i in range(0, len(vectors), 100):
                try:
                    self.index.upsert(vectors=vectors[i:i+100])
                except Exception as e:
                    logging.error(f"Failed to upsert batch {i//100}: {str(e)}")
                    continue

            logging.info(f"Processed batch of {len(batch)} chunks")

        except Exception as e:
            logging.error(f"Batch processing failed: {str(e)}")

def fetch_website_data() -> List[Dict[str, Any]]:
    try:
        response = requests.get(
            "https://guru-back.refactoring.dev.gggroup.media/companies/LG/LT/TOP",
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("websites", [])
    except Exception as e:
        logging.error(f"Data fetch failed: {str(e)}")
        return []

def main():
    # Initialize processors
    processor = EnhancedWebsiteProcessor()
    indexer = OptimizedPineconeIndexer()

    # Fetch and process data
    websites = fetch_website_data()
    if not websites:
        logging.error("No website data received")
        return

    # Process in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(processor.process_website, site) for site in websites]
        all_chunks = []
        
        for future in tqdm(futures, desc="Processing Websites"):
            try:
                chunks = future.result()
                all_chunks.extend(chunks)
            except Exception as e:
                logging.error(f"Processing failed: {str(e)}")

    # Index in batches
    for i in tqdm(range(0, len(all_chunks), BATCH_SIZE), desc="Indexing"):
        batch = all_chunks[i:i+BATCH_SIZE]
        indexer.process_batch(batch)

    logging.info(f"✅ Completed indexing {len(all_chunks)} document chunks")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    main()
