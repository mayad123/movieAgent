"""
View observability data from the CineMind database.
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional
import argparse

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add src to path (repo root = parent of scripts/)
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from cinemind.database import Database


def print_request(request: dict):
    """Pretty print a request."""
    print("\n" + "=" * 80)
    print(f"Request ID: {request.get('request_id', 'N/A')}")
    print(f"Query: {request.get('user_query', 'N/A')}")
    print(f"Status: {request.get('status', 'N/A')}")
    print(f"Type: {request.get('request_type', 'N/A')}")
    print(f"Outcome: {request.get('outcome', 'N/A')}")
    print(f"Model: {request.get('model', 'N/A')}")
    print(f"Response Time: {request.get('response_time_ms', 0):.2f} ms")
    print(f"Created: {request.get('created_at', 'N/A')}")
    if request.get('error_message'):
        print(f"Error: {request.get('error_message')}")
    print("=" * 80)


def view_recent_requests(db: Database, limit: int = 10):
    """View recent requests."""
    print(f"\n[Recent Requests (last {limit}):]")
    requests = db.get_recent_requests(limit=limit)

    if not requests:
        print("No requests found.")
        return

    for i, req in enumerate(requests, 1):
        print(f"\n[{i}] {req.get('request_id', 'N/A')[:8]}...")
        print(f"    Query: {req.get('user_query', 'N/A')[:60]}...")
        print(f"    Type: {req.get('request_type', 'N/A')} | Outcome: {req.get('outcome', 'N/A')}")
        print(f"    Status: {req.get('status', 'N/A')} | Time: {req.get('response_time_ms', 0):.2f}ms")


def view_request_details(db: Database, request_id: str, full_prompt: bool = False, full_response: bool = False):
    """View detailed information about a specific request."""
    from cinemind.observability import Observability

    obs = Observability(db)
    trace = obs.get_request_trace(request_id)

    if not trace:
        print(f"Request {request_id} not found.")
        return

    request = trace.get('request', {})
    response = trace.get('response', {})
    metrics = trace.get('metrics', [])
    searches = trace.get('search_operations', [])

    print_request(request)

    # Show prompt if available
    prompt = request.get('prompt')
    if prompt:
        print("\n[Prompt Used:]")
        if full_prompt or len(prompt) <= 2000:
            lines = prompt.split('\n')
            for line in lines:
                print(f"   {line}")
            if not full_prompt and len(prompt) > 2000:
                print(f"\n   (Full prompt: {len(prompt)} characters, use --full-prompt to see all)")
        else:
            print(f"   {prompt[:1000]}...")
            print(f"   (Full prompt: {len(prompt)} characters, use --full-prompt to see all)")

    if response:
        print("\n[Response:]")
        response_text = response.get('response_text', 'N/A')
        if response_text and response_text != 'N/A':
            if full_response or len(response_text) <= 2000:
                lines = response_text.split('\n')
                for line in lines:
                    print(f"   {line}")
                if not full_response and len(response_text) > 2000:
                    print(f"\n   (Full response: {len(response_text)} characters, use --full-response to see all)")
            else:
                print(f"   {response_text[:2000]}...")
                print(f"   (Full response: {len(response_text)} characters, use --full-response to see all)")
        else:
            print(f"   {response_text}")

        sources = response.get('sources')
        if sources:
            if isinstance(sources, str):
                sources = json.loads(sources)
            print(f"\n   Sources ({len(sources)}):")
            for src in sources[:3]:
                print(f"   - {src.get('title', 'N/A')}: {src.get('url', 'N/A')}")

        token_usage = response.get('token_usage')
        if token_usage:
            if isinstance(token_usage, str):
                token_usage = json.loads(token_usage)
            print(f"\n   Token Usage:")
            print(f"   - Prompt: {token_usage.get('prompt_tokens', 0)}")
            print(f"   - Completion: {token_usage.get('completion_tokens', 0)}")
            print(f"   - Total: {token_usage.get('total_tokens', 0)}")

        cost = response.get('cost_usd')
        if cost:
            print(f"   - Cost: ${cost:.6f}")

    if metrics:
        print(f"\n[Metrics ({len(metrics)}):]")
        classification_metric = None
        for metric in metrics:
            if metric.get('metric_name') == 'classification_metadata':
                classification_metric = metric
                break

        if classification_metric:
            print("\n[Classification Metadata:]")
            metric_data = classification_metric.get('metric_data')
            if isinstance(metric_data, str):
                try:
                    metric_data = json.loads(metric_data)
                except Exception:
                    metric_data = {}
            elif metric_data is None:
                metric_data = {}

            print(f"   Predicted Type: {metric_data.get('predicted_type', 'N/A')}")
            print(f"   Rule Hit: {metric_data.get('rule_hit', 'N/A')}")
            print(f"   LLM Used: {metric_data.get('llm_used', False)}")
            print(f"   Confidence: {metric_data.get('confidence', 0.0):.2f}")
            entities = metric_data.get('entities', [])
            if entities:
                print(f"   Entities: {', '.join(entities) if isinstance(entities, list) else entities}")
            print(f"   Need Freshness: {metric_data.get('need_freshness', False)}")
            print()

        for metric in metrics:
            name = metric.get('metric_name', 'N/A')
            if name == 'classification_metadata':
                continue
            value = metric.get('metric_value', 0)
            metric_data = metric.get('metric_data')
            if metric_data and isinstance(metric_data, str):
                try:
                    metric_data = json.loads(metric_data)
                except Exception:
                    pass
            if metric_data and isinstance(metric_data, dict) and len(metric_data) > 0:
                print(f"   - {name}: {value}")
                for k, v in metric_data.items():
                    print(f"     {k}: {v}")
            else:
                print(f"   - {name}: {value}")

    if searches:
        print(f"\n[Search Operations ({len(searches)}):]")
        for search in searches:
            provider = search.get('search_provider', 'N/A')
            count = search.get('results_count', 0)
            time_ms = search.get('search_time_ms', 0)
            print(f"   - {provider}: {count} results in {time_ms:.2f}ms")


def view_stats(db: Database, days: int = 7, request_type: Optional[str] = None,
               outcome: Optional[str] = None):
    """View statistics."""
    stats = db.get_stats(days=days, request_type=request_type, outcome=outcome)

    print(f"\n[Statistics (last {days} days):]")
    if request_type:
        print(f"   Filter: request_type = {request_type}")
    if outcome:
        print(f"   Filter: outcome = {outcome}")

    print(f"\n   Total Requests: {stats.get('total_requests', 0)}")
    print(f"   Successful: {stats.get('successful_requests', 0)}")
    print(f"   Failed: {stats.get('failed_requests', 0)}")
    avg_time = stats.get('avg_response_time_ms', 0)
    if avg_time:
        print(f"   Avg Response Time: {avg_time:.2f} ms")
    total_cost = stats.get('total_cost_usd', 0)
    if total_cost:
        print(f"   Total Cost: ${total_cost:.6f}")


def view_tag_distribution(db: Database, days: int = 7):
    """View tag distribution."""
    dist = db.get_tag_distribution(days=days)

    print(f"\n[Tag Distribution (last {days} days):]")
    request_types = dist.get('request_types', {})
    if request_types:
        print("\n   Request Types:")
        for req_type, count in sorted(request_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {req_type}: {count}")

    outcomes = dist.get('outcomes', {})
    if outcomes:
        print("\n   Outcomes:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {outcome}: {count}")


def main():
    parser = argparse.ArgumentParser(description="View CineMind observability data")
    parser.add_argument('--db', default='cinemind.db', help='Database path')
    parser.add_argument('--limit', type=int, default=10, help='Number of recent requests to show')
    parser.add_argument('--request-id', help='View details for specific request ID')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--days', type=int, default=7, help='Number of days for stats/tags')
    parser.add_argument('--type', help='Filter by request type')
    parser.add_argument('--outcome', help='Filter by outcome')
    parser.add_argument('--tags', action='store_true', help='Show tag distribution')
    parser.add_argument('--full-prompt', action='store_true', help='Show full prompt (not truncated)')
    parser.add_argument('--full-response', action='store_true', help='Show full response (not truncated)')

    args = parser.parse_args()
    db = Database(db_path=args.db)

    if args.request_id:
        view_request_details(db, args.request_id, full_prompt=args.full_prompt, full_response=args.full_response)
    elif args.stats:
        view_stats(db, days=args.days, request_type=args.type, outcome=args.outcome)
    elif args.tags:
        view_tag_distribution(db, days=args.days)
    else:
        view_recent_requests(db, limit=args.limit)


if __name__ == "__main__":
    main()
