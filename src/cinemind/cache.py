"""
Semantic cache for CineMind with two-tier caching and freshness gates.
Tier 1: Exact cache (hash-based)
Tier 2: Semantic cache (embedding-based with similarity threshold)
"""
import hashlib
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not installed, using fallback cosine similarity")

# TTL (Time To Live) in hours per request type
TTL_BY_TYPE = {
    "release-date": 12,  # 12 hours - release dates change frequently
    "info": {
        "old_films": 30 * 24,  # 30 days - historical info doesn't change
        "recent_films": 7 * 24,  # 7 days - recent films might have updates
        "default": 7 * 24  # 7 days default
    },
    "recs": 14 * 24,  # 14 days - recommendations don't change much
    "comparison": 7 * 24,  # 7 days
    "spoiler": 30 * 24,  # 30 days - spoilers don't change
    "fact-check": 7 * 24,  # 7 days
}

# Semantic similarity threshold (0.88-0.93 as recommended)
SEMANTIC_SIMILARITY_THRESHOLD = 0.90


@dataclass
class CacheEntry:
    """Cache entry with all metadata."""
    prompt_original: str
    prompt_normalized: str
    prompt_hash: str
    prompt_embedding: Optional[List[float]] = None
    predicted_type: str = "info"
    entities: List[str] = None
    response_text: str = ""
    sources: List[Dict] = None
    created_at: str = ""
    expires_at: str = ""
    agent_version: str = ""
    prompt_version: str = ""
    tool_config_version: str = ""
    cost_metrics: Dict = None
    cache_tier: str = ""  # "exact" or "semantic"
    similarity_score: float = 0.0
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.sources is None:
            self.sources = []
        if self.cost_metrics is None:
            self.cost_metrics = {}


class PromptNormalizer:
    """Normalize prompts for caching."""
    
    # Common variants mapping
    VARIANT_MAPPINGS = {
        r"\brelease date\b": "released",
        r"\brelease dates\b": "released",
        r"\breleased\b": "released",
        r"\bout yet\b": "release status",
        r"\bis.*out\b": "release status",
        r"\bwhen.*come out\b": "release status",
        r"\bpremiere\b": "release status",
    }
    
    def normalize(self, prompt: str) -> str:
        """
        Normalize prompt for caching.
        
        Steps:
        1. Lowercase
        2. Strip punctuation (keep basic sentence structure)
        3. Normalize whitespace
        4. Map common variants
        5. Extract and standardize entities (basic version)
        """
        # Step 1: Lowercase
        normalized = prompt.lower()
        
        # Step 2: Strip excessive punctuation but keep sentence structure
        normalized = re.sub(r'[^\w\s\.\?]', ' ', normalized)
        
        # Step 3: Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Step 4: Map common variants
        for pattern, replacement in self.VARIANT_MAPPINGS.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Step 5: Basic entity normalization (extract movie titles, years)
        # This is a simplified version - could be enhanced with NER
        normalized = self._normalize_entities(normalized)
        
        return normalized
    
    def _normalize_entities(self, text: str) -> str:
        """
        Basic entity normalization.
        Extract movie titles with years and standardize format.
        Example: "The Matrix (1999)" -> "the matrix 1999"
        """
        # Extract (year) patterns and normalize
        text = re.sub(r'\((\d{4})\)', r' \1', text)
        
        # Remove common article variations
        text = re.sub(r'\bthe\s+', '', text)
        
        return text
    
    def compute_hash(self, normalized_prompt: str, classifier_type: str, 
                    tool_config_version: str) -> str:
        """Compute hash for exact cache key."""
        key_string = f"{normalized_prompt}|{classifier_type}|{tool_config_version}"
        return hashlib.sha256(key_string.encode()).hexdigest()


