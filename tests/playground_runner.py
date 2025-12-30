"""
Offline playground runner for CineMind agent.

Allows arbitrary user prompts to be executed through the existing CineMind agent
using the FakeLLM setup, exactly as the offline end-to-end tests do.

This runner:
- Uses FakeLLMClient (no OpenAI API calls)
- Always disables live data (no Tavily/other API calls)
- Reuses the exact CineMind execution path from offline e2e tests
- Bypasses planning via request_type parameter (same as tests)

Usage:
    python -m tests.playground_runner "Who directed The Matrix?"
    python -m tests.playground_runner "Who directed The Matrix?" --request-type info
    python -m tests.playground_runner  # Interactive mode
"""
import asyncio
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to path so we can import cinemind
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from cinemind.agent import CineMind
from cinemind.llm_client import FakeLLMClient


def auto_detect_request_type(query: str) -> Optional[str]:
    """
    Auto-detect request_type from query using simple pattern matching.
    
    This helps bypass planning when request_type is not explicitly provided.
    Uses the same patterns as FakeLLMClient for consistency.
    
    Args:
        query: User query string
        
    Returns:
        Detected request_type or None
    """
    query_lower = query.lower()
    
    # Priority order matters (most specific first)
    if "compare" in query_lower:
        return "comparison"
    elif "recommend" in query_lower or ("similar" in query_lower and "movie" in query_lower) or ("like" in query_lower and "movie" in query_lower):
        return "recs"
    elif "where" in query_lower and ("watch" in query_lower or "stream" in query_lower):
        return "info"  # where_to_watch uses info request_type
    elif "available" in query_lower or "streaming" in query_lower:
        return "info"  # availability uses info request_type
    elif "director" in query_lower or "directed by" in query_lower or "directed" in query_lower:
        return "info"
    elif "cast" in query_lower or "starred" in query_lower or "who was in" in query_lower:
        return "info"
    elif "release" in query_lower or "when was" in query_lower or "came out" in query_lower:
        return "release-date"
    elif "runtime" in query_lower or "how long" in query_lower or "length" in query_lower:
        return "info"
    else:
        # Default to "info" for most queries
        return "info"


