import os
import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
import select
import json
import math
import time
from datetime import datetime
from pinecone import AwsRegion, CloudProvider, Pinecone, ServerlessSpec
from openai import OpenAI
from env_config import postgres_config, required_env

# --- Configuration ---
DB_CONFIG = postgres_config("PRODUCT")
PINECONE_API_KEY = os.getenv("PRODUCT_PINECONE_API_KEY") or required_env("PINECONE_API_KEY")
OPENAI_API_KEY = required_env("OPENAI_API_KEY")
INDEX_NAME = os.getenv("PRODUCT_INDEX_NAME", "products")
NEWS_INDEX_NAME = os.getenv("NEWS_INDEX_NAME", "news")
JOB_INDEX_NAME = os.getenv("JOB_INDEX_NAME", "jobs")
EMBEDDING_DIM = 1536
PRODUCT_EMBEDDING_DIM = 1024
PRODUCT_BATCH_SIZE = 96
JOB_EMBEDDING_DIM = 1024
JOB_BATCH_SIZE = 96
DEFAULT_NAMESPACE = "__default__"
PINECONE_EMBED_TOKENS_PER_MIN = int(os.getenv("PINECONE_EMBED_TOKENS_PER_MIN", "750000"))
EMBEDDING_CHARS_PER_TOKEN = int(os.getenv("EMBEDDING_CHARS_PER_TOKEN", "4"))
PINECONE_EMBED_MAX_RETRIES = int(os.getenv("PINECONE_EMBED_MAX_RETRIES", "5"))
PINECONE_EMBED_RETRY_SECONDS = int(os.getenv("PINECONE_EMBED_RETRY_SECONDS", "65"))

openai_client = OpenAI(api_key=OPENAI_API_KEY)


class TokenPerMinuteLimiter:
    def __init__(self, limit):
        self.limit = limit
        self.window_start = time.monotonic()
        self.used = 0

    def wait_for(self, tokens):
        now = time.monotonic()
        elapsed = now - self.window_start
        if elapsed >= 60:
            self.window_start = now
            self.used = 0
            elapsed = 0

        if self.used and self.used + tokens > self.limit:
            sleep_for = max(1, 60 - elapsed)
            print(
                f"Pinecone embedding token budget reached "
                f"({self.used + tokens}/{self.limit} estimated tokens). "
                f"Sleeping {sleep_for:.0f}s..."
            )
            time.sleep(sleep_for)
            self.window_start = time.monotonic()
            self.used = 0

        self.used += tokens

    def reset(self):
        self.window_start = time.monotonic()
        self.used = 0


integrated_embedding_limiter = TokenPerMinuteLimiter(PINECONE_EMBED_TOKENS_PER_MIN)


def estimate_integrated_embedding_tokens(records):
    chars = sum(len(record.get("chunk_text", "")) for record in records)
    return max(len(records), math.ceil(chars / EMBEDDING_CHARS_PER_TOKEN))


def is_pinecone_rate_limit_error(exc):
    message = str(exc)
    return (
        "429" in message
        or "Too Many Requests" in message
        or "RESOURCE_EXHAUSTED" in message
        or "max tokens per minute" in message
    )


def upsert_integrated_records(index, records, label):
    estimated_tokens = estimate_integrated_embedding_tokens(records)

    for attempt in range(1, PINECONE_EMBED_MAX_RETRIES + 1):
        integrated_embedding_limiter.wait_for(estimated_tokens)
        try:
            index.upsert_records(namespace=DEFAULT_NAMESPACE, records=records)
            return
        except Exception as exc:
            if not is_pinecone_rate_limit_error(exc) or attempt == PINECONE_EMBED_MAX_RETRIES:
                raise

            print(
                f"Pinecone rate limit while indexing {label} "
                f"(attempt {attempt}/{PINECONE_EMBED_MAX_RETRIES}). "
                f"Sleeping {PINECONE_EMBED_RETRY_SECONDS}s before retry..."
            )
            integrated_embedding_limiter.reset()
            time.sleep(PINECONE_EMBED_RETRY_SECONDS)


