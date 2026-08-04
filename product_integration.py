import argparse
import html
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

from env_config import postgres_config


load_dotenv()


DEFAULT_WORKBOOK_CANDIDATES = ("Product_Migration.xlsx", "product_microsite_id.xlsx")
DEFAULT_SCRAPE_ENDPOINT = "https://news.mininglifeserver.com/scrape-products"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PRODUCT_INTEGRATION_TIMEOUT_SECONDS", "180"))
REQUEST_RETRIES = int(os.getenv("PRODUCT_INTEGRATION_RETRIES", "2"))
REQUEST_DELAY_SECONDS = float(os.getenv("PRODUCT_INTEGRATION_DELAY_SECONDS", "1"))

CANONICAL_OPTION_FACETS = {
    "condition": {
        "key": "new-remanufactured-refurbished",
        "options": ["New", "Refurbished"],
    },
    "oemAftermarket": {
        "key": "oem-aftermarket-third-party",
        "options": ["OEM Original", "Aftermarket"],
    },
    "serviceRegion": {
        "key": "service-support-region",
        "options": ["Global", "American", "EMEA", "Africa", "Asia-Pacific"],
    },
}


def now() -> datetime:
    return datetime.utcnow()


def default_workbook_path() -> str:
    configured = os.getenv("PRODUCT_INTEGRATION_WORKBOOK")
    if configured:
        return configured
    for candidate in DEFAULT_WORKBOOK_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return DEFAULT_WORKBOOK_CANDIDATES[0]


