"""
Test recommendations case with prompt version v4 and show observability data.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add src and tests to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "tests"))

from test_cases import TEST_SUITES
from cinemind.agent import CineMind
from cinemind.observability import Observability
from cinemind.database import Database
from cinemind.prompts.versions import get_prompt_version
import cinemind.config as config


async def run_multi_hop_v4():
    """Run multi-hop test with prompt version v4 and show observability and cache status."""
    
    # Set prompt version to v4
    config.SYSTEM_PROMPT = get_prompt_version("v4")
    config.PROMPT_VERSION = "v4"
    
    print("=" * 80)
    print("MULTI-HOP TEST WITH PROMPT VERSION V4 (CACHE TEST)")
    print("=" * 80)
    print(f"\nPrompt Version: v4")
    print(f"Prompt Length: {len(config.SYSTEM_PROMPT)} characters\n")
    
    # Get the multi-hop test case
    test_cases = TEST_SUITES.get("multi_hop", [])
    if not test_cases:
        print("No multi-hop test cases found!")
        return
    
    test_case = test_cases[0]  # Get first multi-hop test
    print(f"Test Case: {test_case.name}")
    print(f"Query: {test_case.prompt}")
    print(f"Expected Type: {test_case.expected_type}")
    print("\n" + "=" * 80)
    print("Running test with observability enabled...")
    print("=" * 80 + "\n")
    
    # Create agent with observability enabled
    agent = CineMind(enable_observability=True)
    
    try:
        print("\n" + "=" * 80)
        print("FIRST RUN (Should populate cache)")
        print("=" * 80 + "\n")
        
        # Run the test - FIRST RUN (should populate cache)
        result1 = await agent.search_and_analyze(
            test_case.prompt,
            use_live_data=True
        )
        
        request_id1 = result1.get("request_id")
        cache_hit1 = result1.get("cache_hit", False)
        
        print(f"\nFirst Run Results:")
        print(f"  Request ID: {request_id1}")
        print(f"  Cache Hit: {cache_hit1}")
        print(f"  Live Data Used: {result1.get('live_data_used', False)}")
        print(f"  Response Time: {result1.get('timestamp', 'N/A')}")
        
        # Wait a moment for cache to be written
        import asyncio
        await asyncio.sleep(2)
        
        print("\n" + "=" * 80)
        print("SECOND RUN (Should use cache, NO Tavily call)")
        print("=" * 80 + "\n")
        
        # Run the test again - SECOND RUN (should use cache)
        result2 = await agent.search_and_analyze(
            test_case.prompt,
            use_live_data=True
        )
        
        request_id2 = result2.get("request_id")
        cache_hit2 = result2.get("cache_hit", False)
        cache_tier2 = result2.get("cache_tier", "N/A")
        live_data_used2 = result2.get("live_data_used", False)
        
        print(f"\nSecond Run Results:")
        print(f"  Request ID: {request_id2}")
        print(f"  Cache Hit: {cache_hit2}")
        print(f"  Cache Tier: {cache_tier2}")
        print(f"  Live Data Used: {live_data_used2}")
        print(f"  Cost: ${result2.get('cost_usd', 0):.6f}")
        
        # Check if cache worked
        if cache_hit2:
            print("\n[SUCCESS] CACHE WORKING: Second run used cache (no Tavily call)")
            if not live_data_used2:
                print("[SUCCESS] CONFIRMED: Live data was NOT used (cache served the response)")
            else:
                print("[WARNING] Cache hit but live_data_used is True (unexpected)")
        else:
            print("\n[FAILURE] CACHE NOT WORKING: Second run did NOT use cache (Tavily was called)")
            print("   This indicates a cache miss - need to investigate why")
            print("   Possible reasons:")
            print("   - Cache entry expired (check TTL)")
            print("   - Hash mismatch (normalization differences)")
            print("   - Classification type mismatch")
            print("   - PROMPT_VERSION mismatch")
        
        # Use second result for observability display
        request_id = request_id2
        result = result2
        
        # Print agent response
        print("\n" + "=" * 80)
        print("AGENT RESPONSE")
        print("=" * 80)
        print(result.get("response", ""))
        print("\n" + "=" * 80)
        
        # Get observability data
        db = Database()
        obs = Observability(db)
        trace = obs.get_request_trace(request_id)
        
        if trace:
            request = trace.get('request', {})
            response = trace.get('response', {})
            metrics = trace.get('metrics', [])
            searches = trace.get('search_operations', [])
            
            # Print request info
            print("\n" + "=" * 80)
            print("REQUEST INFORMATION")
            print("=" * 80)
            print(f"Request ID: {request.get('request_id', 'N/A')}")
            print(f"Query: {request.get('user_query', 'N/A')}")
            print(f"Status: {request.get('status', 'N/A')}")
            print(f"Request Type: {request.get('request_type', 'N/A')}")
            print(f"Model: {request.get('model', 'N/A')}")
            print(f"Response Time: {request.get('response_time_ms', 0):.2f} ms")
            print(f"Created: {request.get('created_at', 'N/A')}")
            
            # Print classification metadata
            print("\n" + "=" * 80)
            print("CLASSIFICATION METADATA")
            print("=" * 80)
            
            # Find classification metadata in metrics
            classification_metric = None
            for metric in metrics:
                if metric.get('metric_name') == 'classification_metadata':
                    classification_metric = metric
                    break
            
            if classification_metric:
                import json
                metric_data = classification_metric.get('metric_data')
                if isinstance(metric_data, str):
                    metric_data = json.loads(metric_data)
                elif metric_data is None:
                    metric_data = {}
                
                print(f"Predicted Type: {metric_data.get('predicted_type', 'N/A')}")
                print(f"Rule Hit: {metric_data.get('rule_hit', 'N/A')}")
                print(f"LLM Used: {metric_data.get('llm_used', False)}")
                print(f"Confidence: {metric_data.get('confidence', 0.0):.2f}")
                print(f"Entities: {metric_data.get('entities', [])}")
                print(f"Need Freshness: {metric_data.get('need_freshness', False)}")
            else:
                print("Classification metadata not found in metrics")
            
            # Print metrics summary
            print("\n" + "=" * 80)
            print("METRICS SUMMARY")
            print("=" * 80)
            for metric in metrics:
                name = metric.get('metric_name', 'N/A')
                value = metric.get('metric_value', 0)
                metric_data = metric.get('metric_data')
                if metric_data:
                    if isinstance(metric_data, str):
                        try:
                            import json
                            metric_data = json.loads(metric_data)
                        except:
                            pass
                    if isinstance(metric_data, dict):
                        print(f"{name}: {value}")
                        for k, v in metric_data.items():
                            if k != 'predicted_type':  # Already shown above
                                print(f"  - {k}: {v}")
                    else:
                        print(f"{name}: {value}")
                else:
                    print(f"{name}: {value}")
            
            # Print search operations
            if searches:
                print("\n" + "=" * 80)
                print("SEARCH OPERATIONS")
                print("=" * 80)
                for search in searches:
                    print(f"Query: {search.get('search_query', 'N/A')}")
                    print(f"Provider: {search.get('search_provider', 'N/A')}")
                    print(f"Results: {search.get('results_count', 0)}")
                    print(f"Time: {search.get('search_time_ms', 0):.2f} ms")
                    print()
            
            # Print response details
            if response:
                print("\n" + "=" * 80)
                print("RESPONSE DETAILS")
                print("=" * 80)
                token_usage = response.get('token_usage')
                if token_usage:
                    if isinstance(token_usage, str):
                        import json
                        token_usage = json.loads(token_usage)
                    print(f"Prompt Tokens: {token_usage.get('prompt_tokens', 0)}")
                    print(f"Completion Tokens: {token_usage.get('completion_tokens', 0)}")
                    print(f"Total Tokens: {token_usage.get('total_tokens', 0)}")
                    print(f"Cost: ${response.get('cost_usd', 0):.6f}")
                
                sources = response.get('sources')
                if sources:
                    if isinstance(sources, str):
                        import json
                        sources = json.loads(sources)
                    print(f"\nSources ({len(sources)}):")
                    for i, src in enumerate(sources[:5], 1):
                        print(f"  {i}. {src.get('title', 'N/A')}")
                        print(f"     {src.get('url', 'N/A')}")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
        db.close()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(run_multi_hop_v4())

