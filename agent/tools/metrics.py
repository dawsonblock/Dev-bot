import os
import requests

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


def read():
    try:
        # Example queries; replace with actual queries your system exports
        res_err = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": 'rate(http_requests_total{status=~"5.."}[1m])'},
        )
        res_lat = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={
                "query": (
                    "histogram_quantile(0.99,"
                    " rate(http_request_duration_seconds_bucket[1m]))"
                )
            },
        )

        err_data = res_err.json().get("data", {}).get("result", [])
        lat_data = res_lat.json().get("data", {}).get("result", [])

        err_val = float(err_data[0]["value"][1]) if err_data else 0.0
        lat_val = float(lat_data[0]["value"][1]) if lat_data else 0.0

        return {"error_rate": err_val, "latency_p99": lat_val}
    except Exception as e:
        print(f"[METRICS WARN] Prometheus scrape failed: {e}")
        return {"error_rate": 0.0, "latency_p99": 0.0}
