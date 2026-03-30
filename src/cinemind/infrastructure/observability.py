"""
Observability and monitoring for CineMind.
Handles logging, metrics, and tracing.
"""
import logging
import time
import uuid
from contextlib import contextmanager

from .database import Database


# Create custom formatter that safely handles missing request_id
class SafeRequestFormatter(logging.Formatter):
    """Formatter that safely handles missing request_id field."""
    def format(self, record):
        # Ensure request_id exists - default to 'system' if missing
        if not hasattr(record, 'request_id'):
            record.request_id = getattr(record, 'request_id', 'system')
        # If request_id is None, set to 'system'
        if record.request_id is None:
            record.request_id = 'system'
        try:
            return super().format(record)
        except KeyError:
            # Fallback if there's still an issue
            record.request_id = 'system'
            return super().format(record)

# Create custom filter for request IDs
class RequestContextFilter(logging.Filter):
    """Add request_id to log records if missing."""
    def filter(self, record):
        if not hasattr(record, 'request_id') or record.request_id is None:
            record.request_id = 'system'
        return True

# Configure structured logging with safe formatter
formatter = SafeRequestFormatter('%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s')

file_handler = logging.FileHandler('cinemind.log')
file_handler.setFormatter(formatter)
file_handler.addFilter(RequestContextFilter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.addFilter(RequestContextFilter())

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler],
    force=True  # Override any existing configuration
)

logger = logging.getLogger(__name__)


class Observability:
    """Observability service for tracking requests, metrics, and logs."""

    def __init__(self, db: Database):
        """
        Initialize observability service.

        Args:
            db: Database instance for storing metrics
        """
        self.db = db
        self.logger = logging.getLogger("cinemind.observability")

    def generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return str(uuid.uuid4())

    @contextmanager
    def track_request(self, request_id: str, user_query: str, use_live_data: bool = True,
                     model: str | None = None, request_type: str | None = None,
                     prompt: str | None = None):
        """
        Context manager for tracking a request from start to finish.

        Usage:
            with observability.track_request(request_id, query) as track:
                # Do work
                track.log_metric("response_time", 123.45)
        """
        start_time = time.time()

        # Save initial request with type
        self.db.save_request(request_id, user_query, use_live_data, model, "pending",
                            request_type=request_type, prompt=prompt)

        # Create track object
        track = RequestTracker(request_id, self.db, self.logger)

        try:
            # Set request ID in logging context
            yield track

            # Mark as success
            response_time_ms = (time.time() - start_time) * 1000
            self.db.update_request(request_id, status="success", response_time_ms=response_time_ms,
                                  request_type=request_type)
            track.log_metric("total_response_time_ms", response_time_ms)

        except Exception as e:
            # Mark as error
            response_time_ms = (time.time() - start_time) * 1000
            self.db.update_request(request_id, status="error",
                                 response_time_ms=response_time_ms,
                                 error_message=str(e),
                                 request_type=request_type)
            track.log_error(str(e))
            raise

    def update_request_prompt(self, request_id: str, prompt: str):
        """Update the prompt for an existing request."""
        self.db.update_request(request_id, prompt=prompt)

    def log_request(self, request_id: str, level: str, message: str, **kwargs):
        """Log a message with request context."""
        extra = {"request_id": request_id, **kwargs}
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(message, extra=extra)

    def log_classification_metadata(self, request_id: str, predicted_type: str,
                                   rule_hit: str | None = None, llm_used: bool = False,
                                   confidence: float = 1.0, entities: list | None = None,
                                   need_freshness: bool = False):
        """
        Log classification metadata for a request.

        Args:
            request_id: Request ID
            predicted_type: The predicted request type
            rule_hit: Which rule matched (if any)
            llm_used: Whether LLM was used for classification
            confidence: Confidence score (0.0-1.0)
            entities: List of extracted entities
            need_freshness: Whether query needs fresh data
        """
        metadata = {
            "predicted_type": predicted_type,
            "rule_hit": rule_hit,
            "llm_used": llm_used,
            "confidence": confidence,
            "entities": entities or [],
            "need_freshness": need_freshness
        }

        # Save as metric for querying
        self.db.save_metric(
            request_id,
            metric_type="classification",
            metric_name="classification_metadata",
            metric_value=confidence,
            metric_data=metadata
        )

        self.logger.info(
            f"Classification: type={predicted_type}, rule={rule_hit}, llm={llm_used}, "
            f"confidence={confidence:.2f}, freshness={need_freshness}",
            extra={"request_id": request_id}
        )

    def get_request_trace(self, request_id: str) -> dict:
        """Get complete trace for a request."""
        request = self.db.get_request(request_id)
        if not request:
            return None

        # Get response
        cursor = self.db.conn.cursor()
        if self.db.use_postgres:
            cursor.execute("SELECT * FROM responses WHERE request_id = %s", (request_id,))
        else:
            cursor.execute("SELECT * FROM responses WHERE request_id = ?", (request_id,))

        response_row = cursor.fetchone()
        response = None
        if response_row:
            if self.db.use_postgres:
                response = dict(response_row)
            else:
                response = dict(zip([col[0] for col in cursor.description], response_row, strict=False))

        # Get metrics
        if self.db.use_postgres:
            cursor.execute("SELECT * FROM metrics WHERE request_id = %s", (request_id,))
        else:
            cursor.execute("SELECT * FROM metrics WHERE request_id = ?", (request_id,))

        metrics_rows = cursor.fetchall()
        metrics = []
        if metrics_rows:
            if self.db.use_postgres:
                metrics = [dict(row) for row in metrics_rows]
            else:
                metrics = [dict(zip([col[0] for col in cursor.description], row, strict=False)) for row in metrics_rows]

        # Get search operations
        if self.db.use_postgres:
            cursor.execute("SELECT * FROM search_operations WHERE request_id = %s", (request_id,))
        else:
            cursor.execute("SELECT * FROM search_operations WHERE request_id = ?", (request_id,))

        search_rows = cursor.fetchall()
        searches = []
        if search_rows:
            if self.db.use_postgres:
                searches = [dict(row) for row in search_rows]
            else:
                searches = [dict(zip([col[0] for col in cursor.description], row, strict=False)) for row in search_rows]

        return {
            "request": request,
            "response": response,
            "metrics": metrics,
            "search_operations": searches
        }


