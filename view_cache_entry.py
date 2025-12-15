"""
View cache entry details for a specific query.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cinemind.database import Database
from cinemind.cache import PromptNormalizer
import json


def view_cache_entry(query: str):
    """View cache entry for a specific query."""
    db = Database()
    normalizer = PromptNormalizer()
    
    # Normalize the query
    normalized = normalizer.normalize(query)
    
    # Compute hash (we need classifier_type and tool_config_version)
    # Try v4 first (what we used in the test), then fallback to config
    import cinemind.config as config
    prompt_version = getattr(config, 'PROMPT_VERSION', 'v1')
    # Check if v4 was set (from test script)
    if prompt_version == 'v1':
        # Try v4 as that's what the test used
        prompt_version = 'v4'
    
    classifier_type = "hybrid"
    tool_config_version = f"cine_prompt_{prompt_version}"
    prompt_hash = normalizer.compute_hash(normalized, classifier_type, tool_config_version)
    
    print("=" * 80)
    print("CACHE ENTRY LOOKUP")
    print("=" * 80)
    print(f"\nQuery: {query}")
    print(f"Normalized: {normalized}")
    print(f"Hash: {prompt_hash[:16]}...")
    print(f"Tool Config: {tool_config_version}")
    
    # Query cache
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM cache_entries WHERE prompt_hash = ?", (prompt_hash,))
    row = cursor.fetchone()
    
    if row:
        row_dict = dict(zip([col[0] for col in cursor.description], row))
        
        print("\n" + "=" * 80)
        print("CACHE ENTRY FOUND")
        print("=" * 80)
        print(f"Original Prompt: {row_dict.get('prompt_original', 'N/A')}")
        print(f"Normalized Prompt: {row_dict.get('prompt_normalized', 'N/A')}")
        print(f"Predicted Type: {row_dict.get('predicted_type', 'N/A')}")
        print(f"Created: {row_dict.get('created_at', 'N/A')}")
        print(f"Expires: {row_dict.get('expires_at', 'N/A')}")
        
        # Parse entities
        entities = row_dict.get('entities')
        if entities:
            if isinstance(entities, str):
                entities = json.loads(entities)
            print(f"Entities: {entities}")
        
        # Show response
        response_text = row_dict.get('response_text', '')
        if response_text:
            print("\n" + "=" * 80)
            print("CACHED RESPONSE")
            print("=" * 80)
            print(response_text)
        
        # Show sources
        sources = row_dict.get('sources')
        if sources:
            if isinstance(sources, str):
                sources = json.loads(sources)
            print("\n" + "=" * 80)
            print("SOURCES")
            print("=" * 80)
            for i, src in enumerate(sources[:5], 1):
                print(f"{i}. {src.get('title', 'N/A')}")
                print(f"   {src.get('url', 'N/A')}")
        
        # Show cost metrics
        cost_metrics = row_dict.get('cost_metrics')
        if cost_metrics:
            if isinstance(cost_metrics, str):
                cost_metrics = json.loads(cost_metrics)
            print("\n" + "=" * 80)
            print("COST METRICS")
            print("=" * 80)
            print(f"Saved Cost: ${cost_metrics.get('saved_cost', 0):.6f}")
            print(f"Original Cost: ${cost_metrics.get('original_cost', 0):.6f}")
    else:
        print("\n[NOT FOUND] No cache entry found for this query.")
        print("This means the query hasn't been cached yet or the hash doesn't match.")
    
    db.close()


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "Name three movies with both Robert De Niro and Al Pacino, ordered by release year."
    view_cache_entry(query)