def new_id() -> str:
    return str(uuid.uuid4())


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def to_slugish(value: Any) -> str:
    text = compact_text(value).lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def unique_slug(cursor, microsite_id: str, name: str) -> str:
    base = to_slugish(name) or f"product-{uuid.uuid4().hex[:8]}"
    slug = base
    suffix = 2
    while True:
        cursor.execute(
            'SELECT 1 FROM "Product" WHERE "micrositeId" = %s AND slug = %s LIMIT 1;',
            (microsite_id, slug),
        )
        if cursor.fetchone() is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def strip_html(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return compact_text(text)


def truncate_at_word(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    sliced = value[:max_length].strip()
    last_space = sliced.rfind(" ")
    if last_space > 80:
        sliced = sliced[:last_space]
    return f"{sliced.strip()}..."


def normalize_short_description(value: Any) -> str:
    text = strip_html(value)
    return truncate_at_word(text, 500) if text else ""


def derive_short_description(description: Any) -> str:
    text = strip_html(description)
    if not text:
        return ""
    match = re.match(r"^.{80,260}?[.!?](?:\s|$)", text)
    return truncate_at_word((match.group(0) if match else text).strip(), 260)


def normalize_url(value: Any) -> str | None:
    if not value:
        return None
    normalized = html.unescape(str(value)).strip().strip("\"' \t\r\n").rstrip("\"'")
    return normalized or None


def collect_urls(value: Any) -> list[str]:
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in values:
        normalized = normalize_url(item)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def normalize_images(product: dict[str, Any]) -> list[str]:
    candidates: list[Any] = []
    candidates.extend(collect_urls(product.get("image_url")))
    candidates.extend(collect_urls(product.get("image_urls")))
    candidates.extend(product.get("gallery_images") or [])
    candidates.extend(product.get("images") or [])
    out: list[str] = []
    for item in candidates:
        normalized = normalize_url(item)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def normalize_videos(product: dict[str, Any]) -> list[str]:
    out = collect_urls(product.get("video_url"))
    for item in collect_urls(product.get("video_urls")):
        if item not in out:
            out.append(item)
    return out


def normalize_documents(product: dict[str, Any]) -> list[str]:
    out = collect_urls(product.get("document_urls"))
    for item in collect_urls(product.get("doc_url")):
        if item not in out:
            out.append(item)
    return out


def normalize_taxonomy_node(value: Any) -> dict[str, str | None] | None:
    if not value:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return {"name": trimmed} if trimmed else None
    if not isinstance(value, dict):
        return None
    node = {
        "id": compact_text(value.get("id")) or None,
        "name": compact_text(value.get("name")) or None,
        "slug": compact_text(value.get("slug")) or None,
    }
    return node if any(node.values()) else None


def taxonomy_label(value: Any) -> str | None:
    node = normalize_taxonomy_node(value)
    return node.get("name") if node else None


def taxonomy_id(value: Any) -> str | None:
    node = normalize_taxonomy_node(value)
    return node.get("id") if node else None


def normalize_facets(product: dict[str, Any]) -> list[dict[str, Any]]:
    facets = product.get("facets")
    if not isinstance(facets, list):
        return []
    out: list[dict[str, Any]] = []
    for facet in facets:
        if not isinstance(facet, dict):
            continue
        value = facet.get("value")
        if isinstance(value, str):
            value = value.strip() or None
        out.append(
            {
                "facet_id": compact_text(facet.get("facet_id")) or None,
                "value": value,
                "value_type": compact_text(facet.get("value_type")) or None,
                "key": compact_text(facet.get("key")) or None,
                "label": compact_text(facet.get("label")) or None,
                "sort_order": facet.get("sort_order")
                if isinstance(facet.get("sort_order"), (int, float))
                else None,
            }
        )
    return out


def normalize_facet_payload_key(value: Any) -> str:
    return to_slugish(value)


def build_facet_values(facets: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for facet in facets:
        key = normalize_facet_payload_key(facet.get("key") or facet.get("label"))
        if not key:
            continue
        value = facet.get("value")
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        normalized = value.strip() if isinstance(value, str) else value
        existing = out.get(key)
        if existing is None:
            out[key] = normalized
            continue
        values = existing if isinstance(existing, list) else [existing]
        if str(normalized) not in [str(item) for item in values]:
            values.append(normalized)
        out[key] = values
    return out


def normalize_facet_text(value: Any) -> str:
    text = re.sub(r"[_-]+", " ", str(value or ""))
    return compact_text(text).lower()


def facet_record_has_value(record: dict[str, Any], key: str) -> bool:
    value = record.get(key)
    if isinstance(value, list):
        return any(compact_text(item) for item in value)
    return value is not None and compact_text(value) != ""


def merge_facet_value_records(*records: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for record in records:
        for key, value in (record or {}).items():
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            existing = out.get(key)
            if existing is None:
                out[key] = value
                continue
            values = existing if isinstance(existing, list) else [existing]
            next_values = value if isinstance(value, list) else [value]
            for item in next_values:
                text = compact_text(item)
                if text and text not in [compact_text(entry) for entry in values]:
                    values.append(text)
            out[key] = values[0] if len(values) == 1 else values
    return out


def collect_facet_inference_text(product: dict[str, Any]) -> str:
    chunks: list[str] = [
        product.get("title") or "",
        product.get("description") or "",
        product.get("category") or "",
        product.get("subcategory") or "",
        product.get("productUrl") or "",
    ]
    attributes = product.get("attributes") or {}
    chunks.extend(str(item) for pair in attributes.items() for item in pair if item)
    for facet in product.get("facets") or []:
        chunks.extend(
            [
                facet.get("key") or "",
                facet.get("label") or "",
                "" if facet.get("value") is None else str(facet.get("value")),
            ]
        )
    return normalize_facet_text(" | ".join(chunks))


def infer_canonical_facet_values(product: dict[str, Any]) -> dict[str, Any]:
    text = collect_facet_inference_text(product)
    inferred: dict[str, Any] = {}

    if re.search(r"\b(refurbished|remanufactured|reman|reconditioned|rebuilt|used)\b", text):
        inferred[CANONICAL_OPTION_FACETS["condition"]["key"]] = "Refurbished"
    elif re.search(r"\b(new|newly manufactured|factory new|brand new)\b", text):
        inferred[CANONICAL_OPTION_FACETS["condition"]["key"]] = "New"

    if re.search(r"\b(aftermarket|third party|third-party|non oem|non-oem)\b", text):
        inferred[CANONICAL_OPTION_FACETS["oemAftermarket"]["key"]] = "Aftermarket"
    elif re.search(r"\b(oem|original equipment|genuine|factory original|oem original)\b", text):
        inferred[CANONICAL_OPTION_FACETS["oemAftermarket"]["key"]] = "OEM Original"

    if re.search(r"\b(global|worldwide|international)\b", text):
        inferred[CANONICAL_OPTION_FACETS["serviceRegion"]["key"]] = "Global"
    elif re.search(r"\b(usa|u\.s\.a\.|united states|north america|america|american|canada|mexico)\b", text):
        inferred[CANONICAL_OPTION_FACETS["serviceRegion"]["key"]] = "American"
    elif re.search(r"\b(emea|europe|middle east|germany|sweden|africa)\b", text):
        inferred[CANONICAL_OPTION_FACETS["serviceRegion"]["key"]] = "Africa" if "africa" in text else "EMEA"
    elif re.search(r"\b(asia pacific|asia-pacific|apac|australia|china|india|japan)\b", text):
        inferred[CANONICAL_OPTION_FACETS["serviceRegion"]["key"]] = "Asia-Pacific"

    return inferred


def normalize_canonical_facet_options(values: dict[str, Any]) -> dict[str, Any]:
    out = dict(values)
    for group in CANONICAL_OPTION_FACETS.values():
        key = group["key"]
        current = out.get(key)
        if current is None:
            continue
        selected: list[str] = []
        for value in current if isinstance(current, list) else [current]:
            normalized = normalize_facet_text(value)
            match = next(
                (option for option in group["options"] if normalize_facet_text(option) == normalized),
                compact_text(value),
            )
            if match and match not in selected:
                selected.append(match)
        if selected:
            out[key] = selected[0] if len(selected) == 1 else selected
        else:
            out.pop(key, None)
    return out


def merge_with_inferred_canonical_facets(product: dict[str, Any]) -> dict[str, Any]:
    existing = normalize_canonical_facet_options(product.get("facetValues") or {})
    inferred = infer_canonical_facet_values(product)
    missing = {
        key: value
        for key, value in inferred.items()
        if not facet_record_has_value(existing, key)
    }
    return merge_facet_value_records(existing, missing)


def to_attribute_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def is_noise_attribute(key: str, value: Any) -> bool:
    normalized_key = compact_text(key)
    normalized_value = compact_text(value)
    if not normalized_key or not normalized_value:
        return True
    if len(normalized_key) > 60 or len(normalized_value) > 160:
        return True
    if re.search(r"[.!?]$", normalized_key):
        return True
    if len(normalized_key.split()) > 7:
        return True
    return bool(
        re.search(
            r"^(the|with|optional|fully|industry|hydraulic|integrated|need|spin|spring|storage|offering|for handling)\b",
            normalized_key,
            flags=re.I,
        )
    )


def clean_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in attributes.items():
        clean_key = compact_text(key)
        clean_value = value.strip() if isinstance(value, str) else value
        if not is_noise_attribute(clean_key, clean_value):
            out[clean_key] = clean_value
    return out


def extract_specification_attributes(description: Any) -> dict[str, str]:
    if not description:
        return {}
    lines = [line.strip() for line in str(description).splitlines() if line.strip()]
    try:
        spec_index = next(i for i, line in enumerate(lines) if re.match(r"^specifications$", line, re.I))
    except StopIteration:
        return {}
    end_index = next(
        (
            i
            for i, line in enumerate(lines)
            if i > spec_index and re.match(r"^(features|key features|productivity|gallery|brochures)$", line, re.I)
        ),
        len(lines),
    )
    spec_lines = lines[spec_index + 1 : end_index]
    attributes: dict[str, str] = {}
    for index in range(0, max(0, len(spec_lines) - 1)):
        label = spec_lines[index]
        value = spec_lines[index + 1]
        if not label or not value:
            continue
        if re.match(r"^[A-Z0-9-]{2,}$", label, re.I) and index == 0:
            continue
        if len(label) > 48 or len(value) > 120:
            continue
        if re.match(
            r"^(rated power|operating weight|tipping load|breakout force|net power|gross power|bucket capacity|payload|rated payload)$",
            label,
            re.I,
        ):
            attributes[label] = value
    return attributes


def normalize_scrape_response(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("products"), list):
        return [item for item in payload["products"] if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("product"), dict):
        return [payload["product"]]
    if isinstance(payload, dict) and ("title" in payload or "product_url" in payload):
        return [payload]
    return []


def normalize_product(raw: dict[str, Any], requested_url: str) -> dict[str, Any]:
    description = (raw.get("description") or "").strip()
    description_attributes = extract_specification_attributes(description)
    cleaned_attributes = clean_attributes(to_attribute_record(raw.get("attributes")))
    attributes = description_attributes or cleaned_attributes
    image_urls = normalize_images(raw)
    video_urls = normalize_videos(raw)
    document_urls = normalize_documents(raw)
    facets = normalize_facets(raw)
    product_url = normalize_url(raw.get("product_url")) or normalize_url(requested_url)
    raw_super_category = raw.get("cluster") or raw.get("super_category")
    raw_class = raw.get("class") or raw.get("class_name")
    raw_sub_class = raw.get("sub_class") or raw.get("sub_class_name") or raw.get("subcategory")

    product = {
        "title": compact_text(raw.get("title")) or "Untitled Product",
        "shortDescription": normalize_short_description(
            raw.get("shortDescription") or raw.get("short_description") or raw.get("summary")
        )
        or derive_short_description(description),
        "description": description,
        "imageUrl": image_urls[0] if image_urls else None,
        "imageUrls": image_urls,
        "videoUrls": video_urls,
        "docUrl": document_urls[0] if document_urls else None,
        "documentUrls": document_urls,
        "category": taxonomy_label(raw.get("category")),
        "subcategory": taxonomy_label(raw_sub_class),
        "superCategoryId": taxonomy_id(raw_super_category),
        "taxonomyCategoryId": taxonomy_id(raw.get("category")),
        "taxonomyClassId": taxonomy_id(raw_class),
        "taxonomySubClassId": taxonomy_id(raw_sub_class),
        "sourceTaxonomy": {
            "superCategory": normalize_taxonomy_node(raw_super_category),
            "category": normalize_taxonomy_node(raw.get("category")),
            "className": normalize_taxonomy_node(raw_class),
            "subClass": normalize_taxonomy_node(raw_sub_class),
        },
        "facets": facets,
        "facetValues": build_facet_values(facets),
        "attributes": attributes,
        "productUrl": product_url,
    }
    product["facetValues"] = merge_with_inferred_canonical_facets(product)
    return product


def build_specifications(product: dict[str, Any]) -> dict[str, Any] | None:
    attributes = {
        key: value
        for key, value in (product.get("attributes") or {}).items()
        if value is not None and compact_text(value)
    }
    merged_images = product.get("imageUrls") or []
    facet_values = product.get("facetValues") or {}
    payload: dict[str, Any] = {}

    if attributes:
        payload["attributes"] = attributes
    if product.get("category"):
        payload["sourceCategory"] = product["category"]
    if product.get("subcategory"):
        payload["sourceSubcategory"] = product["subcategory"]
    if product.get("productUrl"):
        payload["productUrl"] = product["productUrl"]
        payload["sourceUrl"] = product["productUrl"]
    if product.get("sourceUrlFromWorkbook"):
        payload["workbookSourceUrl"] = product["sourceUrlFromWorkbook"]
    if product.get("docUrl"):
        payload["docUrl"] = product["docUrl"]
        payload["documentationUrl"] = product["docUrl"]
    if product.get("documentUrls"):
        payload["documents"] = product["documentUrls"]
        payload["documentUrls"] = product["documentUrls"]
    if product.get("videoUrls"):
        payload["videoUrls"] = product["videoUrls"]
    if merged_images:
        payload["sourceImageUrls"] = merged_images
    if any((product.get("sourceTaxonomy") or {}).values()):
        payload["sourceTaxonomy"] = product["sourceTaxonomy"]
    if product.get("facets"):
        payload["sourceFacets"] = product["facets"]
    if facet_values:
        payload["sourceFacetValues"] = facet_values

    return payload or None


def parse_cell_ref(cell_ref: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if not match:
        return 0, 0
    letters, row = match.groups()
    col = 0
    for letter in letters:
        col = col * 26 + (ord(letter) - ord("A") + 1)
    return int(row), col


def read_workbook_rows(path: str) -> list[dict[str, str]]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", ns):
                shared.append("".join(node.text or "" for node in item.findall(".//a:t", ns)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheet = workbook.find("a:sheets/a:sheet", ns)
        if sheet is None:
            raise RuntimeError(f"No sheets found in {path}")
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        sheet_path = "xl/" + relmap[rel_id].lstrip("/")
        root = ET.fromstring(archive.read(sheet_path))

        rows: list[list[str]] = []
        for row in root.findall("a:sheetData/a:row", ns):
            values_by_col: dict[int, str] = {}
            for cell in row.findall("a:c", ns):
                _, col = parse_cell_ref(cell.attrib.get("r", ""))
                value_node = cell.find("a:v", ns)
                value = "" if value_node is None else value_node.text or ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
                values_by_col[col] = compact_text(value)
            if values_by_col:
                max_col = max(values_by_col)
                rows.append([values_by_col.get(index, "") for index in range(1, max_col + 1)])

    if not rows:
        return []

    headers = [to_slugish(header).replace("-", "_") for header in rows[0]]
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        record = {
            headers[index]: row[index] if index < len(row) else ""
            for index in range(len(headers))
        }
        if any(record.values()):
            out.append(record)
    return out


def scrape_product(session: requests.Session, endpoint: str, product_url: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            response = session.post(
                endpoint,
                json={"product_url": product_url},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt >= REQUEST_RETRIES:
                break
            sleep_for = REQUEST_DELAY_SECONDS * (attempt + 1)
            print(f"Scrape failed for {product_url}; retrying in {sleep_for:.1f}s: {exc}", flush=True)
            time.sleep(sleep_for)
    raise RuntimeError(f"Scrape failed for {product_url}: {last_error}")


def fetch_category_ids(cursor) -> set[str]:
    cursor.execute('SELECT id FROM "ProductCategory";')
    return {row["id"] for row in cursor.fetchall()}


def fetch_facet_definitions(cursor) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cursor.execute('SELECT id, key, label, slug, "valueType" FROM "ProductFacetDefinition";')
    by_id: dict[str, dict[str, Any]] = {}
    by_key: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        item = dict(row)
        by_id[item["id"]] = item
        by_key[item["key"]] = item
    return by_id, by_key


def existing_product_id(cursor, microsite_id: str, product_url: str | None) -> str | None:
    if not product_url:
        return None
    cursor.execute(
        """
        SELECT id
        FROM "Product"
        WHERE "micrositeId" = %s
          AND (specifications->>'productUrl' = %s OR specifications->>'sourceUrl' = %s)
        LIMIT 1;
        """,
        (microsite_id, product_url, product_url),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def existing_product_id_by_source_url(cursor, product_url: str | None) -> str | None:
    if not product_url:
        return None
    cursor.execute(
        """
        SELECT id
        FROM "Product"
        WHERE specifications->>'sourceUrl' = %s
        LIMIT 1;
        """,
        (product_url,),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def select_subcategory_id(product: dict[str, Any], category_ids: set[str]) -> str | None:
    for key in ("taxonomySubClassId", "taxonomyClassId", "taxonomyCategoryId", "superCategoryId"):
        value = product.get(key)
        if value and value in category_ids:
            return value
    return None


def insert_product(cursor, microsite_id: str, product: dict[str, Any], category_ids: set[str]) -> str:
    product_id = new_id()
    timestamp = now()
    name = product["title"]
    slug = unique_slug(cursor, microsite_id, name)
    merged_images = product.get("imageUrls") or []
    specifications = build_specifications(product)
    subcategory_id = select_subcategory_id(product, category_ids)

    cursor.execute(
        """
        INSERT INTO "Product" (
            id, "micrositeId", "subcategoryId", name, slug, description,
            "primaryImageUrl", "galleryImages", currency, "stockQuantity",
            status, "promoMessage", "isFeatured", "createdAt", "updatedAt",
            "shortDescription", specifications
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s::"ProductStatus", %s, %s, %s, %s,
            %s, %s
        );
        """,
        (
            product_id,
            microsite_id,
            subcategory_id,
            name,
            slug,
            product.get("description") or None,
            (merged_images[0] if merged_images else product.get("imageUrl")),
            merged_images[1:],
            "USD",
            0,
            "PUBLISHED",
            "NULL",
            False,
            timestamp,
            timestamp,
            product.get("shortDescription") or derive_short_description(product.get("description")) or None,
            Json(specifications) if specifications else None,
        ),
    )
    return product_id


def values_as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def insert_facet_values(
    cursor,
    product_id: str,
    product: dict[str, Any],
    facet_by_id: dict[str, dict[str, Any]],
    facet_by_key: dict[str, dict[str, Any]],
) -> int:
    timestamp = now()
    source_facets_by_key = {
        facet["key"]: facet
        for facet in product.get("facets") or []
        if facet.get("key")
    }
    inserted = 0
    for key, raw_value in (product.get("facetValues") or {}).items():
        source_facet = source_facets_by_key.get(key, {})
        definition = None
        facet_id = source_facet.get("facet_id")
        if facet_id:
            definition = facet_by_id.get(facet_id)
        if definition is None:
            definition = facet_by_key.get(key)
        if definition is None:
            print(f"Skipping unknown facet definition for key={key!r} on product_id={product_id}", flush=True)
            continue

        for value in values_as_list(raw_value):
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            text_value = compact_text(value)
            cursor.execute(
                """
                INSERT INTO "ProductFacetValue" (
                    id, "productId", "facetId", value, "normalizedValue",
                    "rawValue", "createdAt", "updatedAt"
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    new_id(),
                    product_id,
                    definition["id"],
                    text_value,
                    normalize_facet_text(value),
                    Json(value),
                    timestamp,
                    timestamp,
                ),
            )
            inserted += 1
    return inserted


def validate_microsite(cursor, microsite_id: str, expected_title: str | None = None) -> None:
    cursor.execute('SELECT id, title FROM "Microsite" WHERE id = %s;', (microsite_id,))
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Microsite not found: {microsite_id}")
    if expected_title and compact_text(row["title"]) != compact_text(expected_title):
        print(
            f"Workbook title {expected_title!r} does not match DB microsite title {row['title']!r} for {microsite_id}",
            flush=True,
        )


def process_rows(args) -> int:
    rows = read_workbook_rows(args.workbook)
    if not rows:
        print(f"No workbook rows found in {args.workbook}", flush=True)
        return 0

    session = requests.Session()
    conn = psycopg2.connect(**postgres_config("PRODUCT"), sslmode="require")
    conn.autocommit = False
    saved_count = 0
    skipped_count = 0
    failed_count = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            category_ids = fetch_category_ids(cursor)
            facet_by_id, facet_by_key = fetch_facet_definitions(cursor)

            for index, row in enumerate(rows, start=1):
                microsite_id = compact_text(row.get("microsite_id"))
                product_url = compact_text(row.get("product_url_mlo"))
                source_url = compact_text(row.get("product_url_source") or row.get("urlshort"))
                expected_title = compact_text(row.get("microsite_title"))

                if not microsite_id:
                    print(f"[{index}/{len(rows)}] Skipping row with empty microsite_id: {product_url or row}", flush=True)
                    skipped_count += 1
                    continue

                if not product_url:
                    print(f"[{index}/{len(rows)}] Skipping row with empty product_url_mlo: {row}", flush=True)
                    skipped_count += 1
                    continue

                try:
                    existing_source_id = existing_product_id_by_source_url(cursor, product_url)
                    if existing_source_id:
                        print(
                            f"[{index}/{len(rows)}] Skipping existing product {existing_source_id} for sourceUrl={product_url}",
                            flush=True,
                        )
                        skipped_count += 1
                        continue

                    validate_microsite(cursor, microsite_id, expected_title)
                    print(f"[{index}/{len(rows)}] Scraping {product_url}", flush=True)
                    payload = scrape_product(session, args.endpoint, product_url)
                    items = normalize_scrape_response(payload)
                    if not items:
                        raise RuntimeError("Scraper returned no product items")

                    for raw_item in items:
                        product = normalize_product(raw_item, product_url)
                        if source_url:
                            product["sourceUrlFromWorkbook"] = source_url
                        existing_id = existing_product_id(cursor, microsite_id, product.get("productUrl"))
                        if existing_id:
                            print(
                                f"  Skipping existing product {existing_id}: {product.get('title')}",
                                flush=True,
                            )
                            skipped_count += 1
                            continue

                        if args.dry_run:
                            print(f"  DRY RUN product: {product.get('title')}", flush=True)
                            saved_count += 1
                            continue

                        product_id = insert_product(cursor, microsite_id, product, category_ids)
                        facet_count = insert_facet_values(
                            cursor,
                            product_id,
                            product,
                            facet_by_id,
                            facet_by_key,
                        )
                        conn.commit()
                        saved_count += 1
                        print(
                            f"  Saved product {product_id}: {product.get('title')} ({facet_count} facets)",
                            flush=True,
                        )
                except Exception as exc:
                    conn.rollback()
                    failed_count += 1
                    print(f"  FAILED {product_url}: {exc}", flush=True)
                    if args.stop_on_error:
                        raise

                time.sleep(args.delay)
    finally:
        conn.close()

    print(
        f"Done. saved={saved_count} skipped={skipped_count} failed={failed_count}",
        flush=True,
    )
    return 1 if failed_count else 0


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape Product_Migration.xlsx products and save them to Postgres.")
    parser.add_argument("--workbook", default=default_workbook_path())
    parser.add_argument("--endpoint", default=os.getenv("PRODUCT_SCRAPE_ENDPOINT", DEFAULT_SCRAPE_ENDPOINT))
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(process_rows(parse_args()))