class RequestTracker:
    """Tracker for individual request metrics."""

    def __init__(self, request_id: str, db: Database, logger: logging.Logger):
        self.request_id = request_id
        self.db = db
        self.logger = logger
        self.start_time = time.time()

    def log_metric(self, name: str, value: float, metadata: dict | None = None, metric_type: str = "gauge"):
        """Log a metric."""
        self.db.save_metric(
            self.request_id,
            metric_type=metric_type,
            metric_name=name,
            metric_value=value,
            metric_data=metadata
        )
        self.logger.info(f"Metric: {name}={value}", extra={"request_id": self.request_id})

    def log_counter(self, name: str, value: float = 1.0, metadata: dict | None = None):
        """Log a counter metric."""
        self.db.save_metric(
            self.request_id,
            metric_type="counter",
            metric_name=name,
            metric_value=value,
            metric_data=metadata
        )
        self.logger.info(f"Counter: {name}+={value}", extra={"request_id": self.request_id})

    def log_search(self, query: str, provider: str, results_count: int, search_time_ms: float):
        """Log a search operation."""
        self.db.save_search_operation(
            self.request_id,
            search_query=query,
            search_provider=provider,
            results_count=results_count,
            search_time_ms=search_time_ms
        )
        self.logger.info(
            f"Search: {provider} found {results_count} results in {search_time_ms:.2f}ms",
            extra={"request_id": self.request_id}
        )

    def log_error(self, error_message: str, metadata: dict | None = None):
        """Log an error."""
        self.db.save_metric(
            self.request_id,
            metric_type="error",
            metric_name="error_occurred",
            metric_value=1.0,
            metric_data={"error_message": error_message, **(metadata or {})}
        )
        self.logger.error(
            f"Error: {error_message}",
            extra={"request_id": self.request_id}
        )

    def time_operation(self, operation_name: str):
        """Context manager for timing an operation."""
        return OperationTimer(self.request_id, operation_name, self)


class OperationTimer:
    """Timer context manager for operations."""

    def __init__(self, request_id: str, operation_name: str, tracker: RequestTracker):
        self.request_id = request_id
        self.operation_name = operation_name
        self.tracker = tracker
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        start = self.start_time if self.start_time is not None else time.time()
        elapsed_ms = (time.time() - start) * 1000
        self.tracker.log_metric(f"{self.operation_name}_time_ms", elapsed_ms)
        return False


def estimate_llm_cost(usage: dict, model: str) -> float:
    """
    Estimate cost in USD from token usage. Unknown model ids default to 0 (typical for self-hosted Llama).
    Known hosted GPT ids retain approximate list pricing for backwards compatibility.
    """
    if not usage:
        return 0.0

    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    pricing = {
        "gpt-3.5-turbo": (0.0015, 0.002),
        "gpt-4": (0.03, 0.06),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
    }

    input_price, output_price = pricing.get(model.lower(), (0.0, 0.0))

    cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
    return round(cost, 6)


def calculate_openai_cost(usage: dict, model: str) -> float:
    """Deprecated alias for :func:`estimate_llm_cost`."""
    return estimate_llm_cost(usage, model)

