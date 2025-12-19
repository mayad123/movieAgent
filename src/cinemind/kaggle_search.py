"""
Kaggle dataset search module for IMDB dataset.

This module provides functionality to search the IMDB dataset from Kaggle
and check if results are highly correlated with user queries.
"""
import os
import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

# Default correlation threshold (0.0 to 1.0)
# Higher values mean stricter matching
DEFAULT_CORRELATION_THRESHOLD = 0.7


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
        
        # Calculate correlation for each row
        correlations = []
        
        for idx, row in df.iterrows():
            try:
                correlation = self._calculate_correlation(query, row.to_dict())
                if correlation > 0.0:  # Only store non-zero correlations
                    correlations.append({
                        "index": idx,
                        "correlation": correlation,
                        "row_data": row.to_dict()
                    })
            except Exception as e:
                logger.warning(f"Error calculating correlation for row {idx}: {e}")
                continue
        
        # Sort by correlation (highest first)
        correlations.sort(key=lambda x: x["correlation"], reverse=True)
        
        # Convert to result format
        results = []
        max_correlation = 0.0
        
        for item in correlations[:max_results]:
            correlation = item["correlation"]
            row_data = item["row_data"]
            
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
                "score": correlation,
                "source": "kaggle_imdb",
                "correlation": correlation,
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

