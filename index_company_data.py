import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import json
from datetime import datetime
from typing import List, Dict, Any
import hashlib
from tqdm import tqdm
import logging
from env_config import postgres_config, required_env

# Load environment variables
load_dotenv()

# Configuration - using the same config from indexing.py
DB_CONFIG = postgres_config("COMPANY")
PINECONE_API_KEY = required_env("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "company-chatbot")
EMBEDDING_DIM = 1536  # OpenAI text-embedding-ada-002 dimension
OPENAI_API_KEY = required_env("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


class CompanyDataProcessor:
    """
    Processes company data and creates comprehensive single documents for N8N RAG Agent.
    Each company becomes ONE document containing all information.
    """
    
    def __init__(self):
        pass
    
    def generate_id(self, company_id: str) -> str:
        """Generate a unique ID from company ID"""
        return f"company_{company_id}"
    
    def create_comprehensive_document(self, company: Dict[str, Any]) -> str:
        """
        Create ONE comprehensive document containing ALL company information.
        Optimized for N8N RAG Agent retrieval.
        """
        sections = []
        
        # ===== COMPANY OVERVIEW =====
        company_name = company.get('name', 'Unknown Company')
        sections.append(f"# {company_name}\n")
        
        # Basic Information
        overview_parts = []
        if company.get('id'):
            overview_parts.append(f"Company ID: {company['id']}")
        if company.get('description'):
            overview_parts.append(f"Description: {company['description']}")
        if company.get('industry'):
            overview_parts.append(f"Industry: {company['industry']}")
        if company.get('location'):
            overview_parts.append(f"Location: {company['location']}")
        if company.get('website'):
            overview_parts.append(f"Website: {company['website']}")
        if company.get('email'):
            overview_parts.append(f"Email: {company['email']}")
        if company.get('phone'):
            overview_parts.append(f"Phone: {company['phone']}")
        if company.get('created_at'):
            overview_parts.append(f"Profile Created: {company['created_at']}")
        
        if overview_parts:
            sections.append("## Company Overview")
            sections.append("\n".join(overview_parts))
            sections.append("")
        
        # ===== JOBS =====
        jobs = company.get('jobs', [])
        if jobs:
            sections.append(f"## Job Openings ({len(jobs)} positions available)")
            sections.append("")
            
            for idx, job in enumerate(jobs, 1):
                job_parts = []
                if job.get('title'):
                    job_parts.append(f"### {idx}. {job['title']}")
                
                if job.get('description'):
                    job_parts.append(f"Description: {job['description']}")
                if job.get('requirements'):
                    job_parts.append(f"Requirements: {job['requirements']}")
                if job.get('location'):
                    job_parts.append(f"Location: {job['location']}")
                if job.get('employment_type'):
                    job_parts.append(f"Type: {job['employment_type']}")
                if job.get('salary_range'):
                    job_parts.append(f"Salary: {job['salary_range']}")
                if job.get('posted_at'):
                    job_parts.append(f"Posted: {job['posted_at']}")
                
                if job_parts:
                    sections.append("\n".join(job_parts))
                    sections.append("")
        
        # ===== PRODUCTS =====
        products = company.get('products', [])
        if products:
            sections.append(f"## Products & Services ({len(products)} items)")
            sections.append("")
            
            for idx, product in enumerate(products, 1):
                product_parts = []
                if product.get('name'):
                    product_parts.append(f"### {idx}. {product['name']}")
                
                if product.get('description'):
                    product_parts.append(f"Description: {product['description']}")
                if product.get('category'):
                    product_parts.append(f"Category: {product['category']}")
                if product.get('price'):
                    product_parts.append(f"Price: {product['price']}")
                if product.get('features'):
                    product_parts.append(f"Features: {product['features']}")
                
                if product_parts:
                    sections.append("\n".join(product_parts))
                    sections.append("")
        
        # ===== NEWS =====
        news = company.get('news', [])
        if news:
            sections.append(f"## Company News & Updates ({len(news)} articles)")
            sections.append("")
            
            for idx, article in enumerate(news, 1):
                news_parts = []
                if article.get('title'):
                    news_parts.append(f"### {idx}. {article['title']}")
                
                if article.get('content'):
                    news_parts.append(f"Content: {article['content']}")
                elif article.get('summary'):
                    news_parts.append(f"Summary: {article['summary']}")
                
                if article.get('published_at'):
                    news_parts.append(f"Published: {article['published_at']}")
                if article.get('source'):
                    news_parts.append(f"Source: {article['source']}")
                
                if news_parts:
                    sections.append("\n".join(news_parts))
                    sections.append("")
        
        # ===== SERVICES =====
        services = company.get('services', [])
        if services:
            sections.append(f"## Services Offered ({len(services)} services)")
            sections.append("")
            
            for idx, service in enumerate(services, 1):
                service_parts = []
                if service.get('name'):
                    service_parts.append(f"### {idx}. {service['name']}")
                
                if service.get('description'):
                    service_parts.append(f"Description: {service['description']}")
                if service.get('category'):
                    service_parts.append(f"Category: {service['category']}")
                if service.get('pricing'):
                    service_parts.append(f"Pricing: {service['pricing']}")
                if service.get('features'):
                    service_parts.append(f"Features: {service['features']}")
                
                if service_parts:
                    sections.append("\n".join(service_parts))
                    sections.append("")
        
        # Join all sections
        full_document = "\n".join(sections)
        return full_document.strip()
    
    def create_company_document(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a single document for a company with all information.
        Returns a dict ready for Pinecone indexing.
        """
        company_id = str(company.get('id', 'unknown'))
        company_name = company.get('name', 'Unknown Company')
        
        # Create comprehensive text
        full_text = self.create_comprehensive_document(company)
        
        # Create metadata for N8N RAG Agent
        metadata = {
            "company_id": company_id,
            "company_name": company_name,
            "text": full_text,  # N8N retrieves this field
        }
        
        # Add counts for filtering/searching
        if company.get('jobs'):
            metadata['job_count'] = len(company['jobs'])
        if company.get('products'):
            metadata['product_count'] = len(company['products'])
        if company.get('news'):
            metadata['news_count'] = len(company['news'])
        if company.get('services'):
            metadata['service_count'] = len(company['services'])
        
        # Add other useful fields if available
        if company.get('industry'):
            metadata['industry'] = company['industry']
        if company.get('location'):
            metadata['location'] = company['location']
        if company.get('website'):
            metadata['website'] = company['website']
        
        return {
            "id": self.generate_id(company_id),
            "text": full_text,
            "metadata": metadata
        }


class PineconeCompanyIndexer:
    """Handles Pinecone indexing operations for N8N RAG Agent"""
    
    def __init__(self):
        self.pinecone_index = None
        self.processor = CompanyDataProcessor()
    
    def connect_to_postgres(self) -> List[Dict[str, Any]]:
        """Fetch all companies with their related data from PostgreSQL"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            logging.info("Fetching companies from PostgreSQL...")
            cursor.execute("SELECT * FROM scraper_company;")
            companies = cursor.fetchall()
            
            logging.info(f"Found {len(companies)} companies, fetching related data...")
            
            for company in tqdm(companies, desc="Loading company data"):
                # Fetch jobs
                cursor.execute("SELECT * FROM scraper_job WHERE company_id = %s;", (company['id'],))
                company['jobs'] = [dict(row) for row in cursor.fetchall()]
                
                # Fetch products
                cursor.execute("SELECT * FROM scraper_product WHERE company_id = %s;", (company['id'],))
                company['products'] = [dict(row) for row in cursor.fetchall()]
                
                # Fetch news
                cursor.execute("SELECT * FROM scraper_news WHERE company_id = %s;", (company['id'],))
                company['news'] = [dict(row) for row in cursor.fetchall()]
                
                # Fetch services
                cursor.execute("SELECT * FROM scraper_service WHERE company_id = %s;", (company['id'],))
                company['services'] = [dict(row) for row in cursor.fetchall()]
            
            logging.info(f"Successfully loaded data for {len(companies)} companies")
            return companies
            
        except Exception as e:
            logging.error(f"PostgreSQL Error: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def init_pinecone(self) -> bool:
        """Initialize Pinecone index"""
        try:
            pc = Pinecone(api_key=PINECONE_API_KEY)
            
            if INDEX_NAME not in pc.list_indexes().names():
                logging.info(f"Creating new Pinecone index: {INDEX_NAME}")
                pc.create_index(
                    name=INDEX_NAME,
                    dimension=EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                logging.info(f"Created new index: {INDEX_NAME}")
            else:
                logging.info(f"Using existing index: {INDEX_NAME}")
            
            self.pinecone_index = pc.Index(INDEX_NAME)
            return True
            
        except Exception as e:
            logging.error(f"Pinecone Error: {e}")
            return False
    
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize metadata to ensure it's compatible with Pinecone"""
        sanitized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                try:
                    sanitized[key] = json.dumps(value, default=str)
                except Exception:
                    continue
            elif isinstance(value, (str, int, float, bool)):
                # Check string length - Pinecone has metadata size limits
                if isinstance(value, str) and len(value) > 40000:
                    sanitized[key] = value[:40000] + "... [truncated]"
                else:
                    sanitized[key] = value
            else:
                try:
                    sanitized[key] = str(value)
                except Exception:
                    continue
        return sanitized
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            # Truncate text if too long (OpenAI has a limit of ~8191 tokens)
            # Approximately 4 chars per token, so ~32000 chars max
            max_chars = 32000
            if len(text) > max_chars:
                logging.warning(f"Text truncated from {len(text)} to {max_chars} characters for embedding")
                text = text[:max_chars]
            
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=[text]
            )
            return response.data[0].embedding[:EMBEDDING_DIM]
            
        except Exception as e:
            logging.error(f"Embedding Error: {e}")
            return None
    
    def index_companies(self, companies: List[Dict[str, Any]], clear_existing: bool = True) -> bool:
        """
        Index all companies into Pinecone.
        Each company becomes ONE document (no chunking).
        """
        if not self.pinecone_index:
            logging.error("Pinecone not initialized")
            return False
        
        if clear_existing:
            logging.info("Clearing existing index...")
            self.pinecone_index.delete(delete_all=True)
        
        try:
            # Process all companies into documents
            logging.info("Processing companies into documents...")
            documents = []
            
            for company in tqdm(companies, desc="Processing companies"):
                doc = self.processor.create_company_document(company)
                documents.append(doc)
            
            logging.info(f"Created {len(documents)} documents from {len(companies)} companies")
            
            # Generate embeddings and index
            logging.info("Generating embeddings and indexing...")
            batch = []
            
            for doc in tqdm(documents, desc="Generating embeddings"):
                embedding = self._generate_embedding(doc['text'])
                if not embedding:
                    logging.warning(f"Skipping document {doc['id']} - embedding generation failed")
                    continue
                
                sanitized_metadata = self._sanitize_metadata(doc['metadata'])
                
                batch.append({
                    "id": doc['id'],
                    "values": embedding,
                    "metadata": sanitized_metadata
                })
                
                # Upload in batches of 100
                if len(batch) >= 100:
                    self.pinecone_index.upsert(vectors=batch)
                    logging.info(f"Indexed {len(batch)} documents")
                    batch = []
            
            # Upload remaining batch
            if batch:
                self.pinecone_index.upsert(vectors=batch)
                logging.info(f"Indexed final {len(batch)} documents")
            
            logging.info("✅ Indexing completed successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Indexing Error: {e}")
            return False


def main():
    """Main execution function"""
    print("=" * 60)
    print("COMPANY DATA INDEXING FOR N8N RAG AGENT")
    print("=" * 60)
    print()
    print("📋 Configuration:")
    print(f"  - Index: {INDEX_NAME}")
    print(f"  - Embedding Model: text-embedding-ada-002")
    print(f"  - Dimension: {EMBEDDING_DIM}")
    print(f"  - Format: One document per company (no chunking)")
    print("=" * 60)
    print()
    
    indexer = PineconeCompanyIndexer()
    
    # Step 1: Fetch data from PostgreSQL
    print("Step 1: Fetching company data from PostgreSQL...")
    companies = indexer.connect_to_postgres()
    
    if not companies:
        logging.error("No companies found or database connection failed")
        return
    
    print(f"✓ Found {len(companies)} companies")
    
    # Print some statistics
    total_jobs = sum(len(c.get('jobs', [])) for c in companies)
    total_products = sum(len(c.get('products', [])) for c in companies)
    total_news = sum(len(c.get('news', [])) for c in companies)
    total_services = sum(len(c.get('services', [])) for c in companies)
    
    print(f"  - Total jobs: {total_jobs}")
    print(f"  - Total products: {total_products}")
    print(f"  - Total news articles: {total_news}")
    print(f"  - Total services: {total_services}")
    print()
    
    # Step 2: Initialize Pinecone
    print("Step 2: Initializing Pinecone...")
    if not indexer.init_pinecone():
        logging.error("Failed to initialize Pinecone")
        return
    print("✓ Pinecone initialized")
    print()
    
    # Step 3: Index companies
    print("Step 3: Indexing companies to Pinecone...")
    print("  (Creating one comprehensive document per company)")
    print()
    if indexer.index_companies(companies, clear_existing=True):
        print()
        print("=" * 60)
        print("✅ ALL DONE! Your data is ready for N8N RAG Agent")
        print("=" * 60)
        print()
        print("📌 What was indexed:")
        print(f"  - {len(companies)} company documents")
        print(f"  - Each document contains: overview, jobs, products, news, services")
        print()
        print("🔧 N8N Configuration:")
        print(f"  - Pinecone Index Name: {INDEX_NAME}")
        print(f"  - Vector Store: Pinecone")
        print(f"  - Embeddings: OpenAI (text-embedding-ada-002)")
        print(f"  - Retrieve Mode: Vector Search")
        print()
        print("✨ Your N8N RAG Agent can now:")
        print("  - Answer questions about companies")
        print("  - Search for jobs, products, services, news")
        print("  - Provide comprehensive company information")
        print("=" * 60)
    else:
        print()
        print("❌ Indexing failed. Check the logs above for errors.")


if __name__ == "__main__":
    main()