async def run_playground(
    user_query: str,
    request_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a user query through CineMind using FakeLLM (offline).
    
    Args:
        user_query: Free-form user query string
        request_type: Optional request type to bypass planning (e.g., "info", "recs")
                     If not provided, auto-detected from query using pattern matching
    
    Returns:
        Full structured result from CineMind agent
    """
    # Auto-detect request_type if not provided (helps bypass planning)
    if not request_type:
        request_type = auto_detect_request_type(user_query)
    
    # Create FakeLLM client (same as offline e2e tests)
    fake_llm_client = FakeLLMClient()
    
    # Create CineMind agent with FakeLLM (same setup as offline e2e tests)
    # Disable observability to avoid DB dependencies
    agent = CineMind(
        openai_api_key="fake-key",
        enable_observability=False,
        llm_client=fake_llm_client
    )
    
    try:
        # Execute query through agent (same path as offline e2e tests)
        # Always disable live data to avoid external API calls
        # Use request_type to bypass planning (same as tests)
        result = await agent.search_and_analyze(
            user_query=user_query,
            use_live_data=False,  # Always disabled - no external API calls
            request_type=request_type  # Bypass planning (same as offline e2e tests)
        )
        
        return result
    
    finally:
        # Clean up agent resources
        await agent.close()


async def main():
    """Command-line interface for playground runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Offline playground runner for CineMind - execute queries with FakeLLM (no API calls)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Who directed The Matrix?"
  %(prog)s "Who directed The Matrix?" --request-type info
  %(prog)s "Recommend movies like The Matrix" --request-type recs
  %(prog)s "Compare The Matrix and Inception" --request-type comparison
  %(prog)s "When was Dune released?" --request-type release-date
        """
    )
    
    parser.add_argument(
        "query",
        nargs="*",
        help="User query string"
    )
    parser.add_argument(
        "--request-type",
        choices=["info", "recs", "comparison", "release-date"],
        help="Request type to use (info, recs, comparison, release-date). Auto-detected if not provided."
    )
    
    args = parser.parse_args()
    
    # Get user query
    if args.query:
        user_query = " ".join(args.query)
    else:
        # Interactive mode
        print("CineMind Offline Playground")
        print("=" * 60)
        print("Execute queries through CineMind using FakeLLM (no API calls)")
        print("Planning is auto-bypassed using request_type detection")
        print("Type 'exit' to quit")
        print("\nOptional: Use --request-type <type> to override auto-detection")
        print("  Examples: --request-type info, --request-type recs, --request-type release-date")
        print("=" * 60)
        print()
        
        while True:
            try:
                query = input("[Query]: ").strip()
                
                if query.lower() in ['exit', 'quit', 'q']:
                    break
                
                if not query:
                    continue
                
                # Parse request_type from query if provided
                request_type = args.request_type
                if "--request-type" in query:
                    parts = query.split("--request-type")
                    query = parts[0].strip()
                    if len(parts) > 1:
                        request_type = parts[1].strip().split()[0] if parts[1].strip() else None
                
                # Auto-detect if not provided
                detected_type = auto_detect_request_type(query) if not request_type else None
                if detected_type:
                    print(f"\n[Auto-detected request_type: {detected_type}]")
                
                print("\n[Executing through CineMind (offline, FakeLLM, no API calls)...]")
                result = await run_playground(query, request_type=request_type)
                
                # Display formatted output
                print("\n" + "=" * 60)
                print("RESPONSE:")
                print("=" * 60)
                print(result.get("response", result.get("answer", "")))
                
                print("\n" + "=" * 60)
                print("METADATA:")
                print("=" * 60)
                print(f"Request Type: {result.get('request_type', 'unknown')}")
                
                # Calculate sentence count
                response_text = result.get("response", result.get("answer", ""))
                sentences = [s.strip() for s in response_text.split(".") if s.strip()]
                sentence_count = len(sentences)
                print(f"Verbosity: {sentence_count} sentence(s)")
                
                if result.get("sources"):
                    print(f"Sources: {len(result['sources'])} source(s)")
                    for i, source in enumerate(result["sources"][:3], 1):
                        if source.get("url"):
                            print(f"  {i}. {source.get('title', 'Unknown')} - {source['url']}")
                
                print("\n" + "-" * 60 + "\n")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                error_msg = str(e)
                print(f"\n[Error]: {error_msg}\n")
                import traceback
                traceback.print_exc()
        
        print("\n[Goodbye!]")
        return
    
    # Single query mode
    request_type = args.request_type
    
    # Auto-detect if not provided
    if not request_type:
        request_type = auto_detect_request_type(user_query)
        print(f"[Auto-detected request_type: {request_type}]")
    else:
        print(f"[Using provided request_type: {request_type}]")
    
    print(f"\nQuery: {user_query}")
    print("\nExecuting through CineMind (offline, FakeLLM, no API calls)...\n")
    
    try:
        result = await run_playground(user_query, request_type=request_type)
        
        # Display formatted output
        print("=" * 60)
        print("RESPONSE:")
        print("=" * 60)
        print(result.get("response", result.get("answer", "")))
        
        print("\n" + "=" * 60)
        print("METADATA:")
        print("=" * 60)
        print(f"Request Type: {result.get('request_type', 'unknown')}")
        
        # Calculate sentence count (verbosity indicator)
        response_text = result.get("response", result.get("answer", ""))
        sentences = [s.strip() for s in response_text.split(".") if s.strip()]
        sentence_count = len(sentences)
        print(f"Verbosity: {sentence_count} sentence(s)")
        
        if result.get("sources"):
            print(f"Sources: {len(result['sources'])} source(s)")
            for i, source in enumerate(result["sources"][:5], 1):
                if source.get("url"):
                    print(f"  {i}. {source.get('title', 'Unknown')} - {source['url']}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[Error]: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