# --- Pinecone Setup ---
def init_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if INDEX_NAME not in pc.list_indexes().names():
        pc.create_index_for_model(
            name=INDEX_NAME,
            cloud=CloudProvider.AWS,
            region=AwsRegion.US_EAST_1,
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"},
                "metric": "cosine",
                "read_parameters": {
                    "input_type": "query",
                    "dimension": PRODUCT_EMBEDDING_DIM,
                },
                "write_parameters": {
                    "input_type": "passage",
                    "dimension": PRODUCT_EMBEDDING_DIM,
                },
            }
        )
        print(f"Created new Pinecone index: {INDEX_NAME}")
    else:
        print(f"Connected to existing Pinecone index: {INDEX_NAME}")
    return pc.Index(INDEX_NAME)


def init_news_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if NEWS_INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=NEWS_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Created new Pinecone index: {NEWS_INDEX_NAME}")
    else:
        print(f"Connected to existing Pinecone index: {NEWS_INDEX_NAME}")
    return pc.Index(NEWS_INDEX_NAME)


def init_job_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    if JOB_INDEX_NAME not in pc.list_indexes().names():
        pc.create_index_for_model(
            name=JOB_INDEX_NAME,
            cloud=CloudProvider.AWS,
            region=AwsRegion.US_EAST_1,
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"},
                "metric": "cosine",
                "read_parameters": {
                    "input_type": "query",
                    "dimension": JOB_EMBEDDING_DIM,
                },
                "write_parameters": {
                    "input_type": "passage",
                    "dimension": JOB_EMBEDDING_DIM,
                },
            },
        )
        print(f"Created new Pinecone index: {JOB_INDEX_NAME}")
    else:
        print(f"Connected to existing Pinecone index: {JOB_INDEX_NAME}")
    return pc.Index(JOB_INDEX_NAME)


# --- Embedding ---
def generate_embedding(text):
    if not text or not text.strip():
        return None
    response = openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=[text[:8000]],
    )
    return response.data[0].embedding[:EMBEDDING_DIM]


# --- PostgreSQL Helpers ---
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def fetch_category_hierarchy(cursor, subcategory_id):
    """Walk up ProductCategory tree to build 4-level taxonomy."""
    if not subcategory_id:
        return {}

    path = []
    current = subcategory_id
    while current:
        cursor.execute(
            'SELECT id, name, slug, "parentId" FROM "ProductCategory" WHERE id = %s;',
            (current,)
        )
        row = cursor.fetchone()
        if not row:
            break
        path.append(dict(row))
        current = row["parentId"]

    # Reverse: path[0]=cluster, path[1]=category, path[2]=class, path[3]=subclass
    path = list(reversed(path))

    taxonomy = {}
    level_names = ["cluster", "category", "class", "subclass"]
    taxonomy_ids = []

    for i, level in enumerate(level_names):
        if i < len(path):
            node = path[i]
            taxonomy[f"taxonomy_{level}"] = node["name"]
            taxonomy[f"taxonomy_{level}_slug"] = node["slug"]
            taxonomy[f"taxonomy_{level}_id"] = node["id"]
            taxonomy_ids.append(f"{level}_{node['slug']}")

    # Build taxonomy_path string for easy text search
    if path:
        taxonomy["taxonomy_path"] = " > ".join(
            node["slug"] for node in path
        )
    taxonomy["taxonomy_ids"] = taxonomy_ids

    return taxonomy


def fetch_microsite(cursor, microsite_id):
    """Fetch Microsite data by id."""
    if not microsite_id:
        return {}
    cursor.execute('SELECT * FROM "Microsite" WHERE id = %s;', (microsite_id,))
    row = cursor.fetchone()
    if not row:
        return {}
    return dict(row)


def fetch_product_with_facets(cursor, product_id):
    cursor.execute('SELECT * FROM "Product" WHERE id = %s;', (product_id,))
    product = cursor.fetchone()
    if not product:
        return None
    product = dict(product)
    product["facets"] = fetch_facets_for_product(cursor, product_id)
    product["taxonomy"] = fetch_category_hierarchy(cursor, product.get("subcategoryId"))
    product["microsite"] = fetch_microsite(cursor, product.get("micrositeId"))
    return product