class SemanticCache:
    """
    Two-tier semantic cache with freshness gates.
    """
    
    def __init__(self, db, embedding_provider=None):
        """
        Initialize semantic cache.
        
        Args:
            db: Database instance for storing cache entries
            embedding_provider: Function to compute embeddings (default: OpenAI)
        """
        self.db = db
        self.normalizer = PromptNormalizer()
        self.embedding_provider = embedding_provider or self._default_embedding_provider
        self._create_cache_tables()
    
    def _create_cache_tables(self):
        """Create cache tables in database."""
        cursor = self.db.conn.cursor()
        
        if self.db.use_postgres:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id SERIAL PRIMARY KEY,
                    prompt_hash VARCHAR(255) UNIQUE NOT NULL,
                    prompt_original TEXT NOT NULL,
                    prompt_normalized TEXT NOT NULL,
                    prompt_embedding JSONB,
                    predicted_type VARCHAR(50),
                    entities JSONB,
                    response_text TEXT,
                    sources JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    agent_version VARCHAR(50),
                    prompt_version VARCHAR(50),
                    tool_config_version VARCHAR(50),
                    cost_metrics JSONB,
                    cache_tier VARCHAR(20),
                    similarity_score REAL,
                    INDEX idx_hash (prompt_hash),
                    INDEX idx_expires (expires_at),
                    INDEX idx_type (predicted_type)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_hash TEXT UNIQUE NOT NULL,
                    prompt_original TEXT NOT NULL,
                    prompt_normalized TEXT NOT NULL,
                    prompt_embedding TEXT,
                    predicted_type TEXT,
                    entities TEXT,
                    response_text TEXT,
                    sources TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    agent_version TEXT,
                    prompt_version TEXT,
                    tool_config_version TEXT,
                    cost_metrics TEXT,
                    cache_tier TEXT,
                    similarity_score REAL
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON cache_entries(prompt_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON cache_entries(predicted_type)")
        
        self.db.conn.commit()
        logger.info("Cache tables created successfully")
    
    def _default_embedding_provider(self, text: str) -> List[float]:
        """
        Default embedding provider using OpenAI.
        Falls back to simple hash-based if OpenAI not available.
        """
        try:
            import os
            from openai import OpenAI
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OpenAI API key not found, using fallback embedding")
                return self._fallback_embedding(text)
            
            client = OpenAI(api_key=api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",  # Cheaper, faster
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}, using fallback")
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """
        Fallback embedding using simple hash-based approach.
        Not ideal but better than nothing.
        """
        # Create a simple 128-dim vector from hash
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        # Convert to 128 floats (16 bytes * 8 = 128, but we'll use 128 dims)
        embedding = [float(hash_bytes[i % 16]) / 255.0 for i in range(128)]
        return embedding
    
    def _compute_ttl(self, predicted_type: str, entities: List[str] = None, 
                     need_freshness: bool = False) -> timedelta:
        """
        Compute TTL based on request type and context.
        
        Args:
            predicted_type: Classified request type
            entities: Extracted entities
            need_freshness: Whether query needs fresh data
        
        Returns:
            timedelta for TTL
        """
        if need_freshness:
            # Force short TTL if freshness is needed
            return timedelta(hours=12)
        
        base_ttl = TTL_BY_TYPE.get(predicted_type, TTL_BY_TYPE["info"]["default"])
        
        # Special handling for info type
        if predicted_type == "info" and isinstance(base_ttl, dict):
            # Check if it's about old films (pre-2000) or recent
            if entities:
                # Simple heuristic: if entities contain years before 2000, use old_films TTL
                text = " ".join(entities).lower()
                if re.search(r'\b(19\d{2}|before 2000)\b', text):
                    base_ttl = base_ttl["old_films"]
                else:
                    base_ttl = base_ttl["recent_films"]
            else:
                base_ttl = base_ttl["default"]
        
        if isinstance(base_ttl, dict):
            base_ttl = base_ttl["default"]
        
        return timedelta(hours=base_ttl)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        try:
            if HAS_NUMPY:
                v1 = np.array(vec1)
                v2 = np.array(vec2)
                dot_product = np.dot(v1, v2)
                norm1 = np.linalg.norm(v1)
                norm2 = np.linalg.norm(v2)
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return float(dot_product / (norm1 * norm2))
            else:
                # Fallback implementation without numpy
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                norm1 = sum(a * a for a in vec1) ** 0.5
                norm2 = sum(b * b for b in vec2) ** 0.5
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error computing cosine similarity: {e}")
            return 0.0
    
    def get(self, prompt: str, classifier_type: str, tool_config_version: str,
           predicted_type: str, entities: List[str] = None,
           need_freshness: bool = False) -> Optional[CacheEntry]:
        """
        Get cached response if available and fresh.
        
        Returns:
            CacheEntry if found and fresh, None otherwise
        """
        # Normalize prompt
        normalized = self.normalizer.normalize(prompt)
        
        # Tier 1: Exact cache lookup
        prompt_hash = self.normalizer.compute_hash(normalized, classifier_type, tool_config_version)
        
        exact_match = self._get_exact_match(prompt_hash)
        if exact_match and self._is_fresh(exact_match, predicted_type, need_freshness):
            logger.info(f"Exact cache hit for prompt hash: {prompt_hash[:8]}...")
            exact_match.cache_tier = "exact"
            return exact_match
        
        # Tier 2: Semantic cache lookup
        semantic_match = self._get_semantic_match(
            normalized, predicted_type, need_freshness
        )
        if semantic_match:
            logger.info(f"Semantic cache hit (similarity: {semantic_match.similarity_score:.3f})")
            semantic_match.cache_tier = "semantic"
            return semantic_match
        
        logger.debug("Cache miss")
        return None
    
    def _get_exact_match(self, prompt_hash: str) -> Optional[CacheEntry]:
        """Get exact cache match by hash."""
        cursor = self.db.conn.cursor()
        
        if self.db.use_postgres:
            cursor.execute(
                "SELECT * FROM cache_entries WHERE prompt_hash = %s",
                (prompt_hash,)
            )
        else:
            cursor.execute(
                "SELECT * FROM cache_entries WHERE prompt_hash = ?",
                (prompt_hash,)
            )
        
        row = cursor.fetchone()
        if row:
            return self._row_to_cache_entry(row, cursor)
        return None
    
    def _get_semantic_match(self, normalized_prompt: str, predicted_type: str,
                           need_freshness: bool) -> Optional[CacheEntry]:
        """Get semantic cache match by embedding similarity."""
        # Compute embedding for query
        query_embedding = self.embedding_provider(normalized_prompt)
        
        # Get all non-expired entries of the same type
        cursor = self.db.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        if self.db.use_postgres:
            cursor.execute("""
                SELECT * FROM cache_entries 
                WHERE predicted_type = %s 
                AND expires_at > %s
            """, (predicted_type, now))
        else:
            cursor.execute("""
                SELECT * FROM cache_entries 
                WHERE predicted_type = ? 
                AND expires_at > ?
            """, (predicted_type, now))
        
        rows = cursor.fetchall()
        
        best_match = None
        best_similarity = 0.0
        
        for row in rows:
            entry = self._row_to_cache_entry(row, cursor)
            if not entry.prompt_embedding:
                continue
            
            # Skip if freshness is needed and entry is stale
            if need_freshness and not self._is_fresh(entry, predicted_type, need_freshness):
                continue
            
            similarity = self._cosine_similarity(query_embedding, entry.prompt_embedding)
            if similarity > best_similarity and similarity >= SEMANTIC_SIMILARITY_THRESHOLD:
                best_similarity = similarity
                best_match = entry
                best_match.similarity_score = similarity
        
        return best_match
    
    def _is_fresh(self, entry: CacheEntry, predicted_type: str, need_freshness: bool) -> bool:
        """Check if cache entry is still fresh."""
        if not entry.expires_at:
            return False
        
        try:
            expires = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            return expires > now
        except Exception as e:
            logger.error(f"Error checking freshness: {e}")
            return False
    
    def put(self, prompt: str, response_text: str, sources: List[Dict],
           predicted_type: str, entities: List[str], need_freshness: bool,
           classifier_type: str, tool_config_version: str, agent_version: str,
           prompt_version: str, cost_metrics: Dict = None):
        """
        Store entry in cache.
        
        Args:
            prompt: Original prompt
            response_text: Agent response
            sources: List of source dictionaries
            predicted_type: Classified request type
            entities: Extracted entities
            need_freshness: Whether query needs fresh data
            classifier_type: Classifier version/type
            tool_config_version: Tool configuration version
            agent_version: Agent version
            prompt_version: Prompt version
            cost_metrics: Cost savings metrics
        """
        # Normalize prompt
        normalized = self.normalizer.normalize(prompt)
        prompt_hash = self.normalizer.compute_hash(normalized, classifier_type, tool_config_version)
        
        # Compute embedding
        embedding = self.embedding_provider(normalized)
        
        # Compute TTL and expiration
        ttl = self._compute_ttl(predicted_type, entities, need_freshness)
        expires_at = (datetime.utcnow() + ttl).isoformat()
        created_at = datetime.utcnow().isoformat()
        
        # Store in database
        cursor = self.db.conn.cursor()
        
        embedding_json = json.dumps(embedding)
        entities_json = json.dumps(entities)
        sources_json = json.dumps(sources)
        cost_metrics_json = json.dumps(cost_metrics or {})
        
        if self.db.use_postgres:
            cursor.execute("""
                INSERT INTO cache_entries (
                    prompt_hash, prompt_original, prompt_normalized, prompt_embedding,
                    predicted_type, entities, response_text, sources,
                    created_at, expires_at, agent_version, prompt_version,
                    tool_config_version, cost_metrics
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (prompt_hash) DO UPDATE SET
                    response_text = EXCLUDED.response_text,
                    sources = EXCLUDED.sources,
                    expires_at = EXCLUDED.expires_at,
                    cost_metrics = EXCLUDED.cost_metrics
            """, (
                prompt_hash, prompt, normalized, embedding_json,
                predicted_type, entities_json, response_text, sources_json,
                created_at, expires_at, agent_version, prompt_version,
                tool_config_version, cost_metrics_json
            ))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO cache_entries (
                    prompt_hash, prompt_original, prompt_normalized, prompt_embedding,
                    predicted_type, entities, response_text, sources,
                    created_at, expires_at, agent_version, prompt_version,
                    tool_config_version, cost_metrics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_hash, prompt, normalized, embedding_json,
                predicted_type, entities_json, response_text, sources_json,
                created_at, expires_at, agent_version, prompt_version,
                tool_config_version, cost_metrics_json
            ))
        
        self.db.conn.commit()
        logger.info(f"Cached entry with hash: {prompt_hash[:8]}... (expires: {expires_at})")
    
    def _row_to_cache_entry(self, row, cursor) -> CacheEntry:
        """Convert database row to CacheEntry."""
        if self.db.use_postgres:
            row_dict = dict(row)
        else:
            row_dict = dict(zip([col[0] for col in cursor.description], row))
        
        # Parse JSON fields
        embedding = None
        if row_dict.get('prompt_embedding'):
            embedding = json.loads(row_dict['prompt_embedding']) if isinstance(row_dict['prompt_embedding'], str) else row_dict['prompt_embedding']
        
        entities = []
        if row_dict.get('entities'):
            entities = json.loads(row_dict['entities']) if isinstance(row_dict['entities'], str) else row_dict['entities']
        
        sources = []
        if row_dict.get('sources'):
            sources = json.loads(row_dict['sources']) if isinstance(row_dict['sources'], str) else row_dict['sources']
        
        cost_metrics = {}
        if row_dict.get('cost_metrics'):
            cost_metrics = json.loads(row_dict['cost_metrics']) if isinstance(row_dict['cost_metrics'], str) else row_dict['cost_metrics']
        
        return CacheEntry(
            prompt_original=row_dict.get('prompt_original', ''),
            prompt_normalized=row_dict.get('prompt_normalized', ''),
            prompt_hash=row_dict.get('prompt_hash', ''),
            prompt_embedding=embedding,
            predicted_type=row_dict.get('predicted_type', 'info'),
            entities=entities,
            response_text=row_dict.get('response_text', ''),
            sources=sources,
            created_at=row_dict.get('created_at', ''),
            expires_at=row_dict.get('expires_at', ''),
            agent_version=row_dict.get('agent_version', ''),
            prompt_version=row_dict.get('prompt_version', ''),
            tool_config_version=row_dict.get('tool_config_version', ''),
            cost_metrics=cost_metrics,
            cache_tier=row_dict.get('cache_tier', ''),
            similarity_score=row_dict.get('similarity_score', 0.0)
        )

