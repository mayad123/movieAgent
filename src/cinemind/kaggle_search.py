"""
Kaggle dataset search module for IMDB dataset.

This module provides functionality to search the IMDB dataset from Kaggle
and check if results are highly correlated with user queries.

Optimization: Two-stage pipeline with fast candidate retrieval + expensive correlation scorer.
"""
import os
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

# Default correlation threshold (0.0 to 1.0)
# Higher values mean stricter matching
DEFAULT_CORRELATION_THRESHOLD = 0.7

# Stage A: Number of candidates to retrieve for Stage B correlation scoring
STAGE_A_CANDIDATE_LIMIT = 200


def normalize_title(title: str) -> str:
    """
    Normalize a movie title for matching.
    
    Removes:
    - Special characters
    - Extra whitespace
    - Converts to lowercase
    - Removes common articles (the, a, an)
    
    Args:
        title: Original title
        
    Returns:
        Normalized title
    """
    if not title or not isinstance(title, str):
        return ""
    
    # Convert to lowercase
    normalized = title.lower().strip()
    
    # Remove special characters (keep letters, numbers, spaces)
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove leading articles (optional - can be kept for some matching strategies)
    # normalized = re.sub(r'^(the|a|an)\s+', '', normalized).strip()
    
    return normalized


def tokenize(title: str) -> Set[str]:
    """
    Tokenize a title into a set of words.
    
    Args:
        title: Title string
        
    Returns:
        Set of token strings
    """
    normalized = normalize_title(title)
    tokens = set(normalized.split())
    # Filter out very short tokens
    return {t for t in tokens if len(t) > 2}


