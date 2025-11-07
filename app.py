import os
import json
import boto3
import botocore
import time
import logging
import requests
import re
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, request, render_template_string, session, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials

# Import our database systems
from ultra_simple_bedrock import SimpleBedrock

REGION = "us-east-1"
bucket_name = os.environ.get("BUCKET_NAME", "suryaatrial3")
# New bucket for storing conversation logs
conversation_bucket = os.environ.get("CONVERSATION_BUCKET", "promptstorage")

INFERENCE_PROFILE_ARN = os.environ.get(
    "BEDROCK_INFERENCE_PROFILE_ARN",
    "arn:aws:bedrock:us-east-1:705241975254:inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0"
)
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    config=botocore.config.Config(connect_timeout=5, read_timeout=30),
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key_change_this_in_production")

# Enable CORS for cross-origin requests
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database systems
feedback_system = SimpleBedrock("school_feedback.db")

# Production configurations
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# -----------------------
# Conversation Logging Functions
# -----------------------
def log_conversation_to_s3(query, response, query_type, user, api_key, response_time_ms, ip_address, user_agent=None, error_message=None):
    """Log conversation to S3 bucket in JSON format"""
    try:
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        conversation = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "api_key": api_key[:10] + "..." if api_key else None,  # Truncate for security
            "query": query,
            "query_type": query_type,
            "response": response,
            "response_length": len(response) if response else 0,
            "response_time_ms": response_time_ms,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": error_message is None,
            "error_message": error_message
        }
        
        # Store in S3 with date-based folder structure
        date_path = datetime.now().strftime('%Y/%m/%d')
        key = f"conversations/{date_path}/{conversation_id}.json"
        
        s3.put_object(
            Bucket=conversation_bucket,
            Key=key,
            Body=json.dumps(conversation, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Conversation logged to S3: {conversation_id}")
        
    except Exception as e:
        # Don't let logging errors break the main functionality
        logger.error(f"Failed to log conversation to S3: {str(e)}")
        pass

# -----------------------
# API Configuration
# -----------------------
# API Keys for authentication
API_KEYS = {
    "sk-test-12345": {"name": "Test User", "permissions": ["read", "write"]},
    "sk-prod-67890": {"name": "Admin User", "permissions": ["read", "write", "delete"]},
    "sk-school-api-key": {"name": "School Admin", "permissions": ["read", "write"]},
    # Add more API keys as needed
}

# External API configurations
EXTERNAL_APIS = {
    "news": {
        "base_url": "https://newsapi.org/v2/top-headlines",
        "api_key": os.environ.get("NEWS_API_KEY", "e5d7c39b653d47e585dc1232323e7d06"),  # Your News API key
        "enabled": True
    }
}

# -----------------------
# API Authentication
# -----------------------
def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('Authorization')
        if not api_key:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({"error": "API key is required", "code": "MISSING_API_KEY"}), 401
        
        # Remove 'Bearer ' prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        if api_key not in API_KEYS:
            return jsonify({"error": "Invalid API key", "code": "INVALID_API_KEY"}), 401
        
        # Add user info to request context
        request.api_user = API_KEYS[api_key]
        return f(*args, **kwargs)
    return decorated_function

# -----------------------
# Health check endpoints
# -----------------------
# Returns a simple "I'm alive" message for AWS Load Balancer to check if the app is working
@app.route("/health")
def health():
    """Basic health check for ALB"""
    return jsonify({"status": "healthy", "service": "school-chatbot"}), 200

# Another health check endpoint that just returns "pong" - like playing ping-pong to test connectivity
@app.route("/ping")
def ping():
    """Additional health check endpoint"""
    return "pong", 200

# -----------------------
# Conversation Logging Functions
# -----------------------
def log_conversation_to_s3(query, response, query_type, user_name, api_key, response_time_ms=0):
    """Log conversation data to S3 for analytics and monitoring"""
    try:
        conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        conversation_data = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user_name": user_name,
            "api_key": api_key,
            "query": query,
            "query_type": query_type,
            "response": response,
            "response_length": len(response) if response else 0,
            "response_time_ms": response_time_ms,
            "ip_address": request.remote_addr if request else "unknown",
            "user_agent": request.headers.get('User-Agent', 'unknown') if request else "unknown",
            "success": True,
            "error_message": None
        }

        # Create S3 key with date-based folder structure
        date_folder = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"conversations/{date_folder}/{conversation_id}.json"

        # Upload in background so we don't block request handling
        def _worker_put():
            try:
                s3.put_object(
                    Bucket=conversation_bucket,
                    Key=s3_key,
                    Body=json.dumps(conversation_data, indent=2),
                    ContentType='application/json'
                )
                logger.info(f"Conversation logged to S3: {s3_key}")
            except Exception as e:
                logger.error(f"Failed to log conversation to S3 (background): {e}")

        import threading
        t = threading.Thread(target=_worker_put, daemon=True)
        t.start()

    except Exception as e:
        logger.error(f"Failed to prepare background S3 logging: {e}")

def log_error_to_s3(query, error_message, query_type, user_name, api_key):
    """Log error conversations to S3"""
    try:
        conversation_id = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        error_data = {
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
            "user_name": user_name,
            "api_key": api_key,
            "query": query,
            "query_type": query_type,
            "response": None,
            "response_length": 0,
            "response_time_ms": 0,
            "ip_address": request.remote_addr if request else "unknown",
            "user_agent": request.headers.get('User-Agent', 'unknown') if request else "unknown",
            "success": False,
            "error_message": str(error_message)
        }
        
        # Create S3 key with date-based folder structure
        date_folder = datetime.now().strftime('%Y/%m/%d')
        s3_key = f"errors/{date_folder}/{conversation_id}.json"
        
        # Upload to S3
        s3.put_object(
            Bucket=conversation_bucket,
            Key=s3_key,
            Body=json.dumps(error_data, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Error logged to S3: {s3_key}")
        
    except Exception as e:
        logger.error(f"Failed to log error to S3: {e}")

# -----------------------
# S3 utility functions
# -----------------------
# Gets a list of all JSON files stored in the specified S3 bucket
def list_json_files(bucket):
    paginator = s3.get_paginator("list_objects_v2")
    json_files = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".json"):
                json_files.append(obj["Key"])
    return json_files

# Downloads all attendance data from S3 bucket and combines it into one big list
def load_s3_data():
    try:
        print("=== LOADING S3 DATA ===")
        data = []
        # List all JSON files in the bucket
        resp = s3.list_objects_v2(Bucket=bucket_name)
        json_files = [obj['Key'] for obj in resp.get('Contents', []) if obj['Key'].endswith('.json')]
        print(f"Found {len(json_files)} JSON files in S3")
        
        for key in json_files:
            try:
                print(f"Loading file: {key}")
                obj = s3.get_object(Bucket=bucket_name, Key=key)
                records = json.loads(obj['Body'].read().decode('utf-8'))
                if isinstance(records, list):
                    data.extend(records)
                else:
                    data.append(records)
                print(f"Loaded {len(records) if isinstance(records, list) else 1} records from {key}")
            except Exception as e:
                print(f"Error loading {key}: {e}")
                logger.error(f"Error loading {key}: {e}")
                continue
        
        # Flatten if we have nested lists
        all_data = []
        for item in data:
            if isinstance(item, list):
                all_data.extend(item)
            else:
                all_data.append(item)
        
        print(f"Total flattened records: {len(all_data)}")
        
    except Exception as e:
        print(f"ERROR in load_s3_data: {e}")
        logger.error(f"Error loading S3 data: {e}")
        all_data = []
    
    logger.info(f"Loaded {len(all_data)} records from S3")
    return all_data

CACHE_TTL = 600  # seconds (10 minutes)
_cached_data = None
_last_cache_time = 0

# Returns S3 data from memory cache to avoid downloading it every time (saves time and money)
def get_cached_s3_data():
    global _cached_data, _last_cache_time
    now = time.time()
    if _cached_data is None or (now - _last_cache_time) > CACHE_TTL:
        _cached_data = load_s3_data()
        _last_cache_time = now
    return _cached_data


def get_sheet_records():
    """Read the configured Google Sheet (by env SHEET_KEY) and return list of dicts.
    Uses SA_JSON env var for service-account credentials.
    Returns empty list on error.
    """
    try:
        sa_path = os.environ.get('SA_JSON')
        sheet_id = os.environ.get('SHEET_KEY')
        if not sa_path or not sheet_id:
            logger.warning('SA_JSON or SHEET_KEY not set; cannot read Google Sheet')
            return []

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(sa_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        records = []
        # iterate all worksheets/tabs and include sheet title in each record
        for ws in sh.worksheets():
            values = ws.get_all_values()
            if not values or len(values) < 2:
                continue

            # Heuristic: find the header row by searching for 'NAME' or 'NAME OF THE STUDENT' or 'S.No'
            header_row_idx = None
            for idx, row in enumerate(values[:10]):
                joined = " ".join([str(c).lower() for c in row if c])
                if 'name of the student' in joined or 'name' in joined or 's.no' in joined or 's.no.' in joined:
                    header_row_idx = idx
                    break
            if header_row_idx is None:
                # fallback to first row
                header_row_idx = 0

            header = values[header_row_idx]

            # Build composite column headers by combining the rows above the header row
            # This helps capture multi-row headers like SUBJECT -> DATE -> TYPE OF ASSESSMENT
            col_headers = []
            max_cols = max(len(r) for r in values[:header_row_idx+1])
            for col in range(max_cols):
                parts = []
                for r in range(0, header_row_idx+1):
                    cell = values[r][col] if col < len(values[r]) else ''
                    cell = str(cell).strip()
                    if cell and cell not in parts:
                        parts.append(cell)
                # fallback to header row cell if parts empty
                if not parts:
                    hdr_cell = header[col] if col < len(header) else f"col_{col+1}"
                    parts = [str(hdr_cell).strip()]
                col_headers.append(' | '.join(parts))

            # data rows are the rows after the header row
            for row_idx, row in enumerate(values[header_row_idx+1:], start=header_row_idx+2):
                # stop at the first empty row (no name) to avoid trailing empties
                name_cell = ''
                # try to find a name cell in the row (any non-empty cell)
                for cell in row:
                    if str(cell).strip():
                        name_cell = str(cell).strip()
                        break
                if not name_cell:
                    # skip empty rows
                    continue

                rec = {"__sheet": ws.title, "__row": row_idx}
                for i in range(len(col_headers)):
                    key = col_headers[i] if i < len(col_headers) else f"col_{i+1}"
                    val = row[i] if i < len(row) else ""
                    rec[key] = val
                records.append(rec)
        logger.info(f"Loaded {len(records)} total records from Google Sheets (all tabs)")
        return records
    except Exception as e:
        logger.error(f"Error reading Google Sheet: {e}")
        return []

# -----------------------
# Simple in-memory sheet cache
# -----------------------
SHEET_CACHE_TTL = int(os.environ.get('SHEET_CACHE_TTL', 300))  # seconds
_sheet_cache = None
_sheet_cache_ts = 0

def get_cached_sheet_data(force_refresh=False):
    """Return cached sheet records, refresh when TTL expired or force_refresh True.
    Falls back to empty list on error.
    """
    global _sheet_cache, _sheet_cache_ts
    now = time.time()
    if force_refresh or _sheet_cache is None or (now - _sheet_cache_ts) > SHEET_CACHE_TTL:
        try:
            logger.info("Refreshing sheet cache from Google Sheets...")
            _sheet_cache = get_sheet_records()
            _sheet_cache_ts = now
        except Exception as e:
            logger.error(f"Failed to refresh sheet cache: {e}")
            _sheet_cache = _sheet_cache or []
    return _sheet_cache or []


def find_relevant_rows(query, records, max_rows=20):
    """Simple relevance scoring: count token overlaps between query and record JSON string.
    Returns up to max_rows most relevant records.
    """
    if not records:
        return []
    q = re.sub(r"[^A-Za-z0-9 ]+", " ", query).lower().split()
    if not q:
        return records[:max_rows]

    scores = []
    for rec in records:
        text = json.dumps(rec).lower()
        score = sum(1 for t in q if t and t in text)
        scores.append((score, rec))

    # sort descending by score
    scores.sort(key=lambda x: x[0], reverse=True)
    filtered = [r for s, r in scores if s > 0]
    if not filtered:
        # no matches; return first rows (as fallback)
        return records[:min(max_rows, len(records))]
    return filtered[:max_rows]


def detect_grade_from_query(query):
    """Return a normalized grade/tab name candidate from the query, or None.
    Matches patterns like 'k1', 'K1', 'grade 9', 'gr9', 'grade9', 'g9', 'class 9'.
    """
    q = query.lower()
    # k1, k2, etc.
    m = re.search(r"\b(k\s?\d)\b", q)
    if m:
        return m.group(1).replace(" ", "").upper()
    # grade 9, class 9, g9, gr9
    m = re.search(r"\b(?:grade|class|gr|g)\s?(\d{1,2})\b", q)
    if m:
        return f"G{m.group(1)}"
    return None


def find_student_matches(query, records):
    """Try to find records that match a student's name mentioned in the query.
    Returns list of matching records (may be empty).
    Strategy:
      - look for capitalized name tokens (e.g., 'Nanee Ayil.G')
      - otherwise, use significant lowercase tokens from the query and look for records containing them
    """
    # 1) capitalized names
    caps = re.findall(r"\b[A-Z][a-zA-Z\.]{2,}(?:\s+[A-Z][a-zA-Z\.]{2,})*\b", query)
    candidates = [c.strip() for c in caps]

    def normalize(text):
        return re.sub(r"[\.\s]+", " ", str(text).lower()).strip()

    def record_contains(rec, s):
        return normalize(s) in normalize(json.dumps(rec))

    matches = []
    if candidates:
        for c in candidates:
            for r in records:
                if record_contains(r, c):
                    matches.append(r)
        # dedupe
        uniq = []
        seen = set()
        for r in matches:
            k = (r.get('__sheet',''), r.get('__row',''))
            if k not in seen:
                seen.add(k)
                uniq.append(r)
        return uniq

    # 2) fallback: significant tokens
    tokens = [t for t in re.findall(r"[A-Za-z\.]{3,}", query.lower()) if t not in {'marks','mark','term','english','score','scores','exam','grade','k1','k2','class','student','students'}]
    if not tokens:
        return []

    # score records by how many tokens match
    scored = []
    for r in records:
        text = normalize(json.dumps(r))
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for s, r in scored]


def find_target_columns_for_query(query, records):
    """Find column keys that best match the requested subject and term in the query.
    Returns a list of column keys (may be empty).
    Strategy: normalize composite headers and score columns by presence of subject and term tokens.
    """
    if not records:
        return []

    # subject and term tokens (include common synonyms/plurals)
    q = query.lower()
    subj_tokens = ['english', 'eng', 'math', 'maths', 'mathematics', 'evs', 'rhymes', 'science', 'sci', 'social', 'hindi']
    term_tokens = ['term 1', 'term1', 'term 2', 'term2', 'term']

    subj = None
    term = None
    assessment = None
    for s in subj_tokens:
        if s in q:
            subj = s
            break
    for t in term_tokens:
        if t in q:
            term = t
            break
    # detect explicit assessment code (A1, A2, etc.)
    m = re.search(r"\ba\s?\d+\b", q)
    if m:
        assessment = m.group(0).replace(' ', '')

    # If we didn't detect a subject token from the fixed list, try deriving
    # subject candidates from the sheet headers (composite keys) and match them
    if not subj:
        header_candidates = set()
        for rec in records[:10]:
            for k in rec.keys():
                if k.startswith('__'):
                    continue
                parts = [p.strip() for p in str(k).split('|') if p and p.strip()]
                for p in parts:
                    pl = p.lower()
                    # ignore numeric/date-like parts and small words
                    # ignore obvious numeric/date-like candidates and tiny tokens
                    if re.search(r"\d", pl):
                        continue
                    if len(pl) < 3:
                        continue
                    # ignore term/assessment tokens when building subject header candidates
                    if any(tok in pl for tok in ['term', 'a1', 'a2', 'a3', 'a4']):
                        continue
                    header_candidates.add(pl)

        # Try matching multi-word candidates first
        for cand in sorted(header_candidates, key=lambda x: -len(x)):
            if cand in q:
                subj = cand
                break

    # As a final fallback, try to match single-word tokens from header candidates
    if not subj:
        for cand in header_candidates:
            tokens = cand.split()
            for tok in tokens:
                if tok in q:
                    subj = cand
                    break
            if subj:
                break
    # examine keys across records and also inspect column values to tell
    # percentage-like columns apart from raw-score columns
    # build a sample of records to inspect keys from (more robust than single first row)
    sample_records = records[:min(50, len(records))]
    # collect all non-meta keys seen in the sample
    sample_keys = []
    seen_keys = set()
    for r in sample_records:
        for k in r.keys():
            if k.startswith('__'):
                continue
            # skip obvious name/meta columns and very long document-title keys
            klower = str(k).lower()
            meta_blocklist = ['the oasis', 'cumulative', 'maximum marks', 'maximum mark', 'subjects', 'date', 'type of assessment', 'maximum', 's.no', 's.no.', 'name of the student', 'name']
            # skip keys that look like document titles or metadata
            if any(tok in klower for tok in meta_blocklist):
                continue
            # skip extremely long header strings (likely document header)
            if len(klower.split()) > 12:
                continue
            if k not in seen_keys:
                seen_keys.add(k)
                sample_keys.append(k)

    candidates = []

    # We use the module-level `is_column_percentage_like` helper below instead of
    # a nested broken implementation. This avoids recursion/undefined variable bugs
    # and centralises the percentage-detection logic.

    for k in sample_keys:
        kl = str(k).lower()
        score = 0
        if subj and subj in kl:
            score += 3
        if term and term in kl:
            score += 3
        # boost assessment column when user explicitly asks for A1/A2
        if assessment and assessment in kl:
            score += 3
        # partial matches: prefer explicit 'term' mentions; do NOT boost A1/A2-like codes
        if any(tok in kl for tok in ['term 1', 'term1', 'term']):
            score += 2
        # penalize assessment codes (A1/A2/etc) when a term was requested to avoid choosing A1 over TERM1
        if term and re.search(r"\ba\d+\b", kl):
            score -= 2

        # detect percentage-like columns and boost score when query asks for percentage
        # Here we don't know preference yet; we'll return candidates with meta info
        pct_like = is_column_percentage_like(k, records)
        candidates.append((score, pct_like, k))

    # Debug log: show initial scoring before ordering
    try:
        logger.info(f"find_target_columns_for_query debug: subj={subj} term={term} assessment={assessment} sample_keys={sample_keys}")
        logger.info(f"find_target_columns_for_query debug: raw_candidates={candidates}")
    except Exception:
        pass

    # sort primarily by score, secondarily prefer pct_like when the query mentions percentage
    # We'll return up to top 6 so caller can pick
    candidates.sort(key=lambda x: (x[0], 1 if x[1] else 0), reverse=True)
    # If the user explicitly asked for percentages, prefer percentage-like columns;
    # otherwise prefer raw-score (non-percentage) columns. This helps when sheets
    # contain two datasets (marks + percentage) side-by-side.
    want_pct = detect_percentage_request(query)
    if want_pct:
        preferred = [k for s, p, k in candidates if p]
        others = [k for s, p, k in candidates if not p]
    else:
        preferred = [k for s, p, k in candidates if not p]
        others = [k for s, p, k in candidates if p]

    ordered = preferred + others

    # Promote columns that explicitly mention the requested subject (and subject+term when both are present).
    # This prevents date-only TERM headers from outranking subject columns when the user asked for a subject.
    try:
        if subj:
            subj_variants = set([subj])
            # add simple singular/plural variants
            if subj.endswith('s'):
                subj_variants.add(subj.rstrip('s'))
            else:
                subj_variants.add(subj + 's')
            # common shorthand mappings
            syn_map = {
                'maths': 'math', 'math': 'maths',
                'eng': 'english', 'sci': 'science'
            }
            if subj in syn_map:
                subj_variants.add(syn_map[subj])

            klowered = [str(k).lower() for k in ordered]
            # If the query also asked for a specific term, prefer columns that contain BOTH subject and term
            if term:
                both = [k for k in ordered if any(v in str(k).lower() for v in subj_variants) and term in str(k).lower()]
                if both:
                    ordered = both + [k for k in ordered if k not in both]
                else:
                    subj_only = [k for k in ordered if any(v in str(k).lower() for v in subj_variants)]
                    if subj_only:
                        ordered = subj_only + [k for k in ordered if k not in subj_only]
            else:
                subj_only = [k for k in ordered if any(v in str(k).lower() for v in subj_variants)]
                if subj_only:
                    ordered = subj_only + [k for k in ordered if k not in subj_only]
    except Exception:
        # keep original order on any unexpected error
        pass

    # Additional pairing: when sheets contain paired datasets (raw marks + percentage)
    # we try to prefer the non-percentage sibling when the user asked for marks
    # by grouping candidates by a normalized header base (strip digits/punctuation)
    def _normalize_base(k):
        s = str(k).lower()
        # remove numbers and punctuation, collapse whitespace
        s = re.sub(r"\d+", "", s)
        s = re.sub(r"[^a-z]+", " ", s)
        s = s.strip()
        return s

    want_pct = detect_percentage_request(query)
    if not want_pct:
        # build groups
        groups = {}
        for k in ordered:
            base = _normalize_base(k)
            groups.setdefault(base, []).append(k)

        # rebuild ordered list promoting non-pct siblings ahead of pct ones
        final = []
        seen = set()
        for k in ordered:
            base = _normalize_base(k)
            if base in seen:
                continue
            seen.add(base)
            members = groups.get(base, [])
            # split into non-pct then pct
            non_pct = [m for m in members if not is_column_percentage_like(m, sample_records)]
            pct = [m for m in members if is_column_percentage_like(m, sample_records)]
            final.extend(non_pct + pct)

        # preserve overall order for any leftovers
        ordered = [k for k in final if k in ordered] + [k for k in ordered if k not in final]

    # return up to top 6 candidate column keys
    try:
        logger.info(f"find_target_columns_for_query debug: ordered_candidates={ordered}")
    except Exception:
        pass
    return ordered[:6]


def extract_marks_for_student_rows(student_rows, target_cols):
    """Given student_rows (list of rec dicts) and target_cols (list of keys),
    return a structured mapping of sheet -> row -> {col: value} for non-empty values.
    """
    results = []
    for r in student_rows:
        entry = {'__sheet': r.get('__sheet'), '__row': r.get('__row'), 'values': {}}
        for col in target_cols:
            # tolerant key lookup: exact key or case-insensitive match
            if col in r:
                v = r.get(col)
            else:
                # try case-insensitive search
                found = None
                for k in r.keys():
                    if k.lower() == col.lower():
                        found = k
                        break
                v = r.get(found) if found else None
            if v is not None and str(v).strip() != '':
                entry['values'][col] = v
        results.append(entry)
    return results


def choose_best_student_row(student_rows, query, target_cols):
    """Choose the single best student row from candidates for this query.
    Strategy:
      - prefer exact/near-exact name match against common name columns
      - prefer rows with more non-empty target_cols
      - use token-overlap as tie-breaker
    """
    if not student_rows:
        return None

    def normalize(s):
        return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()

    qtokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 1]

    name_keys = ['name of the student', 'name', 'student name', 'student', 'full name']

    best = None
    best_score = -1
    for r in student_rows:
        # find a plausible name cell
        name_cell = None
        for k in r.keys():
            kl = str(k).lower()
            if any(nk in kl for nk in name_keys):
                v = r.get(k)
                if v and str(v).strip():
                    name_cell = str(v).strip()
                    break
        # fallback: try to find the first non-empty textual cell
        if not name_cell:
            for k, v in r.items():
                if k.startswith('__'):
                    continue
                if v and re.search(r"[A-Za-z]", str(v)):
                    name_cell = str(v).strip()
                    break

        name_norm = normalize(name_cell or '')
        # name token overlap
        name_tokens = name_norm.split()
        name_overlap = sum(1 for t in qtokens if t in name_tokens)

        # completeness: how many of the target_cols are non-empty
        completeness = 0
        for c in target_cols:
            v = r.get(c)
            if v is not None and str(v).strip() != '':
                completeness += 1

        score = (name_overlap * 3) + completeness
        # small boost for exact substring match
        if name_norm and any(t in name_norm for t in qtokens):
            score += 1

        if score > best_score:
            best_score = score
            best = r

    return best


def detect_percentage_request(query):
    """Return True if the user is explicitly asking for percentages."""
    if not query:
        return False
    q = query.lower()
    # explicit percent indicators -> treat as percentage request
    percent_tokens = ['percentage', 'percent', '%', 'percentile', 'percentage in']
    if any(tok in q for tok in percent_tokens):
        return True
    # if the user explicitly asked for marks/scores/raw values, prefer raw (not percentage)
    marks_tokens = ['mark', 'marks', 'score', 'scores', 'raw', 'out of']
    if any(tok in q for tok in marks_tokens):
        return False
    return False


def detect_term_from_query(query):
    """Detect if query mentions a term (e.g., Term 1/Term1) and return normalized token or None."""
    if not query:
        return None
    q = query.lower()
    m = re.search(r"term\s?1|term1|term\s?2|term2|term\s?[ivxl]+", q)
    if m:
        return m.group(0).replace(' ', '')
    return None


def detect_assessment_from_query(query):
    """Detect A1/A2 style assessment tokens (e.g., 'A1', 'a1', 'a 1') and return normalized token like 'a1' or None."""
    if not query:
        return None
    q = query.lower()
    # match variations like 'A1', 'a 1', 'assessment a1', 'assmt a1'
    m = re.search(r"\b(?:assessment|assmt|a)\s?[\-:]?\s?(\d+)\b", q)
    if m:
        return f"a{m.group(1)}"
    # fallback: simple 'a1' or 'a 1'
    m2 = re.search(r"\ba\s?(\d+)\b", q)
    if m2:
        return f"a{m2.group(1)}"
    return None


def is_column_percentage_like(col_key, records, max_samples=50):
    """Return True if a column contains mostly percentage-like numeric values (0-100).
    """
    cnt = 0
    nums = []
    header_key = str(col_key).lower()
    # header-level hint
    if '%' in header_key or 'percent' in header_key or 'percentage' in header_key:
        return True
    for r in records[:max_samples]:
        v = r.get(col_key)
        if v is None:
            # try case-insensitive key
            for k in r.keys():
                if k.lower() == str(col_key).lower():
                    v = r.get(k)
                    break
        if v is None:
            continue
        s = str(v).strip()
        if s == '':
            continue
        cleaned = re.sub(r"[^0-9\.\-]+", "", s)
        if cleaned == '':
            continue
        try:
            num = float(cleaned)
        except Exception:
            continue
        cnt += 1
        nums.append(num)
    if cnt == 0:
        return False
    max_val = max(nums)
    if max_val >= 95:
        return True
    return False

# -----------------------
# Intelligent Query Classification
# -----------------------
def classify_query(user_query):
    """
    Determines whether the query is about:
    - S3 attendance data (internal)
    - News (external API)
    - General knowledge (use Bedrock only)
    """
    query_lower = user_query.lower()
    
    # Attendance keywords (S3 data)
    attendance_keywords = [
        "attendance", "absent", "present", "class", "roll", "register",
        "attendance rate", "missing", "who is", "who was", "students", "names", "list"
    ]

    # Marks/grades keywords (Google Sheet)
    marks_keywords = [
        "mark", "marks", "score", "scores", "result", "results", "term", "exam", "percentage", "grade"
    ]
    
    # News API keywords
    news_keywords = ["news", "headlines", "current events", "today's news", "breaking news", "latest news"]
    
    # Check for marks/grades queries first (give precedence)
    matched_marks = [k for k in marks_keywords if k in query_lower]
    if matched_marks:
        logger.info(f"classify_query: matched marks keywords={matched_marks}")
        return "sheet_marks"

    # Check for S3 attendance queries
    matched_attendance = [k for k in attendance_keywords if k in query_lower]
    if matched_attendance:
        logger.info(f"classify_query: matched attendance keywords={matched_attendance}")
        return "s3_attendance"

    # Check for news queries
    matched_news = [k for k in news_keywords if k in query_lower]
    if matched_news:
        logger.info(f"classify_query: matched news keywords={matched_news}")
        return "external_news"
    
    # Default to general knowledge (Bedrock only)
    return "general"

# -----------------------
# External API Functions
# -----------------------
def get_news_data(query=""):
    """Get latest news headlines"""
    try:
        if not EXTERNAL_APIS["news"]["enabled"]:
            return {"error": "News service is currently disabled"}
        
        api_key = EXTERNAL_APIS["news"]["api_key"]
        if api_key == "demo_key":
            return {
                "news": [
                    {"title": "Demo News: Technology Advances in Education", "source": "Demo Source"},
                    {"title": "Demo News: School Attendance Tracking Improvements", "source": "Demo Source"}
                ],
                "note": "This is demo data. Set NEWS_API_KEY environment variable for real data."
            }
        
        # Determine country based on query
        country = "us"  # default
        if any(city in query.lower() for city in ["chennai", "mumbai", "delhi", "bangalore", "india", "indian"]):
            country = "in"
        elif any(city in query.lower() for city in ["london", "uk", "britain", "british"]):
            country = "gb"
        
        url = f"{EXTERNAL_APIS['news']['base_url']}?country={country}&apiKey={api_key}&pageSize=5"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = []
            for article in data.get("articles", [])[:5]:
                articles.append({
                    "title": article["title"],
                    "source": article["source"]["name"],
                    "description": article.get("description", "")[:100] + "..."
                })
            return {"news": articles}
        else:
            return {"error": f"News API error: {response.status_code}"}
    except Exception as e:
        return {"error": f"News service error: {str(e)}"}

# -----------------------
# Hybrid Query Processing
# -----------------------
def process_hybrid_query(user_query, history=None):
    """
    Main function that routes queries to appropriate data sources
    """
    start_time = time.time()
    query_type = classify_query(user_query)
    logger.info(f"Query classified as: {query_type} -- query='{user_query[:120]}'")
    
    try:
        response = ""

        if query_type == "sheet_marks":
            # Route marks/grades queries to the Google Sheet (cached)
            try:
                sheet_data = get_cached_sheet_data()
                logger.info(f"Sheet cache contains {len(sheet_data)} rows")
                if sheet_data:
                    # If the query contains a grade token (e.g., 'K1' or 'grade 9'), try to limit to that sheet/tab
                    grade_token = detect_grade_from_query(user_query)
                    if grade_token:
                        filtered_by_grade = [r for r in sheet_data if grade_token.lower() in r.get('__sheet','').lower()]
                        if filtered_by_grade:
                            # don't completely discard other sheets; prioritise rows from the detected grade
                            logger.info(f"Prioritising sheet data to tab matching grade token '{grade_token}' -> {len(filtered_by_grade)} rows")
                            remaining = [r for r in sheet_data if r not in filtered_by_grade]
                            sheet_data = filtered_by_grade + remaining

                    # Try exact student matching across sheets first
                    student_matches = find_student_matches(user_query, sheet_data)
                    if student_matches:
                        logger.info(f"Found {len(student_matches)} student-specific matches in sheet")
                        all_data = student_matches[:60]
                    else:
                        # fallback to relevance-based selection
                        relevant = find_relevant_rows(user_query, sheet_data, max_rows=60)
                        logger.info(f"Using {len(relevant)} relevant rows from sheet for marks query")
                        all_data = relevant
                else:
                    logger.info("Sheet cache empty; falling back to S3 data for marks query")
                    all_data = get_cached_s3_data()
            except Exception as e:
                logger.error(f"Error loading sheet data for marks: {e}")
                all_data = get_cached_s3_data()

            # Try deterministic extraction of marks before calling the LLM
            try:
                # find any student-specific rows from the selected all_data
                student_rows = find_student_matches(user_query, all_data)
                # detect whether the user asked for percentage specifically
                want_pct = detect_percentage_request(user_query)
                # detect if user specified a term (Term 1 / Term2 etc.)
                term_token = detect_term_from_query(user_query)
                # detect if user specified an assessment (A1/A2 etc.)
                assessment_token = detect_assessment_from_query(user_query)

                # detect target column candidates
                candidate_cols = find_target_columns_for_query(user_query, all_data)
                logger.info(f"Deterministic extractor: candidate_cols={candidate_cols} student_rows={len(student_rows)} want_pct={want_pct} term_token={term_token}")

                # AGGRESSIVE FIX: if the user explicitly asked for a TERM (term1/term2),
                # exclude any A# (A1/A2...) candidate columns entirely so TERM columns are preferred.
                if term_token:
                    # refine aggressive filter: drop A# candidates only when they don't match the requested subject
                    # or when the user explicitly asked for marks and the A# column looks percentage-like.
                    subj_tokens_local = ['english', 'eng', 'math', 'maths', 'mathematics', 'evs', 'rhymes', 'science', 'sci', 'social', 'hindi']
                    subj_in_query = None
                    for s in subj_tokens_local:
                        if s in user_query.lower():
                            subj_in_query = s
                            break

                    refined = []
                    for c in candidate_cols:
                        kl = str(c).lower()
                        if re.search(r"\ba\d+\b", kl):
                            # If this A# candidate mentions the requested subject and appears to be raw (not pct), keep it
                            if subj_in_query and subj_in_query in kl and not is_column_percentage_like(c, all_data):
                                refined.append(c)
                                continue
                            # Otherwise drop A# candidate
                            continue
                        refined.append(c)

                    if refined:
                        logger.info(f"Aggressive TERM filter applied (refined): remaining={refined}")
                        candidate_cols = refined
                    else:
                        logger.info("Aggressive TERM filter removed all candidates; keeping original candidate list")

                # Prefer assessment (A1/A2) columns when explicitly requested; otherwise prefer TERM columns when requested
                target_cols = []
                if assessment_token:
                    # user explicitly asked for A1/A2-style assessment -> prefer headers that include that token
                    for c in candidate_cols:
                        kl = str(c).lower()
                        if assessment_token in kl or re.search(r"\ba\d+\b", kl):
                            target_cols.append(c)
                    if target_cols:
                        logger.info(f"Assessment-specific columns selected: {target_cols}")

                # Only consider term-specific matching if we didn't already find assessment-specific columns
                if not target_cols and term_token:
                    term_tok = term_token.replace(' ', '').lower()
                    digits = re.findall(r"\d+", term_tok)
                    for c in candidate_cols:
                        kl = str(c).lower()
                        matches_number = False
                        if term_tok in kl:
                            matches_number = True
                        elif 'term' in kl and digits:
                            if any(d in kl for d in digits):
                                matches_number = True
                        # exclude A# matches when matching TERM requests
                        if matches_number and not re.search(r"\ba\d+\b", kl):
                            target_cols.append(c)
                    if target_cols:
                        logger.info(f"Term-specific columns selected: {target_cols}")

                # If no term/assessment-specific columns found (or no such token requested), fall back to pct vs raw preference
                if not target_cols:
                    if want_pct:
                        # prefer percentage-like columns
                        for c in candidate_cols:
                            is_pct = is_column_percentage_like(c, all_data)
                            logger.info(f"Pct-check for column '{c}': {is_pct}")
                            if is_pct:
                                target_cols.append(c)
                            if len(target_cols) >= 3:
                                break
                    else:
                        # prefer non-percentage (raw score) columns
                        for c in candidate_cols:
                            is_pct = is_column_percentage_like(c, all_data)
                            logger.info(f"Pct-check for column '{c}': {is_pct}")
                            if not is_pct:
                                target_cols.append(c)
                            if len(target_cols) >= 3:
                                break

                logger.info(f"Deterministic extractor: target_cols after filtering={target_cols}")

                if target_cols and student_rows:
                    # Re-rank student_rows with tie-breakers:
                    #  - prefer rows from the grade/tab detected in the query
                    #  - prefer rows with more non-empty values for the target columns (completeness)
                    #  - prefer later rows (higher __row) as a weak recency proxy
                    grade_token_local = detect_grade_from_query(user_query)
                    def row_score(r):
                        score = 0
                        try:
                            sheet_name = str(r.get('__sheet','')).lower()
                        except Exception:
                            sheet_name = ''
                        if grade_token_local and grade_token_local.lower() in sheet_name:
                            score += 100
                        # completeness: count non-empty target cols
                        compl = 0
                        for c in target_cols:
                            v = None
                            if c in r:
                                v = r.get(c)
                            else:
                                for k in r.keys():
                                    if k.lower() == str(c).lower():
                                        v = r.get(k)
                                        break
                            if v is not None and str(v).strip() != '':
                                compl += 1
                        score += compl * 5
                        # weak recency: prefer higher row numbers
                        try:
                            rownum = int(r.get('__row') or 0)
                        except Exception:
                            rownum = 0
                        score += rownum / 1000.0
                        return score

                    student_rows_sorted = sorted(student_rows, key=lambda x: row_score(x), reverse=True)
                    best_row = student_rows_sorted[0] if student_rows_sorted else None
                    logger.info(f"Best student row chosen (scored): sheet={best_row.get('__sheet') if best_row else None} row={best_row.get('__row') if best_row else None}")

                    if best_row:
                        # choose the best column using stricter preferences
                        chosen_col = None
                        chosen_val = None

                        # Preference 1: if assessment_token present, try columns that match it first
                        preferred_cols = []
                        if assessment_token:
                            for c in target_cols:
                                if assessment_token in str(c).lower() or re.search(r"\ba\d+\b", str(c).lower()):
                                    preferred_cols.append(c)
                        # Preference 2: if term_token present and no assessment-specific hits, prefer TERM columns
                        if not preferred_cols and term_token:
                            term_tok = term_token.replace(' ', '').lower()
                            for c in target_cols:
                                kl = str(c).lower()
                                if term_tok in kl or ('term' in kl and any(d in kl for d in re.findall(r"\d+", term_tok))):
                                    preferred_cols.append(c)

                        # Fallback: use target_cols order
                        search_cols = preferred_cols + [c for c in target_cols if c not in preferred_cols]

                        for c in search_cols:
                            v = None
                            if c in best_row:
                                v = best_row.get(c)
                            else:
                                # case-insensitive key lookup
                                for k in best_row.keys():
                                    if k.lower() == str(c).lower():
                                        v = best_row.get(k)
                                        break
                            if v is not None and str(v).strip() != '':
                                chosen_col = c
                                chosen_val = v
                                break

                        if chosen_col and chosen_val is not None:
                            # decide whether chosen_col is percentage-like
                            col_is_pct = is_column_percentage_like(chosen_col, all_data)

                            # Log the final deterministic selection for debugging (use best_row values)
                            logger.info(f"Deterministic selection: chosen_col='{chosen_col}', chosen_val='{chosen_val}', col_is_pct={col_is_pct}, sheet='{best_row.get('__sheet') if best_row else None}', row={best_row.get('__row') if best_row else None}")

                            def _fmt_val(v, as_pct=False):
                                sv = str(v).strip()
                                if as_pct and not sv.endswith('%'):
                                    # try to normalize numeric and append % only when column is pct-like
                                    try:
                                        cleaned = re.sub(r"[^0-9\.\-]+", "", sv)
                                        if cleaned == '':
                                            return sv
                                        num = float(cleaned)
                                        if abs(num - round(num)) < 0.01:
                                            return f"{int(round(num))}%"
                                        return f"{round(num,1)}%"
                                    except Exception:
                                        return sv
                                else:
                                    # return raw string as-is
                                    return sv

                            sheet = best_row.get('__sheet')
                            rown = best_row.get('__row')
                            # Only append % when the column looks percentage-like; otherwise keep raw marks
                            det_resp = f"{chosen_col} (Sheet: {sheet}, Row: {rown}): {_fmt_val(chosen_val, as_pct=col_is_pct)}"
                            logger.info("Returning single deterministic marks response")
                            return det_resp
            except Exception as e:
                logger.error(f"Deterministic extraction failed: {e}")

            # If deterministic path didn't return, fall back to Bedrock LLM
            response = query_bedrock(user_query, history or [], all_data)

        elif query_type == "s3_attendance":
            # Route attendance queries to S3 cached data
            try:
                all_data = get_cached_s3_data()
                logger.info(f"Using S3 cached data with {len(all_data)} rows for attendance query")
            except Exception as e:
                logger.error(f"Error loading S3 data: {e}")
                all_data = []

            response = query_bedrock(user_query, history or [], all_data)

        elif query_type == "external_news":
            # Get news data
            news_data = get_news_data()
            if "error" in news_data:
                response = f"Sorry, I couldn't get news information: {news_data['error']}"
            elif "note" in news_data:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                response += f"\nNote: {news_data['note']}"
            else:
                response = "📰 Latest News Headlines:\n\n"
                for article in news_data["news"]:
                    response += f"• {article['title']} - {article['source']}\n"
                    if article.get('description'):
                        response += f"  {article['description']}\n"

        else:  # general queries
            # Use Bedrock for general knowledge
            response = query_bedrock(user_query, history or [], [])

        # Interaction logging simplified - feedback will be collected via modal
        logger.info(f"process_hybrid_query: returning response length={len(response) if response else 0}")

        return response

    except Exception as e:
        logger.error(f"Error in process_hybrid_query: {e}")
        error_response = f"Sorry, I encountered an error processing your request: {str(e)}"

        # Error logging simplified

        return error_response

# -----------------------
# Summarize and query
# -----------------------
# Takes messy attendance data and formats it nicely for the AI to understand
def summarize_records(records):
    summary = []
    for rec in records:
        name = rec.get("Unnamed: 2", "")
        grade = rec.get("Unnamed: 5", "")
        attendance = rec.get("Unnamed: 8", "")
        present = rec.get("Unnamed: 17", "")
        summary.append(f"Name: {name}, Grade: {grade}, Attendance: {attendance}, Present: {present}")
    return "\n".join(summary)

# The main AI brain - takes user question, finds relevant data, asks AI, and returns smart answer
def query_bedrock(user_prompt: str, history: list, all_data) -> str:
    import re
    logger.info(f"Processing query: {user_prompt[:50]}...")
    
    match = re.search(r"\b([A-Z][a-z]+)\b", user_prompt)
    student_name = match.group(1) if match else None

    if student_name:
        filtered = [record for record in all_data if student_name.lower() in json.dumps(record).lower()]
        sample = filtered if filtered else all_data
        logger.info(f"Filtered {len(sample)} records for student: {student_name}")
    else:
        sample = all_data[:min(100, len(all_data))] if isinstance(all_data, list) else all_data

    # If we have data from S3 or Sheets, include a compact JSON excerpt to the model so it can answer precisely.
    if isinstance(all_data, list) and len(all_data) > 0:
        try:
            # Convert sample rows to a compact human-friendly summary
            # First, detect subject and term tokens from the user prompt to prefer corresponding columns
            qlow = user_prompt.lower()
            # include common synonyms and plurals so queries like 'maths' or 'mathematics' match
            subj_tokens = ['english', 'eng', 'math', 'maths', 'mathematics', 'evs', 'rhymes', 'science', 'sci', 'social', 'hindi']
            term_tokens = ['term 1', 'term1', 'term 2', 'term2', 'term']
            subj = None
            term = None
            for s in subj_tokens:
                if s in qlow:
                    subj = s
                    break
            for t in term_tokens:
                if t in qlow:
                    term = t
                    break

            # Ordering tweak: if the user asked for percentages, prefer feeding the model rows from the bottom
            # (bottom-up). If the user asked for marks/scores, feed rows top-down. This helps the model
            # focus on the percentage block when present at the bottom of the sheet.
            want_pct_for_order = detect_percentage_request(user_prompt)
            try:
                if isinstance(sample, list):
                    N = min(100, len(sample))
                    if want_pct_for_order:
                        # bottom-to-top: last N rows, reversed so bottom row appears first
                        ordered_sample = list(reversed(sample[-N:]))
                    else:
                        # top-to-bottom: first N rows
                        ordered_sample = sample[:N]
                else:
                    ordered_sample = sample
            except Exception:
                ordered_sample = sample

            logger.info(f"query_bedrock: sending {len(ordered_sample) if isinstance(ordered_sample, list) else 0} rows to model (want_pct={want_pct_for_order})")

            lines = []
            for rec in ordered_sample[:min(50, len(ordered_sample) if isinstance(ordered_sample, list) else 0)]:
                sheet = rec.get('__sheet', '')
                rownum = rec.get('__row', '')
                # try common name keys
                name = rec.get('NAME OF THE STUDENT') or rec.get('NAME') or rec.get('Name') or ''
                parts = [f"Sheet={sheet}"]
                if rownum:
                    parts.append(f"Row={rownum}")
                if name:
                    parts.append(f"Name={name}")

                # choose columns that match subject/term if possible
                chosen = []
                for k, v in rec.items():
                    if k.startswith('__'):
                        continue
                    if k in {'S.No', 'S.No.', 'S.No', 'NAME', 'Name', 'NAME OF THE STUDENT', 'NAME OF THE STUDENT '}:
                        continue
                    if v is None or str(v).strip() == '':
                        continue
                    kl = str(k).lower()
                    include = False
                    if subj and subj in kl:
                        include = True
                    if term and term in kl:
                        include = True
                    if subj and term and subj in kl and term in kl:
                        include = True
                    if not subj and not term:
                        include = True
                    if include:
                        chosen.append((k, v))

                # If we found specific chosen columns, include them; otherwise include a few non-empty columns
                if chosen:
                    for k, v in chosen:
                        parts.append(f"{k}: {v}")
                else:
                    # include up to 6 non-empty columns for context
                    cnt = 0
                    for k, v in rec.items():
                        if k.startswith('__'):
                            continue
                        if k in {'S.No', 'S.No.', 'S.No', 'NAME', 'Name', 'NAME OF THE STUDENT', 'NAME OF THE STUDENT '}:
                            continue
                        if v is None or str(v).strip() == '':
                            continue
                        parts.append(f"{k}: {v}")
                        cnt += 1
                        if cnt >= 6:
                            break

                lines.append(" | ".join(parts))

            excerpt = "\n".join(lines)
            user_text = (
                f"{user_prompt}\n\n"
                "Here is the relevant student data (one line per matching row):\n"
                f"{excerpt}\n"
                "Please answer the question using only this data when possible. If the sample is insufficient, say so."
            )
        except Exception:
            user_text = user_prompt
    else:
        user_text = user_prompt

    messages = []
    for msg in history:
        if isinstance(msg, dict) and isinstance(msg.get("content", ""), str):
            messages.append({"role": msg.get("role", "user"), "content": [{"text": str(msg.get("content", ""))}]})
    messages.append({"role": "user", "content": [{"text": str(user_text)}]})

    try:
        print("=== SENDING TO BEDROCK ===")
        print(f"Model ID: {INFERENCE_PROFILE_ARN}")
        print(f"Messages count: {len(messages)}")
        logger.info("Sending request to Bedrock...")
        
        resp = bedrock.converse(
            modelId=INFERENCE_PROFILE_ARN,
            messages=messages,
            inferenceConfig={"maxTokens": 256, "temperature": 0.3, "topP": 0.9},
        )
        print("Bedrock response received")
        out = resp.get("output", {}).get("message", {}).get("content", [])
        assistant_text = "".join(part.get("text", "") for part in out if "text" in part)
        print(f"Assistant text: {assistant_text[:100]}...")
        logger.info("Successfully received response from Bedrock")
        return assistant_text or "(No text returned by model)"
    except Exception as e:
        print(f"BEDROCK ERROR: {e}")
        logger.error(f"Bedrock error: {e}")
        return f"Sorry, I'm having trouble processing your request right now. Please try again later. Error: {e}"

# -----------------------
# Main chat route
# -----------------------
# The main webpage - shows the chat interface and processes user questions
@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if "history" not in session:
            session["history"] = []
        
        assistant_text = ""
        if request.method == "POST":
            print("=== POST REQUEST RECEIVED ===")
            user_input = request.form.get("user_input", "").strip()
            print(f"User input: {user_input}")
            if not user_input:
                assistant_text = "Please enter a question."
                print("No user input provided")
            else:
                print(f"Processing user input: {user_input[:50]}...")
                logger.info(f"User input received: {user_input[:50]}...")
                try:
                    print("Processing with hybrid query system...")
                    assistant_text = process_hybrid_query(user_input, session["history"])
                    print(f"Hybrid response: {assistant_text[:100]}...")
                    
                    session["history"].append({"role": "user", "content": user_input})
                    session["history"].append({"role": "assistant", "content": assistant_text})
                    print("Session updated successfully")
                except Exception as e:
                    print(f"ERROR in POST processing: {e}")
                    assistant_text = f"Sorry, there was an error: {e}"
        
        chat_history_html = ""
        for msg in session.get("history", []):
            if msg["role"] == "user":
                chat_history_html += f'<div class="user-msg"><b>You:</b> {msg["content"]}</div>'
            else:
                chat_history_html += f'<div class="ai-msg"><b>AI:</b> {msg["content"]}</div>'
        
        # Check if we should ask for feedback (simplified version)
        should_ask_feedback = len(session.get("history", [])) >= 4  # Ask after 2 exchanges
        feedback_prompt = "How helpful was my previous response?"
        
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>School Attendance Chatbot - Auto Deploy v1.0</title>
            <style>
            * { box-sizing: border-box; }
            body { background: #1565c0; color: #fff; font-family: Arial, sans-serif; margin: 0; padding: 10px; }
            .container { background: #fff; color: #1565c0; border-radius: 10px; padding: 20px; max-width: 700px; margin: 20px auto; } 
            input[type="text"] { width: 100%; padding: 12px; border-radius: 5px; border: 1px solid #1565c0; margin-bottom: 10px; font-size: 16px; }
            input[type="submit"] { background: #1565c0; color: #fff; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; transition: all 0.3s; }
            input[type="submit"]:hover { background: #0d47a1; }
            input[type="submit"]:disabled { background: #ccc; cursor: not-allowed; }
            
            /* Feedback Modal Styles */
            .feedback-modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
            .feedback-content { background-color: #fff; margin: 10% auto; padding: 20px; border-radius: 10px; width: 90%; max-width: 500px; color: #1565c0; }
            .close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
            .close:hover { color: #000; }
            .rating-stars { font-size: 2em; margin: 15px 0; text-align: center; }
            .star { color: #ddd; cursor: pointer; transition: color 0.2s; }
            .star:hover, .star.selected { color: #ffd700; }
            .feedback-textarea { width: 100%; min-height: 80px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; }
            .feedback-submit { background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
            .feedback-skip { background: #95a5a6; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-left: 10px; }
            
            /* Loading Spinner Styles */
            .loading-container { text-align: center; margin: 15px 0; display: none; }
            .spinner { border: 3px solid #e3f2fd; border-top: 3px solid #1565c0; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; display: inline-block; margin-right: 10px; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .loading-text { color: #1565c0; font-style: italic; font-weight: bold; }
            .chat-box { background: #e3f2fd; color: #1565c0; border-radius: 8px; padding: 15px; margin-bottom: 20px; height: 300px; overflow-y: auto; }
            .user-msg { text-align: right; margin: 8px 0; word-wrap: break-word; }
            .ai-msg { text-align: left; margin: 8px 0; word-wrap: break-word; }
            h2 { text-align: center; color: #1565c0; font-size: 1.2em; margin-bottom: 20px; }
            .sample-prompt { color: #1565c0; font-size: 0.9em; margin-bottom: 10px; }
            .error-msg { background: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #c62828; }
            .success-msg { background: #e8f5e8; color: #2e7d32; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #2e7d32; }
            .feedback-prompt { background: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #ffc107; }
            .feedback-btn { background: #ffc107; color: #212529; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; margin-left: 10px; }
            @media (max-width: 600px) {
                .container { margin: 10px; padding: 15px; }
                h2 { font-size: 1.1em; }
                .chat-box { height: 250px; }
                input[type="text"], input[type="submit"] { font-size: 16px; } /* Prevents zoom on iOS */
                .feedback-content { margin: 5% auto; width: 95%; }
            }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🎓 SMART SCHOOL ASSISTANT - Attendance</h2>
                
                <!-- GUARANTEED VISIBLE FEEDBACK BUTTON -->
                <div style="background: #e7f3ff; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center;">
                    <button onclick="showFeedbackModal()" style="background: #4CAF50; color: white; border: none; padding: 15px 30px; font-size: 18px; border-radius: 8px; cursor: pointer; width: 100%; max-width: 400px;">⭐ RATE MY RESPONSE (ALWAYS VISIBLE)</button>
                    <div style="margin-top: 10px; font-size: 14px; color: #666;">Click above to rate the AI's response quality</div>
                </div>
                
                {% if should_ask_feedback %}
                <div class="feedback-prompt">
                    <strong>💭 Quick Feedback:</strong> {{ feedback_prompt }}
                    <button class="feedback-btn" onclick="showFeedbackModal()">Rate Previous Response</button>
                </div>
                {% endif %}
                
                <form method="post" id="chatForm">
                    <div class="sample-prompt">Try: "John's attendance" | "Latest news" | "Tell me a joke"</div>
                    <input name="user_input" type="text" placeholder="Ask about attendance, news, or anything!" required id="userInput">
                    <input type="submit" value="Submit" id="submitBtn">
                </form>
                <div class="loading-container" id="loadingContainer">
                    <div class="spinner"></div>
                    <span class="loading-text">🤖 AI is thinking... Please wait</span>
                </div>
                <div class="chat-box">{{chat_history_html|safe}}</div>
            </div>
            
            <!-- Feedback Modal -->
            <div id="feedbackModal" class="feedback-modal">
                <div class="feedback-content">
                    <span class="close" onclick="closeFeedbackModal()">&times;</span>
                    <h3>📝 How was my response?</h3>
                    <p>Please rate the helpfulness of my previous answer:</p>
                    
                    <div class="rating-stars" id="ratingStars">
                        <span class="star" data-rating="1">★</span>
                        <span class="star" data-rating="2">★</span>
                        <span class="star" data-rating="3">★</span>
                        <span class="star" data-rating="4">★</span>
                        <span class="star" data-rating="5">★</span>
                    </div>
                    
                    <textarea class="feedback-textarea" id="feedbackText" placeholder="Optional: Tell me how I can improve my responses..."></textarea>
                    
                    <div style="text-align: center;">
                        <button class="feedback-submit" onclick="submitFeedback()">Submit Feedback</button>
                        <button class="feedback-skip" onclick="closeFeedbackModal()">Skip</button>
                    </div>
                </div>
            </div>
            
            <script>
            let selectedRating = 0;
            let lastInteractionId = null;
            
            document.getElementById('chatForm').addEventListener('submit', function(e) {
                // Show loading spinner
                document.getElementById('loadingContainer').style.display = 'block';
                
                // Disable submit button but NOT the input (so form data gets sent)
                document.getElementById('submitBtn').disabled = true;
                document.getElementById('submitBtn').value = '🤖 Processing...';
                // Don't disable the input field - we need its value to be submitted!
                
                // Scroll to show loading spinner
                document.getElementById('loadingContainer').scrollIntoView({ behavior: 'smooth' });
                
                // Add timeout to re-enable form if request takes too long (30 seconds)
                setTimeout(function() {
                    if (document.getElementById('submitBtn').disabled) {
                        // Re-enable form controls
                        document.getElementById('submitBtn').disabled = false;
                        document.getElementById('submitBtn').value = 'Submit';
                        document.getElementById('loadingContainer').style.display = 'none';
                        
                        // Show timeout message
                        alert('Request timed out. Please try again.');
                        document.getElementById('userInput').focus();
                    }
                }, 30000); // 30 second timeout
            });
            
            // Auto-focus on input field and scroll chat to bottom
            window.addEventListener('load', function() {
                document.getElementById('userInput').focus();
                // Scroll chat box to bottom to show latest messages
                const chatBox = document.querySelector('.chat-box');
                if (chatBox) {
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            });
            
            // Handle page visibility change (if user switches tabs and comes back)
            document.addEventListener('visibilitychange', function() {
                if (!document.hidden && document.getElementById('submitBtn').disabled) {
                    // If page becomes visible and form is still disabled, re-enable it
                    setTimeout(function() {
                        if (document.getElementById('submitBtn').disabled) {
                            document.getElementById('submitBtn').disabled = false;
                            document.getElementById('submitBtn').value = 'Submit';
                            document.getElementById('loadingContainer').style.display = 'none';
                        }
                    }, 1000);
                }
            });
            
            // Feedback Modal Functions
            function showFeedbackModal() {
                document.getElementById('feedbackModal').style.display = 'block';
            }
            
            function closeFeedbackModal() {
                document.getElementById('feedbackModal').style.display = 'none';
                resetFeedbackForm();
            }
            
            function resetFeedbackForm() {
                selectedRating = 0;
                document.querySelectorAll('.star').forEach(star => {
                    star.classList.remove('selected');
                });
                document.getElementById('feedbackText').value = '';
            }
            
            // Star rating functionality
            document.querySelectorAll('.star').forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.getAttribute('data-rating'));
                    updateStarDisplay();
                });
                
                star.addEventListener('mouseover', function() {
                    const rating = parseInt(this.getAttribute('data-rating'));
                    highlightStars(rating);
                });
            });
            
            document.getElementById('ratingStars').addEventListener('mouseleave', function() {
                updateStarDisplay();
            });
            
            function highlightStars(rating) {
                document.querySelectorAll('.star').forEach((star, index) => {
                    if (index < rating) {
                        star.style.color = '#ffd700';
                    } else {
                        star.style.color = '#ddd';
                    }
                });
            }
            
            function updateStarDisplay() {
                document.querySelectorAll('.star').forEach((star, index) => {
                    if (index < selectedRating) {
                        star.classList.add('selected');
                        star.style.color = '#ffd700';
                    } else {
                        star.classList.remove('selected');
                        star.style.color = '#ddd';
                    }
                });
            }
            
            async function submitFeedback() {
                if (selectedRating === 0) {
                    alert('Please select a rating before submitting.');
                    return;
                }
                
                const feedbackText = document.getElementById('feedbackText').value.trim();
                
                try {
                    const response = await fetch('/api/feedback/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            rating: selectedRating,
                            feedback_text: feedbackText,
                            session_id: 'web_session_' + Date.now()
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('Thank you for your feedback! 🙏');
                        closeFeedbackModal();
                    } else {
                        alert('Failed to submit feedback. Please try again.');
                    }
                } catch (error) {
                    console.error('Error submitting feedback:', error);
                    alert('Error submitting feedback. Please try again.');
                }
            }
            
            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('feedbackModal');
                if (event.target === modal) {
                    closeFeedbackModal();
                }
            }
            </script>
        </body>
        </html>
        """, assistant_text=assistant_text, chat_history_html=chat_history_html, 
            should_ask_feedback=should_ask_feedback, feedback_prompt=feedback_prompt)
    
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return f"Sorry, there was an error processing your request: {e}", 500

# -----------------------
# REST API Endpoints
# -----------------------

@app.route("/api/info", methods=["GET"])
def api_info():
    """Public API information"""
    return jsonify({
        "service": "School Attendance Chatbot API",
        "version": "2.0.0",
        "description": "Simplified hybrid API supporting S3 attendance data and news",
        "capabilities": [
            "Student attendance queries",
            "News headlines", 
            "General knowledge questions"
        ],
        "endpoints": {
            "POST /api/chat": "Main chat endpoint with hybrid intelligence",
            "GET /api/students": "List all students from attendance data",
            "GET /api/news": "Get latest news headlines",
            "PUT /api/attendance": "Update attendance records"
        },
        "authentication": "API key required (Authorization header or api_key parameter)",
        "demo_keys": ["sk-test-12345", "sk-prod-67890", "sk-school-api-key"]
    })

@app.route("/api/chat", methods=["POST"])
@require_api_key
def api_chat():
    """
    Main hybrid chat endpoint - handles both S3 data and external API queries
    """
    start_time = time.time()
    user_message = None
    query_type = None
    response = None
    error_message = None
    
    try:
        data = request.get_json()
        if not data or "message" not in data:
            error_message = "Request must include 'message' field"
            return jsonify({
                "error": error_message,
                "code": "MISSING_MESSAGE"
            }), 400
        
        user_message = data["message"]
        history = data.get("history", [])
        
        # Classify and process with hybrid system
        query_type = classify_query(user_message)
        response = process_hybrid_query(user_message, history)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log conversation to S3
        log_conversation_to_s3(
            query=user_message,
            response=response,
            query_type=query_type,
            user=request.api_user["name"],
            api_key=request.headers.get('Authorization', '').replace('Bearer ', ''),
            response_time_ms=response_time_ms,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            error_message=None
        )
        
        return jsonify({
            "response": response,
            "query_type": query_type,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        error_message = str(e)
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log error conversation to S3
        log_conversation_to_s3(
            query=user_message or "Unknown",
            response=None,
            query_type=query_type or "error",
            user=request.api_user.get("name", "Unknown") if hasattr(request, 'api_user') else "Unknown",
            api_key=request.headers.get('Authorization', '').replace('Bearer ', ''),
            response_time_ms=response_time_ms,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            error_message=error_message
        )
        
        logger.error(f"API chat error: {e}")
        return jsonify({
            "error": f"Internal server error: {error_message}",
            "code": "INTERNAL_ERROR"
        }), 500

@app.route("/api/students", methods=["GET"])
@require_api_key
def api_students():
    """Get list of all students from S3 attendance data"""
    try:
        all_data = get_cached_s3_data()
        students = []
        seen_names = set()
        
        for record in all_data:
            name = record.get("Unnamed: 2", "").strip()
            grade = record.get("Unnamed: 5", "").strip()
            if name and name not in seen_names:
                students.append({
                    "name": name,
                    "grade": grade,
                    "attendance": record.get("Unnamed: 8", ""),
                    "present": record.get("Unnamed: 17", "")
                })
                seen_names.add(name)
        
        return jsonify({
            "students": students[:50],  # Limit to first 50 for API response
            "total_count": len(students),
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API students error: {e}")
        return jsonify({
            "error": f"Error fetching students: {str(e)}",
            "code": "FETCH_ERROR"
        }), 500

@app.route("/api/news", methods=["GET"])
@require_api_key
def api_news():
    """Get latest news headlines"""
    try:
        location = request.args.get("location", "")
        news_data = get_news_data(location)
        
        return jsonify({
            **news_data,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API news error: {e}")
        return jsonify({
            "error": f"News service error: {str(e)}",
            "code": "NEWS_ERROR"
        }), 500


@app.route("/api/sheet_preview", methods=["GET"])
@require_api_key
def api_sheet_preview():
    """Return a short preview of the cached Google Sheet for debugging.
    Query params: n (number of rows, default 10)
    """
    try:
        n = int(request.args.get('n', 10))
        rows = get_cached_sheet_data()
        preview = rows[:n]
        return jsonify({
            "count_cached_rows": len(rows),
            "preview_rows": preview,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"API sheet_preview error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sheet_debug", methods=["GET"])
@require_api_key
def api_sheet_debug():
    """Debug endpoint that returns candidate columns, sample values, matched student rows,
    and which row/column the deterministic extractor would pick for a given query.

    Query params:
      q (required) - the user query to debug
      n (optional) - number of sample rows/values to return (default 10)
    """
    try:
        q = request.args.get('q')
        if not q:
            return jsonify({"error": "Missing query param 'q'"}), 400
        n = int(request.args.get('n', 10))

        sheet_data = get_cached_sheet_data()
        if not sheet_data:
            return jsonify({"error": "No sheet data available in cache"}), 500

        want_pct = detect_percentage_request(q)
        candidate_cols = find_target_columns_for_query(q, sheet_data)

        # build samples for candidate columns
        col_samples = {}
        for c in candidate_cols:
            samples = []
            for r in sheet_data[:n]:
                v = r.get(c)
                if v is None:
                    # try case-insensitive key
                    for k in r.keys():
                        if k.lower() == str(c).lower():
                            v = r.get(k)
                            break
                samples.append(v)
            col_samples[c] = samples

        student_matches = find_student_matches(q, sheet_data)[:n]

        # choose best row and chosen column (re-use logic)
        target_cols = []
        if want_pct:
            for c in candidate_cols:
                cnt = 0
                pct_cnt = 0
                for r in sheet_data[:50]:
                    v = r.get(c)
                    if v is None:
                        continue
                    s = str(v).strip()
                    if s == '':
                        continue
                    cleaned = re.sub(r"[^0-9\.\-]+", "", s)
                    if cleaned == '':
                        continue
                    try:
                        num = float(cleaned)
                    except Exception:
                        continue
                    cnt += 1
                    if 0 <= num <= 100:
                        pct_cnt += 1
                if cnt > 0 and (pct_cnt / cnt) >= 0.6:
                    target_cols.append(c)
                if len(target_cols) >= 3:
                    break
        else:
            for c in candidate_cols:
                cnt = 0
                pct_cnt = 0
                for r in sheet_data[:50]:
                    v = r.get(c)
                    if v is None:
                        continue
                    s = str(v).strip()
                    if s == '':
                        continue
                    cleaned = re.sub(r"[^0-9\.\-]+", "", s)
                    if cleaned == '':
                        continue
                    try:
                        num = float(cleaned)
                    except Exception:
                        continue
                    cnt += 1
                    if 0 <= num <= 100:
                        pct_cnt += 1
                if cnt == 0 or (pct_cnt / cnt) < 0.6:
                    target_cols.append(c)
                if len(target_cols) >= 3:
                    break

        best_row = choose_best_student_row(student_matches, q, target_cols) if student_matches else None
        chosen_col = None
        chosen_val = None
        if best_row:
            for c in target_cols:
                v = best_row.get(c) if c in best_row else None
                if v is None:
                    for k in best_row.keys():
                        if k.lower() == str(c).lower():
                            v = best_row.get(k)
                            break
                if v is not None and str(v).strip() != '':
                    chosen_col = c
                    chosen_val = v
                    break

        return jsonify({
            "query": q,
            "want_percentage": want_pct,
            "candidate_columns": candidate_cols,
            "column_samples": col_samples,
            "student_matches_count": len(student_matches),
            "student_matches_sample": student_matches,
            "best_row": best_row,
            "chosen_column": chosen_col,
            "chosen_value": chosen_val
        })

    except Exception as e:
        logger.error(f"API sheet_debug error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/attendance", methods=["PUT"])
@require_api_key
def api_update_attendance():
    """Update attendance records (demo endpoint)"""
    try:
        if "write" not in request.api_user["permissions"]:
            return jsonify({
                "error": "Insufficient permissions",
                "code": "PERMISSION_DENIED"
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Request body required",
                "code": "MISSING_DATA"
            }), 400
        
        # This is a demo endpoint - in real implementation, you'd update S3
        return jsonify({
            "message": "Attendance update received (demo mode)",
            "data": data,
            "user": request.api_user["name"],
            "timestamp": time.time(),
            "note": "This is a demo endpoint. Real implementation would update S3 bucket."
        })
    
    except Exception as e:
        logger.error(f"API attendance update error: {e}")
        return jsonify({
            "error": f"Update error: {str(e)}",
            "code": "UPDATE_ERROR"
        }), 500

@app.route("/api/conversations", methods=["GET"])
@require_api_key
def api_conversations():
    """Get conversation logs from S3"""
    try:
        # Get query parameters
        date = request.args.get('date', datetime.now().strftime('%Y/%m/%d'))
        limit = int(request.args.get('limit', 50))
        
        # List objects in S3 for the specified date
        prefix = f"conversations/{date}/"
        
        try:
            response = s3.list_objects_v2(
                Bucket=conversation_bucket,
                Prefix=prefix,
                MaxKeys=limit
            )
        except Exception as e:
            if "NoSuchBucket" in str(e):
                return jsonify({
                    "error": f"Conversation bucket '{conversation_bucket}' does not exist. Please create it first.",
                    "code": "BUCKET_NOT_FOUND",
                    "conversations": [],
                    "count": 0
                }), 404
            raise e
        
        conversations = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                try:
                    # Get the conversation file
                    file_response = s3.get_object(
                        Bucket=conversation_bucket,
                        Key=obj['Key']
                    )
                    conversation_data = json.loads(file_response['Body'].read().decode('utf-8'))
                    conversations.append(conversation_data)
                except Exception as e:
                    logger.error(f"Error reading conversation file {obj['Key']}: {e}")
                    continue
        
        # Sort by timestamp (newest first)
        conversations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            "conversations": conversations,
            "count": len(conversations),
            "date": date,
            "bucket": conversation_bucket,
            "user": request.api_user["name"],
            "timestamp": time.time()
        })
    
    except Exception as e:
        logger.error(f"API conversations error: {e}")
        return jsonify({
            "error": f"Error fetching conversations: {str(e)}",
            "code": "FETCH_ERROR"
        }), 500

@app.route("/api/feedback/submit", methods=["POST"])
def submit_feedback():
    """Submit user feedback"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        rating = data.get('rating')
        feedback_text = data.get('feedback_text', '')
        session_id = data.get('session_id')
        
        if not rating or rating < 1 or rating > 5:
            return jsonify({"success": False, "error": "Valid rating (1-5) required"}), 400
        
        # Submit feedback using simplified system
        feedback_id = feedback_system.add_feedback(
            user_question="Previous interaction",
            ai_response="Generated response", 
            rating=rating,
            feedback_text=feedback_text
        )
        
        return jsonify({
            "success": True,
            "feedback_id": feedback_id,
            "message": "Thank you for your feedback!"
        })
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------
# ADMIN DASHBOARD ROUTES
# -----------------------

@app.route("/admin")
@app.route("/admin/")
def admin_dashboard():
    """Admin dashboard to view all user interactions"""
    try:
        conn = sqlite3.connect("school_feedback.db")
        cursor = conn.cursor()
        
        # Check if tables exist first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Initialize with default values
        total_interactions = 0
        total_feedback = 0
        avg_rating = 0.0
        
        # Get stats only if tables exist
        if 'interactions' in tables:
            cursor.execute('SELECT COUNT(*) FROM interactions')
            result = cursor.fetchone()
            total_interactions = result[0] if result and result[0] is not None else 0
        
        if 'feedback' in tables:
            cursor.execute('SELECT COUNT(*) FROM feedback')
            result = cursor.fetchone()
            total_feedback = result[0] if result and result[0] is not None else 0
            
            cursor.execute('SELECT AVG(rating) FROM feedback WHERE rating IS NOT NULL')
            result = cursor.fetchone()
            avg_rating = round(result[0], 2) if result and result[0] is not None else 0.0
        
        # Get recent interactions (only if tables exist)
        interactions = []
        if 'interactions' in tables:
            try:
                if 'feedback' in tables:
                    cursor.execute('''
                        SELECT i.id, i.timestamp, i.user_question, i.ai_response, i.query_type, i.response_time_ms, f.rating, f.feedback_text
                        FROM interactions i
                        LEFT JOIN feedback f ON i.id = f.interaction_id
                        ORDER BY i.timestamp DESC
                        LIMIT 20
                    ''')
                else:
                    cursor.execute('''
                        SELECT id, timestamp, user_question, ai_response, query_type, response_time_ms, NULL, NULL
                        FROM interactions
                        ORDER BY timestamp DESC
                        LIMIT 20
                    ''')
                
                for row in cursor.fetchall():
                    if row and len(row) >= 6:  # Ensure row exists and has minimum columns
                        interactions.append({
                            'id': row[0] or 'N/A',
                            'timestamp': row[1] or 'Unknown',
                            'user_question': row[2] or 'No question',
                            'ai_response': row[3] or 'No response',
                            'query_type': row[4] or 'unknown',
                            'response_time_ms': row[5] or 0,
                            'rating': row[6] if len(row) > 6 and row[6] else None,
                            'feedback_text': row[7] if len(row) > 7 and row[7] else None
                        })
            except Exception as e:
                logger.error(f"Error querying interactions: {e}")
                # Continue with empty interactions list
        
        conn.close()
        
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard - School Chatbot</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .header { background: #2c3e50; color: white; padding: 1rem 2rem; }
        .header h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .nav a { color: #ecf0f1; text-decoration: none; margin-right: 1rem; padding: 0.5rem; border-radius: 4px; }
        .nav a:hover { background: #34495e; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-card h3 { font-size: 2rem; color: #3498db; margin-bottom: 0.5rem; }
        .interaction { background: white; margin-bottom: 1rem; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .interaction-header { display: flex; justify-content: space-between; margin-bottom: 1rem; }
        .timestamp { color: #7f8c8d; font-weight: bold; }
        .query-type { background: #3498db; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; }
        .user-question { background: #e74c3c; color: white; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
        .ai-response { background: #27ae60; color: white; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
        .meta { display: flex; gap: 1rem; font-size: 0.9rem; color: #7f8c8d; margin-top: 0.5rem; }
        .rating { color: #f39c12; font-weight: bold; }
        .refresh-btn { position: fixed; bottom: 2rem; right: 2rem; background: #27ae60; color: white; border: none; padding: 1rem; border-radius: 50px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎓 Admin Dashboard - School Chatbot</h1>
        <div class="nav">
            <a href="/admin">Dashboard</a>
            <a href="/">← Back to Chat</a>
        </div>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>{{ total_interactions }}</h3>
                <p>Total Interactions</p>
            </div>
            <div class="stat-card">
                <h3>{{ total_feedback }}</h3>
                <p>Total Feedback</p>
            </div>
            <div class="stat-card">
                <h3>{{ "%.1f"|format(avg_rating) }}/5</h3>
                <p>Average Rating</p>
            </div>
        </div>
        
        <h2 style="margin-bottom: 1rem;">Recent User Interactions</h2>
        
        {% for interaction in interactions %}
        <div class="interaction">
            <div class="interaction-header">
                <span class="timestamp">{{ interaction.timestamp }}</span>
                <span class="query-type">{{ interaction.query_type or 'general' }}</span>
            </div>
            
            <div class="user-question">
                <strong>👤 USER:</strong>
                <div class="text-block">
                    <span class="short-text">{{ interaction.user_question[:200] }}{% if interaction.user_question|length > 200 %}...{% endif %}</span>
                    {% if interaction.user_question|length > 200 %}
                    <a href="#" class="toggle-link" onclick="toggleText(event, 'uq-{{ loop.index }}')">Show more</a>
                    <div id="uq-{{ loop.index }}" class="full-text" style="display:none; margin-top:0.6rem;">{{ interaction.user_question }}</div>
                    {% endif %}
                </div>
            </div>

            <div class="ai-response">
                <strong>🤖 AI:</strong>
                <div class="text-block">
                    <span class="short-text">{{ interaction.ai_response[:300] }}{% if interaction.ai_response|length > 300 %}...{% endif %}</span>
                    {% if interaction.ai_response|length > 300 %}
                    <a href="#" class="toggle-link" onclick="toggleText(event, 'ai-{{ loop.index }}')">Show more</a>
                    <div id="ai-{{ loop.index }}" class="full-text" style="display:none; margin-top:0.6rem;">{{ interaction.ai_response }}</div>
                    {% endif %}
                </div>
            </div>
            
            {% if interaction.feedback_text %}
            <div style="background: #f39c12; color: white; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;">
                <strong>💭 FEEDBACK:</strong> {{ interaction.feedback_text }}
            </div>
            {% endif %}
            
            <div class="meta">
                <span>IP: {{ interaction.user_ip or 'Unknown' }}</span>
                <span>Response: {{ interaction.response_time_ms or 0 }}ms</span>
                {% if interaction.rating %}
                <span class="rating">Rating: {{ interaction.rating }}/5 ⭐</span>
                {% endif %}
                <span>ID: {{ interaction.id[:8] if interaction.id else 'N/A' }}</span>
            </div>
        </div>
        {% endfor %}
        
        {% if not interactions %}
        <div style="background: white; padding: 2rem; text-align: center; border-radius: 8px;">
            <h3>No interactions found</h3>
            <p>User interactions will appear here once people start using the chatbot.</p>
        </div>
        {% endif %}
    </div>
    
    <button class="refresh-btn" onclick="location.reload()" title="Refresh Data">🔄</button>
    
    <script>
        // Auto-refresh every 30 seconds
        setInterval(() => location.reload(), 30000);
        // Toggle full/short text for long fields
        function toggleText(e, id) {
            e.preventDefault();
            const el = document.getElementById(id);
            if (!el) return;
            if (el.style.display === 'none') {
                el.style.display = 'block';
                e.target.textContent = 'Show less';
            } else {
                el.style.display = 'none';
                e.target.textContent = 'Show more';
            }
        }
    </script>
</body>
</html>
        ''', 
        total_interactions=total_interactions,
        total_feedback=total_feedback, 
        avg_rating=avg_rating,
        interactions=interactions)
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        return f"Admin dashboard error: {e}", 500

# -----------------------
# S3 Bucket Creation (Run once)
# -----------------------
def create_conversation_bucket():
    """Create the S3 bucket for storing conversations if it doesn't exist"""
    try:
        s3.head_bucket(Bucket=conversation_bucket)
        print(f"Bucket '{conversation_bucket}' already exists.")
    except:
        try:
            if REGION == 'us-east-1':
                s3.create_bucket(Bucket=conversation_bucket)
            else:
                s3.create_bucket(
                    Bucket=conversation_bucket,
                    CreateBucketConfiguration={'LocationConstraint': REGION}
                )
            print(f"Created bucket '{conversation_bucket}' successfully!")
        except Exception as e:
            print(f"Error creating bucket '{conversation_bucket}': {e}")

# Analytics dashboard not available in simplified version

# Starts the web server when this file is run directly (not imported)
if __name__ == "__main__":
    # Create conversation bucket if it doesn't exist (run in background to avoid blocking startup)
    try:
        import threading
        threading.Thread(target=create_conversation_bucket, daemon=True).start()
    except Exception:
        # fallback: call synchronously if threading import fails for any reason
        try:
            create_conversation_bucket()
        except Exception:
            pass
    
    print("🚀 School Chatbot with Enhanced Feedback System")
    print("📊 Analytics Dashboard: http://localhost:7860/admin/dashboard")
    print("🔗 Main Chat: http://localhost:7860/")
    
    port = int(os.environ.get("PORT", 7860))
    app.run(host="0.0.0.0", port=port, debug=False)