def fetch_facets_for_product(cursor, product_id):
    cursor.execute('''
        SELECT pd.key, pd.label, pd."valueType", pd.unit, pv.value, pv."normalizedValue"
        FROM "ProductFacetValue" pv
        JOIN "ProductFacetDefinition" pd ON pv."facetId" = pd.id
        WHERE pv."productId" = %s;
    ''', (product_id,))
    return [dict(row) for row in cursor.fetchall()]


def fetch_all_products_with_facets():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT * FROM "Product";')
        products = [dict(row) for row in cursor.fetchall()]

        # Fetch all facets
        cursor.execute('''
            SELECT pv."productId", pd.key, pd.label, pd."valueType", pd.unit,
                   pv.value, pv."normalizedValue"
            FROM "ProductFacetValue" pv
            JOIN "ProductFacetDefinition" pd ON pv."facetId" = pd.id;
        ''')
        all_facets = cursor.fetchall()

        # Group facets by productId
        facets_by_product = {}
        for fv in all_facets:
            pid = fv["productId"]
            facets_by_product.setdefault(pid, []).append(dict(fv))

        # Pre-fetch all categories for efficiency
        cursor.execute('SELECT id, name, slug, "parentId" FROM "ProductCategory";')
        all_categories = {row["id"]: dict(row) for row in cursor.fetchall()}

        # Pre-fetch all microsites for efficiency
        cursor.execute('SELECT * FROM "Microsite";')
        all_microsites = {row["id"]: dict(row) for row in cursor.fetchall()}

        for product in products:
            product["facets"] = facets_by_product.get(product["id"], [])
            product["taxonomy"] = build_taxonomy_from_cache(
                all_categories, product.get("subcategoryId")
            )
            product["microsite"] = all_microsites.get(product.get("micrositeId"), {})

        return products
    finally:
        conn.close()


def build_taxonomy_from_cache(all_categories, subcategory_id):
    """Walk up category tree using pre-fetched category dict."""
    if not subcategory_id:
        return {}

    path = []
    current = subcategory_id
    while current:
        node = all_categories.get(current)
        if not node:
            break
        path.append(node)
        current = node.get("parentId")

    path = list(reversed(path))

    taxonomy = {}
    level_names = ["cluster", "category", "class", "subclass"]
    taxonomy_ids = []

    for i, level in enumerate(level_names):
        if i < len(path):
            node = path[i]
            taxonomy[f"taxonomy_{level}"] = node["name"]
            taxonomy[f"taxonomy_{level}_slug"] = node["slug"]
            taxonomy[f"taxonomy_{level}_id"] = node["id"]
            taxonomy_ids.append(f"{level}_{node['slug']}")

    if path:
        taxonomy["taxonomy_path"] = " > ".join(
            node["slug"] for node in path
        )
    taxonomy["taxonomy_ids"] = taxonomy_ids

    return taxonomy


# --- Build Pinecone Vector Record ---
PRODUCT_TEXT_PRIORITY_FIELDS = (
    "id", "name", "slug", "description", "modelType", "sku", "status",
    "basePrice", "currency", "stockQuantity", "promoMessage", "isFeatured",
    "primaryImageUrl", "micrositeId", "subcategoryId", "createdAt", "updatedAt",
)
PRODUCT_NESTED_FIELDS = {"facets", "taxonomy", "microsite"}
EMBEDDING_VALUE_MAX_CHARS = 4000


