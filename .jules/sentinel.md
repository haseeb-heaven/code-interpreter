## 2025-02-27 - Missing Timeouts in API Calls
**Vulnerability:** External API calls via the `requests` library lacked a `timeout` parameter.
**Learning:** This exposes the application to a Denial of Service (DoS) vulnerability where a slow or unresponsive external server can cause the application thread to hang indefinitely.
**Prevention:** Always specify an explicit `timeout` parameter (e.g., `timeout=10`) when using `requests.get` or `requests.post`.