class KaggleDatasetSearcher:
    """Searches the IMDB dataset from Kaggle and checks correlation with queries."""
    
    def __init__(self, dataset_path: str = "", correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD):
        """
        Initialize Kaggle dataset searcher.
        
        Args:
            dataset_path: Path to the dataset file within the Kaggle dataset.
                         If empty, will try to load default files.
            correlation_threshold: Minimum correlation score (0.0-1.0) to consider
                                  results as "highly correlated"
        """
        self.dataset_path = dataset_path
        self.correlation_threshold = correlation_threshold
        self._dataset = None
        self._dataset_loaded = False
        self.kaggle_dataset_name = "parthdande/imdb-dataset-2024-updated"
        
        # Stage A: Precomputed normalized title index (built once on init)
        self._normalized_title_index: Dict[int, str] = {}  # row_index -> normalized_title
        self._token_index: Dict[str, Set[int]] = {}  # token -> set of row_indices
        self._title_index_loaded = False
    
    def _load_dataset(self) -> Optional[pd.DataFrame]:
        """Load the Kaggle dataset. Caches the result."""
        if self._dataset_loaded and self._dataset is not None:
            return self._dataset
        
        try:
            import kagglehub
            from kagglehub import KaggleDatasetAdapter
            from pathlib import Path
            import os
            
            logger.info(f"Loading Kaggle dataset: {self.kaggle_dataset_name}")
            
            # If dataset_path is provided, use it
            if self.dataset_path:
                df = kagglehub.load_dataset(
                    KaggleDatasetAdapter.PANDAS,
                    self.kaggle_dataset_name,
                    self.dataset_path,
                )
            else:
                # Auto-detect: download dataset and find CSV files
                try:
                    # Download dataset to get the path
                    dataset_path = kagglehub.dataset_download(self.kaggle_dataset_name)
                    dataset_dir = Path(dataset_path)
                    
                    # Find all CSV files
                    csv_files = sorted(list(dataset_dir.glob("*.csv")))
                    
                    if not csv_files:
                        logger.error(f"No CSV files found in dataset directory: {dataset_dir}")
                        return None
                    
                    # Try to load the main dataset file first (usually the first one or one with "Dataset" in name)
                    main_file = None
                    for csv_file in csv_files:
                        if "Dataset" in csv_file.name and "Dataset_2" not in csv_file.name and "Dataset_3" not in csv_file.name:
                            main_file = csv_file
                            break
                    
                    # If no main file found, use the first one
                    if not main_file:
                        main_file = csv_files[0]
                    
                    file_path = main_file.name
                    logger.info(f"Loading dataset file: {file_path}")
                    
                    # Load the dataset using the file path
                    df = kagglehub.load_dataset(
                        KaggleDatasetAdapter.PANDAS,
                        self.kaggle_dataset_name,
                        file_path,
                    )
                    
                    # Optionally: combine multiple CSV files if they exist and are related
                    # For now, we'll just use the main file
                    
                except Exception as e:
                    logger.error(f"Failed to auto-detect and load dataset file: {e}")
                    # Fallback: try common file names
                    common_files = [
                        "IMDb_Dataset.csv",
                        "imdb_movies.csv",
                        "movies.csv",
                        "imdb.csv",
                        "dataset.csv"
                    ]
                    
                    df = None
                    for file_path in common_files:
                        try:
                            logger.info(f"Trying fallback file: {file_path}")
                            df = kagglehub.load_dataset(
                                KaggleDatasetAdapter.PANDAS,
                                self.kaggle_dataset_name,
                                file_path,
                            )
                            if df is not None and not df.empty:
                                logger.info(f"Successfully loaded {file_path}")
                                break
                        except Exception as e2:
                            logger.debug(f"Failed to load {file_path}: {e2}")
                            continue
                    
                    if df is None or df.empty:
                        raise Exception(f"Could not load dataset. Tried: {common_files}")
            
            if df is None or df.empty:
                logger.warning("Loaded dataset is empty")
                return None
            
            self._dataset = df
            self._dataset_loaded = True
            logger.info(f"Loaded dataset with {len(df)} records. Columns: {list(df.columns)}")
            
            # Build normalized title index
            self._build_title_index()
            
            return df
            
        except ImportError:
            logger.error("kagglehub not installed. Install with: pip install kagglehub[pandas-datasets]")
            return None
        except Exception as e:
            logger.error(f"Failed to load Kaggle dataset: {e}")
            return None
    
    def _extract_query_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract entities from query (movie titles, people names, etc.).
        
        This is a simple extraction - could be enhanced with NER or LLM.
        """
        entities = {
            "movies": [],
            "people": [],
            "keywords": []
        }
        
        query_lower = query.lower()
        
        # Simple keyword extraction - look for capitalized words/phrases
        # This is a heuristic approach
        words = query.split()
        
        # Look for movie titles (capitalized phrases)
        title_patterns = [
            r'"([^"]+)"',  # Quoted titles
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # Capitalized phrases
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                if len(match.split()) >= 1:  # At least one word
                    entities["movies"].append(match)
        
        # Extract common movie-related keywords
        movie_keywords = [
            "directed", "director", "released", "release", "cast", "actor", "actress",
            "movie", "film", "cinema", "who", "when", "what", "where", "year"
        ]
        
        for keyword in movie_keywords:
            if keyword in query_lower:
                entities["keywords"].append(keyword)
        
        # Try to extract person names (words after "who", "directed by", etc.)
        person_indicators = ["who", "directed by", "director", "actor", "actress", "starring"]
        for indicator in person_indicators:
            if indicator in query_lower:
                idx = query_lower.find(indicator)
                # Get words after the indicator
                after = query[idx + len(indicator):].strip()
                # Simple heuristic: capitalized words are potential names
                potential_names = [w for w in after.split() if w and w[0].isupper()]
                if potential_names:
                    entities["people"].extend(potential_names[:2])  # Limit to 2
        
        return entities
    
    def _build_title_index(self) -> None:
        """
        Build normalized title index for fast candidate retrieval.
        Called once when dataset is loaded.
        """
        if self._title_index_loaded:
            return
        
        df = self._dataset
        if df is None or df.empty:
            return
        
        logger.info("Building normalized title index for fast candidate retrieval...")
        
        # Find title column
        title_cols = ["Title", "title", "movie_title", "name", "Movie"]
        title_col = None
        for col in title_cols:
            if col in df.columns:
                title_col = col
                break
        
        if not title_col:
            # Fallback: use first string column
            for col in df.columns:
                if df[col].dtype == 'object':
                    title_col = col
                    break
        
        if not title_col:
            logger.warning("Could not find title column for indexing")
            return
        
        # Build indexes
        self._normalized_title_index = {}
        self._token_index = {}
        
        for idx, row in df.iterrows():
            title = row.get(title_col)
            if pd.notna(title) and title:
                title_str = str(title)
                normalized = normalize_title(title_str)
                if normalized:
                    self._normalized_title_index[idx] = normalized
                    # Build token index for fast token overlap matching
                    tokens = tokenize(title_str)
                    for token in tokens:
                        if token not in self._token_index:
                            self._token_index[token] = set()
                        self._token_index[token].add(idx)
        
        self._title_index_loaded = True
        logger.info(f"Built title index: {len(self._normalized_title_index)} titles, {len(self._token_index)} unique tokens")
    
    def _stage_a_candidate_retrieval(self, query: str, top_n: int = STAGE_A_CANDIDATE_LIMIT) -> List[Tuple[int, float, str]]:
        """
        Stage A: Fast candidate retrieval using title normalization + simple lookup.
        
        Uses multiple strategies:
        1. Exact normalized title match
        2. Substring match
        3. Token overlap (fast token-based matching)
        4. Optional fuzzy matching (if rapidfuzz is available)
        
        Args:
            query: Search query
            top_n: Maximum number of candidates to return
            
        Returns:
            List of (row_index, match_score, match_reason) tuples, sorted by match_score descending
        """
        if not self._title_index_loaded:
            self._build_title_index()
        
        query_normalized = normalize_title(query)
        query_tokens = tokenize(query)
        
        candidates: Dict[int, Tuple[float, str]] = {}  # row_index -> (score, reason)
        
        # Strategy 1: Exact normalized title match (highest priority)
        for row_idx, normalized_title in self._normalized_title_index.items():
            if query_normalized == normalized_title:
                candidates[row_idx] = (1.0, "exact_title")
            elif query_normalized in normalized_title or normalized_title in query_normalized:
                # Substring match (one contains the other)
                if row_idx not in candidates:  # Don't override exact matches
                    candidates[row_idx] = (0.9, "substring_match")
        
        # Strategy 2: Token overlap (high priority, fast)
        if query_tokens:
            token_matches: Dict[int, int] = {}  # row_index -> number of matching tokens
            for token in query_tokens:
                if token in self._token_index:
                    for row_idx in self._token_index[token]:
                        token_matches[row_idx] = token_matches.get(row_idx, 0) + 1
            
            # Calculate token overlap score
            for row_idx, match_count in token_matches.items():
                if row_idx not in candidates:  # Don't override exact/substring matches
                    overlap_score = match_count / len(query_tokens)
                    if overlap_score >= 0.3:  # At least 30% token overlap
                        candidates[row_idx] = (overlap_score * 0.8, "token_overlap")  # Max 0.8 for token overlap
        
        # Strategy 3: Optional fuzzy matching with rapidfuzz (if available)
        try:
            from rapidfuzz import fuzz, process
            # Use rapidfuzz to find fuzzy matches if we don't have enough candidates
            if len(candidates) < top_n:
                # Extract titles and indices for fuzzy matching
                title_list = [(idx, normalized) for idx, normalized in self._normalized_title_index.items() if idx not in candidates]
                
                if title_list:
                    # Use rapidfuzz to get best matches
                    # Extract just the titles for process.extract
                    titles_only = [t[1] for t in title_list]
                    matches = process.extract(query_normalized, titles_only, limit=min(top_n - len(candidates), len(titles_only)), scorer=fuzz.ratio)
                    
                    # Map back to row indices
                    for match_title, score, _ in matches:
                        # Find the row index for this title
                        for idx, norm_title in title_list:
                            if norm_title == match_title and idx not in candidates:
                                # Normalize rapidfuzz score (0-100) to 0.0-1.0, then scale to max 0.7 for fuzzy
                                normalized_score = (score / 100.0) * 0.7
                                if normalized_score >= 0.5:  # Only include if similarity >= 50%
                                    candidates[idx] = (normalized_score, "fuzzy_match")
                                break
        except ImportError:
            # rapidfuzz not available, skip fuzzy matching
            pass
        
        # Strategy 4: Substring matching on individual words (lower priority fallback)
        if len(candidates) < top_n:
            query_words = [w for w in query_normalized.split() if len(w) > 3]
            for word in query_words:
                if len(candidates) >= top_n:
                    break
                for row_idx, normalized_title in self._normalized_title_index.items():
                    if row_idx not in candidates and word in normalized_title:
                        candidates[row_idx] = (0.5, "substring_match")
        
        # Sort by score and return top N
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1][0], reverse=True)
        return [(idx, score, reason) for idx, (score, reason) in sorted_candidates[:top_n]]
    
    def _calculate_correlation(self, query: str, dataset_row: Dict) -> float:
        """
        Calculate correlation score between query and a dataset row.
        
        Args:
            query: User query
            dataset_row: A row from the dataset (as dict)
            
        Returns:
            Correlation score between 0.0 and 1.0
        """
        query_lower = query.lower()
        query_entities = self._extract_query_entities(query)
        
        # Convert dataset row to searchable text
        row_text = " ".join([str(v) for v in dataset_row.values() if pd.notna(v)]).lower()
        
        score = 0.0
        max_score = 0.0
        
        # Check for movie title matches (high weight)
        for movie in query_entities["movies"]:
            max_score += 0.4
            movie_lower = movie.lower()
            if movie_lower in row_text:
                # Exact match gets full points
                score += 0.4
            elif any(word in row_text for word in movie_lower.split() if len(word) > 3):
                # Partial match gets half points
                score += 0.2
        
        # Check for person name matches (medium weight)
        for person in query_entities["people"]:
            max_score += 0.3
            person_lower = person.lower()
            if person_lower in row_text:
                score += 0.3
            elif any(word in row_text for word in person_lower.split() if len(word) > 3):
                score += 0.15
        
        # Check for keyword matches (lower weight)
        for keyword in query_entities["keywords"]:
            max_score += 0.1
            if keyword in row_text:
                score += 0.1
        
        # Check for direct query term matches (for generic queries)
        query_words = [w for w in query_lower.split() if len(w) > 3]
        if query_words:
            max_score += 0.2
            matches = sum(1 for word in query_words if word in row_text)
            score += 0.2 * (matches / len(query_words))
        
        # Normalize score
        if max_score > 0:
            normalized_score = score / max_score
        else:
            # Fallback: check if any query words appear
            query_words = [w for w in query_lower.split() if len(w) > 3]
            if query_words:
                matches = sum(1 for word in query_words if word in row_text)
                normalized_score = matches / len(query_words) if query_words else 0.0
            else:
                normalized_score = 0.0
        
        return min(1.0, normalized_score)
    
    def search(self, query: str, max_results: int = 5) -> Tuple[List[Dict], float]:
        """
        Search the Kaggle dataset for results correlated with the query.
        
        Uses two-stage pipeline:
        - Stage A: Fast candidate retrieval using normalized title lookup
        - Stage B: Expensive correlation scorer on top N candidates
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            Tuple of (results_list, max_correlation_score)
            - results_list: List of dictionaries with search results
            - max_correlation_score: Highest correlation score found (0.0-1.0)
        """
        df = self._load_dataset()
        
        if df is None or df.empty:
            logger.warning("Kaggle dataset not available or empty")
            return [], 0.0
        
        # Stage A: Fast candidate retrieval
        candidates = self._stage_a_candidate_retrieval(query, top_n=STAGE_A_CANDIDATE_LIMIT)
        
        if not candidates:
            logger.info(f"No candidates found in Stage A for query: {query}")
            return [], 0.0
        
        logger.debug(f"Stage A found {len(candidates)} candidates, running Stage B correlation on top {min(len(candidates), STAGE_A_CANDIDATE_LIMIT)}")
        
        # Stage B: Run expensive correlation scorer only on top N candidates
        correlations = []
        
        for row_idx, stage_a_score, match_reason in candidates:
            try:
                row = df.iloc[row_idx]
                row_dict = row.to_dict()
                
                # Run expensive correlation scorer
                correlation = self._calculate_correlation(query, row_dict)
                
                # Combine Stage A score (0.0-1.0) with Stage B correlation (0.0-1.0)
                # Weight: 30% Stage A, 70% Stage B (Stage B is more accurate)
                combined_score = (stage_a_score * 0.3) + (correlation * 0.7)
                
                if combined_score > 0.0:  # Only store non-zero correlations
                    correlations.append({
                        "index": row_idx,
                        "correlation": correlation,
                        "combined_score": combined_score,
                        "match_reason": match_reason,
                        "stage_a_score": stage_a_score,
                        "row_data": row_dict
                    })
            except Exception as e:
                logger.warning(f"Error calculating correlation for row {row_idx}: {e}")
                continue
        
        # Sort by combined score (highest first)
        correlations.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Convert to result format
        results = []
        max_correlation = 0.0
        
        for item in correlations[:max_results]:
            correlation = item["correlation"]
            combined_score = item["combined_score"]
            match_reason = item.get("match_reason", "correlation")
            stage_a_score = item.get("stage_a_score", 0.0)
            row_data = item["row_data"]
            
            # Use combined_score for final ranking, but report correlation as the score
            # (to preserve backward compatibility with existing code)
            if correlation > max_correlation:
                max_correlation = correlation
            
            if correlation > max_correlation:
                max_correlation = correlation
            
            # Format result similar to Tavily format
            # Try to extract title and other fields based on dataset columns
            title = ""
            content = ""
            
            # Common column names in IMDB datasets (prioritized order)
            title_cols = ["Title", "title", "movie_title", "name", "Movie"]
            
            for col in title_cols:
                if col in row_data and pd.notna(row_data[col]):
                    title = str(row_data[col])
                    break
            
            # If no title found, use first non-null string column
            if not title:
                for col, val in row_data.items():
                    if isinstance(val, str) and val.strip():
                        title = val[:100]  # Limit length
                        break
            
            # Build structured content with important fields in readable format
            # Priority order for IMDB dataset: Director, Year, Genre, Star Cast, Rating, etc.
            priority_fields = {
                "Director": ["Director", "director", "Directed By"],
                "Year": ["Year", "year", "Release Year", "Release Date"],
                "Genre": ["Genre", "genre", "genres", "Categories"],
                "Star Cast": ["Star Cast", "Cast", "cast", "Actors", "actors", "Stars"],
                "Rating": ["IMDb Rating", "Rating", "rating", "IMDB Rating", "Score"],
                "MetaScore": ["MetaScore", "metascore", "Metascore"],
                "Duration": ["Duration (minutes)", "Duration", "duration", "Runtime", "runtime"],
                "Certificates": ["Certificates", "certificate", "Rating", "MPAA Rating"]
            }
            
            content_lines = []
            used_cols = set(title_cols)
            
            # Add priority fields in order
            for field_name, possible_cols in priority_fields.items():
                for col in possible_cols:
                    if col in row_data and pd.notna(row_data[col]):
                        val = row_data[col]
                        if val:  # Only add non-empty values
                            # Format Star Cast field: split by capitalization if names are concatenated
                            if field_name == "Star Cast" and isinstance(val, str):
                                # Try to detect concatenated names (capital letters without spaces before them)
                                import re
                                # Add space before capital letters that follow lowercase
                                formatted_val = re.sub(r'(?<=[a-z])(?=[A-Z])', ', ', val)
                                # Also handle cases where names might be separated by other patterns
                                if ',' not in formatted_val and ' and ' not in formatted_val.lower():
                                    # Try to split on patterns like "Name1Name2" -> "Name1, Name2"
                                    formatted_val = re.sub(r'([a-z])([A-Z])', r'\1, \2', formatted_val)
                                val = formatted_val
                            content_lines.append(f"{field_name}: {val}")
                            used_cols.add(col)
                            break
            
            # Add any remaining fields that weren't used (max 3 more to keep it readable)
            remaining_count = 0
            for col, val in row_data.items():
                if col not in used_cols and pd.notna(val) and val:
                    if isinstance(val, (str, int, float)):
                        content_lines.append(f"{col}: {val}")
                        remaining_count += 1
                        if remaining_count >= 3:  # Limit additional fields
                            break
            
            # Join with newlines for better readability, but truncate total length
            content = "\n".join(content_lines)
            if len(content) > 800:  # Truncate if too long
                content = content[:800] + "..."
            
            results.append({
                "title": title or "IMDB Dataset Result",
                "url": "",  # No URL for dataset results
                "content": content,  # Content already truncated above if needed
                "score": correlation,  # Use correlation for backward compatibility
                "source": "kaggle_imdb",
                "correlation": correlation,
                "match_score": combined_score,  # Combined Stage A + Stage B score
                "match_reason": match_reason,  # "exact_title", "token_overlap", "substring_match", etc.
                "stage_a_score": stage_a_score,  # Fast lookup score from Stage A
                "published_date": None,
                "row_index": item["index"]
            })
        
        logger.info(f"Kaggle search returned {len(results)} results (max correlation: {max_correlation:.3f})")
        
        return results, max_correlation
    
    def is_highly_correlated(self, query: str, max_results: int = 5) -> Tuple[bool, List[Dict], float]:
        """
        Check if Kaggle dataset has highly correlated results for the query.
        
        Args:
            query: Search query
            max_results: Maximum number of results to check
            
        Returns:
            Tuple of (is_highly_correlated, results_list, max_correlation_score)
        """
        results, max_correlation = self.search(query, max_results)
        
        is_correlated = max_correlation >= self.correlation_threshold
        
        if is_correlated:
            logger.info(f"Kaggle dataset has highly correlated results (score: {max_correlation:.3f} >= {self.correlation_threshold})")
        else:
            logger.info(f"Kaggle dataset results not highly correlated (score: {max_correlation:.3f} < {self.correlation_threshold})")
        
        return is_correlated, results, max_correlation

