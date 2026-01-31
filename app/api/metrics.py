from prometheus_client import Counter

REQUEST_COUNTER = Counter(
    "data_contracts_http_requests_total",
    "Total number of HTTP requests",
    ["method", "path", "status"],
)


def record_http_request(method: str, path: str, status_code: int) -> None:
    REQUEST_COUNTER.labels(method=method, path=path, status=str(status_code)).inc()
