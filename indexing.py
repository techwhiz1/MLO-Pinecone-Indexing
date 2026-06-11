import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
import json
from datetime import datetime
from env_config import postgres_config, required_env

load_dotenv()
client = OpenAI(api_key=required_env("OPENAI_API_KEY"))

# Configuration
DB_CONFIG = postgres_config("COMPANY")
PINECONE_API_KEY = required_env("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "company-chatbot")
EMBEDDING_DIM = 1536  # Must match Pinecone index

class PineconeIndexer:
    def __init__(self):
        self.pinecone_index = None

    def connect_to_postgres(self):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM scraper_company;")
            companies = cursor.fetchall()
            batch = []
            for company in companies:
                # jobs = []
                cursor.execute("SELECT * FROM scraper_job WHERE company_id = %s;", (company['id'],))
                jobs = [dict(row) for row in cursor.fetchall()]
                # products = []
                cursor.execute("SELECT * FROM scraper_product WHERE company_id = %s;", (company['id'],))
                products = [dict(row) for row in cursor.fetchall()]
                # news = []
                cursor.execute("SELECT * FROM scraper_news WHERE company_id = %s;", (company['id'],))
                news = [dict(row) for row in cursor.fetchall()]
                # services = []
                cursor.execute("SELECT * FROM scraper_service WHERE company_id = %s;", (company['id'],))
                services = [dict(row) for row in cursor.fetchall()]
                company['jobs'] = jobs
                company['products'] = products
                company['news'] = news
                company['services'] = services
                # print(company)
            return companies
        except Exception as e:
            print(f"PostgreSQL Error: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def init_pinecone(self):
        try:
            pc = Pinecone(api_key=PINECONE_API_KEY)
            if INDEX_NAME not in pc.list_indexes().names():
                pc.create_index(
                    name=INDEX_NAME,
                    dimension=EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                print(f"Created new index: {INDEX_NAME}")
            self.pinecone_index = pc.Index(INDEX_NAME)
            return True
        except Exception as e:
            print(f"Pinecone Error: {e}")
            return False
    def _sanitize_metadata(self, article):
        metadata = {}
        for key, value in article.items():
            if value is None:
                continue  # skip nulls
            if isinstance(value, datetime):
                metadata[key] = value.isoformat()  # convert datetime → string
            elif isinstance(value, (list, dict)):
                try:
                    metadata[key] = json.dumps(value, default=str)  # convert nested to string
                except Exception:
                    continue
            else:
                metadata[key] = value
        return metadata

    def index_articles(self, articles):
        if not self.pinecone_index:
            print("Pinecone not initialized")
            return False

        self.pinecone_index.delete(delete_all=True)  # Clear existing index
        try:
            batch = []
            for article in articles:
                embedding = self._generate_embeddings(article)
                if not embedding:
                    continue
                batch.append({
                    "id": str(article['id']),
                    "values": embedding,
                    "metadata": self._sanitize_metadata(article)
                })

            for i in range(0, len(batch), 100):
                chunk = batch[i:i+100]
                self.pinecone_index.upsert(vectors=chunk)
                print(f"Indexed {len(chunk)} articles")

            return True
        except Exception as e:
            print(f"Indexing Error: {e}")
            return False

    def _generate_embeddings(self, article):
        try:
            text = article.get('name', '')[:1000]
            if not text.strip():
                return None
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=[text]
            )
            return response.data[0].embedding[:EMBEDDING_DIM]
        except Exception as e:
            print(f"Embedding Error: {e}")
            return None


if __name__ == "__main__":
    print("Starting indexing process...")

    indexer = PineconeIndexer()

    print("Fetching articles from PostgreSQL...")
    articles = indexer.connect_to_postgres()
    print(articles)
    print(f"Found {len(articles)} articles")

    print("Initializing Pinecone...")
    if not indexer.init_pinecone():
        exit(1)

    print("Indexing articles...")
    if indexer.index_articles(articles):
        print("Indexing completed successfully!")
    else:
        print("Indexing failed")