def format_embedding_value(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        if not value:
            return None
        text = json.dumps(value, default=str, sort_keys=True, ensure_ascii=False)
    else:
        text = str(value)

    text = " ".join(text.split())
    if not text:
        return None
    if len(text) > EMBEDDING_VALUE_MAX_CHARS:
        return f"{text[:EMBEDDING_VALUE_MAX_CHARS]}..."
    return text


def append_embedding_line(lines, key, value):
    formatted = format_embedding_value(value)
    if formatted is not None:
        lines.append(f"{key}: {formatted}")


def build_embedding_text(product):
    lines = [
        "record_type: product",
        "content_format: structured key value text for semantic product search",
    ]

    added_keys = set()
    for key in PRODUCT_TEXT_PRIORITY_FIELDS:
        if key in product and key not in PRODUCT_NESTED_FIELDS:
            append_embedding_line(lines, f"product.{key}", product.get(key))
            added_keys.add(key)

    for key in sorted(product.keys()):
        if key in added_keys or key in PRODUCT_NESTED_FIELDS:
            continue
        append_embedding_line(lines, f"product.{key}", product.get(key))

    microsite = product.get("microsite") or {}
    if microsite:
        lines.append("section: microsite supplier")
        for key in sorted(microsite.keys()):
            append_embedding_line(lines, f"microsite.{key}", microsite.get(key))

    taxonomy = product.get("taxonomy") or {}
    if taxonomy:
        lines.append("section: product taxonomy")
        for key in (
            "taxonomy_path",
            "taxonomy_cluster",
            "taxonomy_category",
            "taxonomy_class",
            "taxonomy_subclass",
            "taxonomy_cluster_slug",
            "taxonomy_category_slug",
            "taxonomy_class_slug",
            "taxonomy_subclass_slug",
            "taxonomy_cluster_id",
            "taxonomy_category_id",
            "taxonomy_class_id",
            "taxonomy_subclass_id",
            "taxonomy_ids",
        ):
            append_embedding_line(lines, key, taxonomy.get(key))

    facets = product.get("facets") or []
    if facets:
        lines.append("section: product facets")
        for facet in facets:
            facet_key = format_embedding_value(facet.get("key")) or "unknown"
            label = format_embedding_value(facet.get("label")) or facet_key
            value = format_embedding_value(facet.get("value"))
            normalized = format_embedding_value(facet.get("normalizedValue"))
            unit = format_embedding_value(facet.get("unit"))
            value_type = format_embedding_value(facet.get("valueType"))

            facet_parts = [f"label={label}"]
            if value is not None:
                facet_parts.append(f"value={value}")
            if normalized is not None:
                facet_parts.append(f"normalized_value={normalized}")
            if unit is not None:
                facet_parts.append(f"unit={unit}")
            if value_type is not None:
                facet_parts.append(f"value_type={value_type}")

            lines.append(f"facet.{facet_key}: {'; '.join(facet_parts)}")

    return "\n".join(lines)


def sanitize_metadata(product):
    metadata = {}
    # Core product fields
    for key in ("name", "slug", "modelType", "status", "sku", "currency",
                "promoMessage", "isFeatured", "primaryImageUrl", "micrositeId",
                "subcategoryId"):
        val = product.get(key)
        if val is not None:
            metadata[key] = val

    if product.get("basePrice") is not None:
        metadata["basePrice"] = float(product["basePrice"])
    if product.get("stockQuantity") is not None:
        metadata["stockQuantity"] = int(product["stockQuantity"])
    if product.get("description"):
        metadata["description"] = product["description"][:1000]
    for ts_field in ("createdAt", "updatedAt"):
        val = product.get(ts_field)
        if isinstance(val, datetime):
            metadata[ts_field] = val.isoformat()

    # Microsite fields
    microsite = product.get("microsite", {})
    for key in ("title", "slug", "type", "status", "customDomain", "label", "tagline"):
        val = microsite.get(key)
        if val is not None:
            metadata[f"microsite_{key}"] = val
    if microsite.get("description"):
        metadata["microsite_description"] = microsite["description"][:500]
    if microsite.get("logo"):
        metadata["microsite_logo"] = microsite["logo"]
    if microsite.get("published") is not None:
        metadata["microsite_published"] = microsite["published"]

    # Taxonomy fields (flat for facet filtering)
    taxonomy = product.get("taxonomy", {})
    for key in ("taxonomy_cluster", "taxonomy_category", "taxonomy_class", "taxonomy_subclass",
                "taxonomy_cluster_slug", "taxonomy_category_slug", "taxonomy_class_slug",
                "taxonomy_subclass_slug", "taxonomy_cluster_id", "taxonomy_category_id",
                "taxonomy_class_id", "taxonomy_subclass_id", "taxonomy_path"):
        val = taxonomy.get(key)
        if val:
            metadata[key] = val

    # taxonomy_ids as list for $in filtering
    taxonomy_ids = taxonomy.get("taxonomy_ids", [])
    if taxonomy_ids:
        metadata["taxonomy_ids"] = taxonomy_ids

    # Facets as flat metadata: facet_<key> = value
    for facet in product.get("facets", []):
        facet_key = f"facet_{facet['key']}"
        value = facet.get("value", "")
        # Try to store numbers as numbers for range filtering
        if facet.get("valueType") == "number":
            try:
                value = float(value)
            except (ValueError, TypeError):
                pass
        metadata[facet_key] = value

    return metadata


def build_vector_record(product):
    text = build_embedding_text(product)
    if not text.strip():
        return None
    return {
        "_id": product["id"],
        "chunk_text": text,
        **sanitize_metadata(product),
    }


# --- Initial Full Index ---
def index_all_products(pinecone_index):
    print("Fetching all products with facets from PostgreSQL...")
    products = fetch_all_products_with_facets()
    print(f"Found {len(products)} products")

    if not products:
        print("No products to index")
        return

    batch = []
    for product in products:
        record = build_vector_record(product)
        if record:
            batch.append(record)

    # Upsert in batches that fit llama-text-embed-v2 hosted embedding limits.
    for i in range(0, len(batch), PRODUCT_BATCH_SIZE):
        chunk = batch[i:i + PRODUCT_BATCH_SIZE]
        upsert_integrated_records(
            pinecone_index,
            chunk,
            f"products batch {i // PRODUCT_BATCH_SIZE + 1}",
        )
        print(f"Indexed {len(chunk)} products (batch {i // PRODUCT_BATCH_SIZE + 1})")

    print(f"Initial indexing complete: {len(batch)} products indexed")


# --- Handle Trigger Events ---
def handle_insert_or_update(pinecone_index, product_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        product = fetch_product_with_facets(cursor, product_id)
        if not product:
            print(f"Product {product_id} not found in DB, skipping")
            return
        record = build_vector_record(product)
        if record:
            upsert_integrated_records(pinecone_index, [record], f"product {product_id}")
            print(f"Upserted product {product_id} to Pinecone")
        else:
            print(f"Could not generate embedding for product {product_id}")
    finally:
        conn.close()


def handle_delete(pinecone_index, product_id):
    pinecone_index.delete(ids=[product_id], namespace=DEFAULT_NAMESPACE)
    print(f"Deleted product {product_id} from Pinecone")


def process_change(pinecone_index, payload):
    operation, product_id = payload.split(":", 1)
    if operation == "INSERT":
        print(f"INSERT detected: product {product_id}")
        handle_insert_or_update(pinecone_index, product_id)
    elif operation == "UPDATE":
        print(f"UPDATE detected: product {product_id}")
        handle_insert_or_update(pinecone_index, product_id)
    elif operation == "DELETE":
        print(f"DELETE detected: product {product_id}")
        handle_delete(pinecone_index, product_id)
    else:
        print(f"Unknown operation: {operation}")


# ============================================================
# NEWS TRIGGER
# ============================================================

def fetch_news_with_microsite(cursor, news_id):
    cursor.execute('SELECT * FROM "News" WHERE id = %s;', (news_id,))
    news = cursor.fetchone()
    if not news:
        return None
    news = dict(news)
    news["microsite"] = fetch_microsite(cursor, news.get("micrositeId"))
    return news


def fetch_all_news_with_microsites():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT * FROM "News";')
        all_news = [dict(row) for row in cursor.fetchall()]

        # Pre-fetch all microsites
        cursor.execute('SELECT * FROM "Microsite";')
        all_microsites = {row["id"]: dict(row) for row in cursor.fetchall()}

        for news in all_news:
            news["microsite"] = all_microsites.get(news.get("micrositeId"), {})

        return all_news
    finally:
        conn.close()


def build_news_embedding_text(news):
    parts = []
    if news.get("title"):
        parts.append(news["title"])
    if news.get("summary"):
        parts.append(news["summary"])
    if news.get("content"):
        parts.append(news["content"][:4000])
    if news.get("author"):
        parts.append(f"Author: {news['author']}")
    if news.get("short_description"):
        parts.append(news["short_description"])

    # Include microsite info
    microsite = news.get("microsite", {})
    if microsite.get("title"):
        parts.append(f"Supplier: {microsite['title']}")
    if microsite.get("description"):
        parts.append(microsite["description"])

    return " | ".join(parts)


def sanitize_news_metadata(news):
    metadata = {}

    # Core news fields
    for key in ("title", "slug", "author", "type", "source_url",
                "coverImage", "videoUrl", "thumbnail", "image_url",
                "categoryId", "isFeatured", "isPublished",
                "micrositeId", "tagline", "categoryImage",
                "featuredStoryHeroImage", "featuredStoryImage"):
        val = news.get(key)
        if val is not None:
            metadata[key] = val

    if news.get("summary"):
        metadata["summary"] = news["summary"][:1000]
    if news.get("short_description"):
        metadata["short_description"] = news["short_description"][:500]
    if news.get("content"):
        metadata["content"] = news["content"][:1000]

    # Timestamp fields
    for ts_field in ("publishDate", "landingPublishAt", "createdAt", "updatedAt"):
        val = news.get(ts_field)
        if isinstance(val, datetime):
            metadata[ts_field] = val.isoformat()

    # List fields
    if news.get("categoryIds"):
        metadata["categoryIds"] = news["categoryIds"]
    if news.get("placements"):
        metadata["placements"] = news["placements"]

    # Microsite fields
    microsite = news.get("microsite", {})
    for key in ("title", "slug", "type", "status", "customDomain", "label", "tagline"):
        val = microsite.get(key)
        if val is not None:
            metadata[f"microsite_{key}"] = val
    if microsite.get("description"):
        metadata["microsite_description"] = microsite["description"][:500]
    if microsite.get("logo"):
        metadata["microsite_logo"] = microsite["logo"]
    if microsite.get("published") is not None:
        metadata["microsite_published"] = microsite["published"]

    return metadata


def build_news_vector_record(news):
    text = build_news_embedding_text(news)
    embedding = generate_embedding(text)
    if not embedding:
        return None
    return {
        "id": news["id"],
        "values": embedding,
        "metadata": sanitize_news_metadata(news),
    }


def index_all_news(news_pinecone_index):
    print("Fetching all news with microsites from PostgreSQL...")
    all_news = fetch_all_news_with_microsites()
    print(f"Found {len(all_news)} news articles")

    if not all_news:
        print("No news to index")
        return

    batch = []
    for news in all_news:
        record = build_news_vector_record(news)
        if record:
            batch.append(record)

    for i in range(0, len(batch), 100):
        chunk = batch[i:i + 100]
        news_pinecone_index.upsert(vectors=chunk)
        print(f"Indexed {len(chunk)} news articles (batch {i // 100 + 1})")

    print(f"News indexing complete: {len(batch)} articles indexed")


def handle_news_insert_or_update(news_pinecone_index, news_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        news = fetch_news_with_microsite(cursor, news_id)
        if not news:
            print(f"News {news_id} not found in DB, skipping")
            return
        record = build_news_vector_record(news)
        if record:
            news_pinecone_index.upsert(vectors=[record])
            print(f"Upserted news {news_id} to Pinecone")
        else:
            print(f"Could not generate embedding for news {news_id}")
    finally:
        conn.close()


def handle_news_delete(news_pinecone_index, news_id):
    news_pinecone_index.delete(ids=[news_id])
    print(f"Deleted news {news_id} from Pinecone")


def process_news_change(news_pinecone_index, payload):
    operation, news_id = payload.split(":", 1)
    if operation == "INSERT":
        print(f"NEWS INSERT detected: {news_id}")
        handle_news_insert_or_update(news_pinecone_index, news_id)
    elif operation == "UPDATE":
        print(f"NEWS UPDATE detected: {news_id}")
        handle_news_insert_or_update(news_pinecone_index, news_id)
    elif operation == "DELETE":
        print(f"NEWS DELETE detected: {news_id}")
        handle_news_delete(news_pinecone_index, news_id)
    else:
        print(f"Unknown news operation: {operation}")


# ============================================================
# JOB TRIGGER
# ============================================================

def fetch_job_with_microsite(cursor, job_id):
    cursor.execute('SELECT * FROM "JobPost" WHERE id = %s;', (job_id,))
    job = cursor.fetchone()
    if not job:
        return None
    job = dict(job)
    job["microsite"] = fetch_microsite(cursor, job.get("siteId"))
    return job


def fetch_all_jobs_with_microsites():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute('SELECT * FROM "JobPost";')
        all_jobs = [dict(row) for row in cursor.fetchall()]

        # Pre-fetch all microsites
        cursor.execute('SELECT * FROM "Microsite";')
        all_microsites = {row["id"]: dict(row) for row in cursor.fetchall()}

        for job in all_jobs:
            job["microsite"] = all_microsites.get(job.get("siteId"), {})

        return all_jobs
    finally:
        conn.close()


JOB_TEXT_PRIORITY_FIELDS = (
    "id", "jobTitle", "jobId", "employerName", "description", "location",
    "city", "state", "country", "stateId", "countryId", "salaryRange",
    "keyResponsibilities", "qualifications", "perksBenefits", "educationLevel",
    "certificationLevel", "interviewFormat", "requiredExperience",
    "preferredExperience", "categoryId", "siteId", "active", "isScrapped",
    "hideEmployer", "applicationDeadline", "createdAt", "updatedAt",
)
JOB_NESTED_FIELDS = {"microsite"}


def build_job_embedding_text(job):
    lines = [
        "record_type: job",
        "content_format: structured key value text for semantic job search",
    ]

    added_keys = set()
    for key in JOB_TEXT_PRIORITY_FIELDS:
        if key in job and key not in JOB_NESTED_FIELDS:
            append_embedding_line(lines, f"job.{key}", job.get(key))
            added_keys.add(key)

    for key in sorted(job.keys()):
        if key in added_keys or key in JOB_NESTED_FIELDS:
            continue
        append_embedding_line(lines, f"job.{key}", job.get(key))

    microsite = job.get("microsite") or {}
    if microsite:
        lines.append("section: microsite employer")
        for key in sorted(microsite.keys()):
            append_embedding_line(lines, f"microsite.{key}", microsite.get(key))

    return "\n".join(lines)


def sanitize_job_metadata(job):
    metadata = {}

    # Core job fields
    for key in ("jobTitle", "jobId", "employerName", "location", "salaryRange",
                "educationLevel", "certificationLevel", "interviewFormat",
                "siteId", "active", "isScrapped", "hideEmployer", "image",
                "requiredExperience", "city", "state", "country", "stateId",
                "countryId"):
        val = job.get(key)
        if val is not None:
            metadata[key] = val

    if job.get("description"):
        metadata["description"] = job["description"][:1000]
    if job.get("keyResponsibilities"):
        metadata["keyResponsibilities"] = job["keyResponsibilities"][:1000]
    if job.get("qualifications"):
        metadata["qualifications"] = job["qualifications"][:1000]
    if job.get("perksBenefits"):
        metadata["perksBenefits"] = job["perksBenefits"][:500]
    if job.get("preferredExperience") is not None:
        metadata["preferredExperience"] = int(job["preferredExperience"])
    if job.get("categoryId") is not None:
        metadata["categoryId"] = job["categoryId"]

    # Timestamp fields
    for ts_field in ("applicationDeadline", "createdAt", "updatedAt"):
        val = job.get(ts_field)
        if isinstance(val, datetime):
            metadata[ts_field] = val.isoformat()

    # Microsite fields
    microsite = job.get("microsite", {})
    for key in ("title", "slug", "type", "status", "customDomain", "label", "tagline"):
        val = microsite.get(key)
        if val is not None:
            metadata[f"microsite_{key}"] = val
    if microsite.get("description"):
        metadata["microsite_description"] = microsite["description"][:500]
    if microsite.get("logo"):
        metadata["microsite_logo"] = microsite["logo"]
    if microsite.get("published") is not None:
        metadata["microsite_published"] = microsite["published"]

    return metadata


def build_job_vector_record(job):
    text = build_job_embedding_text(job)
    if not text.strip():
        return None
    return {
        "_id": job["id"],
        "chunk_text": text,
        **sanitize_job_metadata(job),
    }


def index_all_jobs(job_pinecone_index):
    print("Fetching all jobs with microsites from PostgreSQL...")
    all_jobs = fetch_all_jobs_with_microsites()
    print(f"Found {len(all_jobs)} job posts")

    if not all_jobs:
        print("No jobs to index")
        return

    batch = []
    for job in all_jobs:
        record = build_job_vector_record(job)
        if record:
            batch.append(record)

    for i in range(0, len(batch), JOB_BATCH_SIZE):
        chunk = batch[i:i + JOB_BATCH_SIZE]
        upsert_integrated_records(
            job_pinecone_index,
            chunk,
            f"jobs batch {i // JOB_BATCH_SIZE + 1}",
        )
        print(f"Indexed {len(chunk)} jobs (batch {i // JOB_BATCH_SIZE + 1})")

    print(f"Job indexing complete: {len(batch)} jobs indexed")


def handle_job_insert_or_update(job_pinecone_index, job_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        job = fetch_job_with_microsite(cursor, job_id)
        if not job:
            print(f"Job {job_id} not found in DB, skipping")
            return
        record = build_job_vector_record(job)
        if record:
            upsert_integrated_records(job_pinecone_index, [record], f"job {job_id}")
            print(f"Upserted job {job_id} to Pinecone")
        else:
            print(f"Could not generate embedding for job {job_id}")
    finally:
        conn.close()


def handle_job_delete(job_pinecone_index, job_id):
    job_pinecone_index.delete(ids=[job_id], namespace=DEFAULT_NAMESPACE)
    print(f"Deleted job {job_id} from Pinecone")


def process_job_change(job_pinecone_index, payload):
    operation, job_id = payload.split(":", 1)
    if operation == "INSERT":
        print(f"JOB INSERT detected: {job_id}")
        handle_job_insert_or_update(job_pinecone_index, job_id)
    elif operation == "UPDATE":
        print(f"JOB UPDATE detected: {job_id}")
        handle_job_insert_or_update(job_pinecone_index, job_id)
    elif operation == "DELETE":
        print(f"JOB DELETE detected: {job_id}")
        handle_job_delete(job_pinecone_index, job_id)
    else:
        print(f"Unknown job operation: {operation}")


# --- Main ---
if __name__ == "__main__":
    # 1. Connect to Pinecone
    pinecone_index = init_pinecone()
    news_pinecone_index = init_news_pinecone()
    job_pinecone_index = init_job_pinecone()

    # 2. Initial full index of all products
    index_all_products(pinecone_index)

    # 3. Initial full index of all news
    index_all_news(news_pinecone_index)

    # 4. Initial full index of all jobs
    index_all_jobs(job_pinecone_index)

    # 5. Listen for PostgreSQL trigger notifications
    print("\nStarting trigger listener...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN product_changes;")
    cur.execute("LISTEN news_changes;")
    cur.execute("LISTEN job_changes;")
    print("Listening for product_changes, news_changes, and job_changes notifications...\n")

    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            print("Waiting for new notifications...")
        else:
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop()
                print(f"Notification received on '{notify.channel}': {notify.payload}")
                if notify.channel == "product_changes":
                    process_change(pinecone_index, notify.payload)
                elif notify.channel == "news_changes":
                    process_news_change(news_pinecone_index, notify.payload)
                elif notify.channel == "job_changes":
                    process_job_change(job_pinecone_index, notify.payload)
