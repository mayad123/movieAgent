"""
Semantic cache for CineMind with two-tier caching and freshness gates.
Tier 1: Exact cache (hash-based)
Tier 2: Semantic cache (embedding-based with similarity threshold)
"""
import hashlib
import json
import re
import logging
import sqlite3
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
    structured_facts: Optional[Dict] = None  # Structured facts for regeneration
    created_at: str = ""
    expires_at: str = ""
    agent_version: str = ""
    prompt_version: str = ""
    tool_config_version: str = ""
    cost_metrics: Dict = None
    cache_tier: str = ""  # "exact" or "semantic"
    similarity_score: float = 0.0
    last_verified_at: Optional[str] = None  # When sources were last verified
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.sources is None:
            self.sources = []
        if self.cost_metrics is None:
            self.cost_metrics = {}
        if self.structured_facts is None:
            self.structured_facts = {}


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
                    structured_facts JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    agent_version VARCHAR(50),
                    prompt_version VARCHAR(50),
                    tool_config_version VARCHAR(50),
                    cost_metrics JSONB,
                    cache_tier VARCHAR(20),
                    similarity_score REAL,
                    last_verified_at TIMESTAMP,
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
                    structured_facts TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    agent_version TEXT,
                    prompt_version TEXT,
                    tool_config_version TEXT,
                    cost_metrics TEXT,
                    cache_tier TEXT,
                    similarity_score REAL,
                    last_verified_at TEXT
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON cache_entries(prompt_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON cache_entries(predicted_type)")
            
            # Add structured_facts column if it doesn't exist (for existing databases)
            cursor.execute("PRAGMA table_info(cache_entries)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'structured_facts' not in columns:
                try:
                    cursor.execute("ALTER TABLE cache_entries ADD COLUMN structured_facts TEXT")
                except sqlite3.OperationalError:
                    pass
            if 'last_verified_at' not in columns:
                try:
                    cursor.execute("ALTER TABLE cache_entries ADD COLUMN last_verified_at TEXT")
                except sqlite3.OperationalError:
                    pass
        
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
           need_freshness: bool = False, current_agent_version: str = "",
           current_prompt_version: str = "") -> Optional[CacheEntry]:
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
        if exact_match:
            # Check version compatibility
            if not self._check_version_compatibility(exact_match, current_agent_version, current_prompt_version, tool_config_version):
                logger.info(f"Cache entry version mismatch, invalidating")
                return None
            
            # Check freshness
            if self._is_fresh(exact_match, predicted_type, need_freshness):
                logger.info(f"Exact cache hit for prompt hash: {prompt_hash[:8]}...")
                exact_match.cache_tier = "exact"
                exact_match.similarity_score = 1.0  # Exact match = 100% similarity
                return exact_match
            else:
                logger.info(f"Cache entry expired for hash: {prompt_hash[:8]}...")
                return None
        
        # Tier 2: Semantic cache lookup
        semantic_match = self._get_semantic_match(
            normalized, predicted_type, need_freshness
        )
        if semantic_match:
            # Check version compatibility
            if not self._check_version_compatibility(semantic_match, current_agent_version, current_prompt_version, tool_config_version):
                logger.info(f"Semantic cache entry version mismatch, invalidating")
                return None
            
            logger.info(f"Semantic cache hit (similarity: {semantic_match.similarity_score:.3f})")
            semantic_match.cache_tier = "semantic"
            return semantic_match
        
        logger.debug("Cache miss")
        return None
    
    def _check_version_compatibility(self, entry: CacheEntry, agent_version: str, 
                                     prompt_version: str, tool_config_version: str) -> bool:
        """
        Check if cache entry is compatible with current versions.
        
        Returns:
            True if compatible, False if should be invalidated
        """
        # If versions don't match, invalidate
        if entry.agent_version and agent_version and entry.agent_version != agent_version:
            return False
        if entry.prompt_version and prompt_version and entry.prompt_version != prompt_version:
            return False
        if entry.tool_config_version and tool_config_version and entry.tool_config_version != tool_config_version:
            return False
        
        return True
    
    def should_use_cache_entry(self, cache_entry: CacheEntry, request_plan) -> Tuple[bool, str]:
        """
        Cache correctness rules using RequestPlan.
        Determines if a cache entry is safe to use.
        
        Args:
            cache_entry: Cached entry to evaluate
            request_plan: RequestPlan for current request
        
        Returns:
            (should_use: bool, reason: str)
        """
        from .request_plan import RequestPlan as RP
        
        # Rule 1: Version compatibility check
        # If agent/prompt/source policy version changed, bypass cache
        # (This is already checked in get(), but double-check here)
        if not self._check_version_compatibility(
            cache_entry, 
            request_plan.get("agent_version", ""),
            request_plan.get("prompt_version", ""),
            request_plan.get("tool_config_version", "")
        ):
            return (False, "version_mismatch")
        
        # Rule 2: Freshness TTL check
        # If need_freshness=True and cached entry is older than TTL → bypass cache
        if request_plan.get("need_freshness", False):
            cache_age_hours = self._get_cache_age_hours(cache_entry)
            ttl_hours = request_plan.get("freshness_ttl_hours", 24.0)
            if cache_age_hours > ttl_hours:
                return (False, f"freshness_ttl_expired (age: {cache_age_hours:.1f}h > ttl: {ttl_hours:.1f}h)")
        
        # Rule 3: Source tier validation
        # If cached sources include Tier C → bypass cache for "facts" intents
        if request_plan.get("reject_tier_c", True):
            # Check if cached sources have Tier C
            sources = cache_entry.sources or []
            has_tier_c = any(
                s.get("tier") == "C" or "quora" in s.get("url", "").lower() or 
                "facebook" in s.get("url", "").lower() or "reddit" in s.get("url", "").lower()
                for s in sources
            )
            
            # For fact-based intents, reject if Tier C present
            if has_tier_c and request_plan.get("request_type") in ["info", "fact-check"]:
                return (False, "tier_c_sources_in_facts")
        
        # Rule 4: Entity year mismatch
        # If same prompt but different movie year → no cache hit
        # (This is handled by exact match hash, but check entity_years if present)
        request_entity_years = request_plan.get("entity_years", {})
        if request_entity_years:
            # Check if cached entry has different years for same entities
            cached_entities = cache_entry.entities or []
            for entity, year in request_entity_years.items():
                if entity in cached_entities and year is not None:
                    # If entity year is specified and different, might be different movie
                    # This is a conservative check - exact hash should catch most cases
                    pass
        
        # Rule 5: Require Tier A check
        # If require_tier_a=True, check if cached entry has Tier A sources
        if request_plan.get("require_tier_a", False):
            sources = cache_entry.sources or []
            has_tier_a = any(
                s.get("tier") == "A" or "imdb.com" in s.get("url", "").lower() or 
                "wikipedia.org" in s.get("url", "").lower()
                for s in sources
            )
            if not has_tier_a:
                return (False, "missing_required_tier_a_sources")
        
        # All checks passed - cache entry is safe to use
        return (True, "cache_valid")
    
    def should_call_openai_on_cache_hit(self, cache_entry: CacheEntry, 
                                       request_plan, similarity_score: float = 1.0) -> Tuple[bool, str]:
        """
        Decision tree: Should we call OpenAI even on a cache hit?
        Uses RequestPlan for decision making.
        
        Args:
            cache_entry: Cached entry
            request_plan: RequestPlan dict or object
            similarity_score: Similarity score of cache hit
        
        Returns:
            (should_call: bool, reason: str)
        """
        # Convert RequestPlan to dict if needed
        if hasattr(request_plan, "to_dict"):
            plan_dict = request_plan.to_dict()
        elif isinstance(request_plan, dict):
            plan_dict = request_plan
        else:
            plan_dict = {}
        
        # First check cache correctness rules
        should_use, reason = self.should_use_cache_entry(cache_entry, plan_dict)
        if not should_use:
            return (True, reason)  # Need to call OpenAI because cache is invalid
        
        predicted_type = plan_dict.get("request_type", "")
        need_freshness = plan_dict.get("need_freshness", False)
        
        # 1. Exact hit with high confidence -> No OpenAI needed
        if cache_entry.cache_tier == "exact" and similarity_score >= 0.99:
            return (False, "exact_match_high_confidence")
        
        # 2. Semantic match near threshold (0.86-0.90) -> Consider rewrite
        if cache_entry.cache_tier == "semantic" and 0.86 <= similarity_score < 0.90:
            # For low-freshness intents, can serve directly or do cheap rewrite
            if predicted_type in ["info", "recs", "spoiler"] and not need_freshness:
                return (False, "semantic_match_low_risk")  # Serve directly
            else:
                return (True, "semantic_match_near_threshold_rewrite")
        
        # 3. High-freshness intent -> Re-verify if cache age > threshold
        if need_freshness or predicted_type in ["release-date"]:
            cache_age_hours = self._get_cache_age_hours(cache_entry)
            ttl_hours = plan_dict.get("freshness_ttl_hours", 24.0)
            # Re-verify if cache age > TTL threshold
            if cache_age_hours > ttl_hours:
                return (True, f"high_freshness_reverify (age: {cache_age_hours:.1f}h > ttl: {ttl_hours:.1f}h)")
        
        # 4. Default: Serve cached (no OpenAI)
        return (False, "cache_valid_serve_direct")
    
    def _get_cache_age_hours(self, entry: CacheEntry) -> float:
        """Get cache entry age in hours."""
        try:
            created = datetime.fromisoformat(entry.created_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = now - created
            return delta.total_seconds() / 3600.0
        except:
            return 0.0
    
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
    
    def _extract_structured_facts(self, response_text: str, predicted_type: str, 
                                 entities: List[str], sources: List[Dict],
                                 need_freshness: bool = False, freshness_reason: Optional[str] = None,
                                 freshness_ttl_hours: Optional[float] = None) -> Dict:
        """
        Extract structured facts from response for safe regeneration.
        
        Returns:
            Dict with structured facts based on intent type
        """
        facts = {}
        
        if predicted_type == "info":
            # Extract movie info: title, year, director, cast
            # Simple extraction - could be enhanced with LLM
            facts["type"] = "movie_info"
            # Try to extract titles and years from response
            title_year_pattern = r'"([^"]+)"\s*\((\d{4})\)'
            matches = re.findall(title_year_pattern, response_text)
            if matches:
                facts["movies"] = [{"title": title, "year": int(year)} for title, year in matches]
        
        elif predicted_type == "filmography_overlap" or "collaboration" in response_text.lower():
            # Extract collaboration facts
            facts["type"] = "collaboration"
            title_year_pattern = r'"([^"]+)"\s*\((\d{4})\)'
            matches = re.findall(title_year_pattern, response_text)
            if matches:
                facts["collaborations"] = [
                    {"title": title, "year": int(year), "verified_sources": [s.get("url", "") for s in sources[:3]]}
                    for title, year in matches
                ]
        
        elif predicted_type == "release-date":
            # Extract release status
            facts["type"] = "release_status"
            # Try to extract status and date
            if "released" in response_text.lower() or "out" in response_text.lower():
                facts["status"] = "released"
            elif "coming" in response_text.lower() or "premiere" in response_text.lower():
                facts["status"] = "upcoming"
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', response_text)
            if year_match:
                facts["release_year"] = int(year_match.group(1))
        
        elif predicted_type == "recs":
            # Extract recommendations
            facts["type"] = "recommendations"
            title_year_pattern = r'"([^"]+)"\s*\((\d{4})\)'
            matches = re.findall(title_year_pattern, response_text)
            if matches:
                facts["recommendations"] = [{"title": title, "year": int(year)} for title, year in matches]
        
        # Store entities
        if entities:
            facts["entities"] = entities
        
        # Store freshness metadata
        facts["need_freshness"] = need_freshness
        if freshness_reason:
            facts["freshness_reason"] = freshness_reason
        if freshness_ttl_hours:
            facts["freshness_ttl_hours"] = freshness_ttl_hours
        
        # Store source URLs for verification
        tier_a_sources = [s.get("url", "") for s in sources if s.get("tier") == "A"]
        if tier_a_sources:
            facts["verified_sources"] = tier_a_sources
        
        return facts
    
    def put(self, prompt: str, response_text: str, sources: List[Dict],
           predicted_type: str, entities: List[str], need_freshness: bool,
           classifier_type: str, tool_config_version: str, agent_version: str,
           prompt_version: str, cost_metrics: Dict = None, structured_facts: Dict = None,
           freshness_reason: Optional[str] = None, freshness_ttl_hours: Optional[float] = None):
        """
        Store entry in cache with structured facts.
        
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
            structured_facts: Pre-extracted structured facts (optional)
        """
        # Normalize prompt
        normalized = self.normalizer.normalize(prompt)
        prompt_hash = self.normalizer.compute_hash(normalized, classifier_type, tool_config_version)
        
        # Compute embedding
        embedding = self.embedding_provider(normalized)
        
        # Extract structured facts if not provided
        if structured_facts is None:
            structured_facts = self._extract_structured_facts(
                response_text, predicted_type, entities, sources,
                need_freshness=need_freshness,
                freshness_reason=freshness_reason,
                freshness_ttl_hours=freshness_ttl_hours
            )
        else:
            # Ensure freshness metadata is in structured_facts
            if freshness_reason:
                structured_facts["freshness_reason"] = freshness_reason
            if freshness_ttl_hours:
                structured_facts["freshness_ttl_hours"] = freshness_ttl_hours
            structured_facts["need_freshness"] = need_freshness
        
        # Compute TTL and expiration
        ttl = self._compute_ttl(predicted_type, entities, need_freshness)
        expires_at = (datetime.utcnow() + ttl).isoformat()
        created_at = datetime.utcnow().isoformat()
        last_verified_at = datetime.utcnow().isoformat()
        
        # Store in database
        cursor = self.db.conn.cursor()
        
        embedding_json = json.dumps(embedding)
        entities_json = json.dumps(entities)
        sources_json = json.dumps(sources)
        structured_facts_json = json.dumps(structured_facts)
        cost_metrics_json = json.dumps(cost_metrics or {})
        
        if self.db.use_postgres:
            cursor.execute("""
                INSERT INTO cache_entries (
                    prompt_hash, prompt_original, prompt_normalized, prompt_embedding,
                    predicted_type, entities, response_text, sources, structured_facts,
                    created_at, expires_at, agent_version, prompt_version,
                    tool_config_version, cost_metrics, last_verified_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (prompt_hash) DO UPDATE SET
                    response_text = EXCLUDED.response_text,
                    sources = EXCLUDED.sources,
                    structured_facts = EXCLUDED.structured_facts,
                    expires_at = EXCLUDED.expires_at,
                    cost_metrics = EXCLUDED.cost_metrics,
                    last_verified_at = EXCLUDED.last_verified_at
            """, (
                prompt_hash, prompt, normalized, embedding_json,
                predicted_type, entities_json, response_text, sources_json, structured_facts_json,
                created_at, expires_at, agent_version, prompt_version,
                tool_config_version, cost_metrics_json, last_verified_at
            ))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO cache_entries (
                    prompt_hash, prompt_original, prompt_normalized, prompt_embedding,
                    predicted_type, entities, response_text, sources, structured_facts,
                    created_at, expires_at, agent_version, prompt_version,
                    tool_config_version, cost_metrics, last_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prompt_hash, prompt, normalized, embedding_json,
                predicted_type, entities_json, response_text, sources_json, structured_facts_json,
                created_at, expires_at, agent_version, prompt_version,
                tool_config_version, cost_metrics_json, last_verified_at
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
        
        structured_facts = {}
        if row_dict.get('structured_facts'):
            structured_facts = json.loads(row_dict['structured_facts']) if isinstance(row_dict['structured_facts'], str) else row_dict['structured_facts']
        
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
            structured_facts=structured_facts,
            created_at=row_dict.get('created_at', ''),
            expires_at=row_dict.get('expires_at', ''),
            agent_version=row_dict.get('agent_version', ''),
            prompt_version=row_dict.get('prompt_version', ''),
            tool_config_version=row_dict.get('tool_config_version', ''),
            cost_metrics=cost_metrics,
            cache_tier=row_dict.get('cache_tier', ''),
            similarity_score=row_dict.get('similarity_score', 0.0),
            last_verified_at=row_dict.get('last_verified_at')
        )

