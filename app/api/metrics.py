from prometheus_client import Counter, Histogram

REQUEST_COUNTER = Counter(
    "data_contracts_http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status"],
)

REQUEST_ERROR_COUNTER = Counter(
    "data_contracts_http_errors_total",
    "Total number of HTTP error responses",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "data_contracts_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status"],
)


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {
        "method": method,
        "path": path,
        "status": str(status_code),
    }
    REQUEST_COUNTER.labels(**labels).inc()
    REQUEST_DURATION.labels(**labels).observe(duration_seconds)
    if status_code >= 400:
        REQUEST_ERROR_COUNTER.labels(**labels).inc()
