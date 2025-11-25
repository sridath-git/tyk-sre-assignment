import json
import socketserver
from typing import Optional

from kubernetes import client
from http.server import BaseHTTPRequestHandler


class AppHandler(BaseHTTPRequestHandler):

    # -------------------------
    # Main GET router
    # -------------------------
    def do_GET(self):
        if self.path == "/healthz":
            self.healthz()
        elif self.path == "/health/apiserver":
            self.health_apiserver()
        elif self.path == "/health/deployments":
            self.health_deployments()
        else:
            self.send_error(404)

    # -------------------------
    # Existing health check
    # -------------------------
    def healthz(self):
        self.respond(200, "ok")

    # -------------------------
    # New: API Server connectivity check
    # -------------------------
    def health_apiserver(self):
        try:
            # Create a Kubernetes API client from the global config
            api_client = client.ApiClient()
            version = get_kubernetes_version(api_client)

            result = {"status": "ok", "version": version}
            self.respond_json(200, result)

        except Exception as e:
            result = {"status": "error", "message": str(e)}
            self.respond_json(500, result)

    # -------------------------
    # New: Deployment health check
    # -------------------------
    def health_deployments(self):
        try:
            api_client = client.ApiClient()
            result = get_deployments_health(api_client)

            status_code = 200 if result["status"] == "ok" else 503
            self.respond_json(status_code, result)

        except Exception as e:
            result = {"status": "error", "message": str(e)}
            self.respond_json(500, result)

    # -------------------------
    # Shared response helpers
    # -------------------------
    def respond(self, status: int, content: str):
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(bytes(content, "UTF-8"))

    def respond_json(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


# ----------------------------------------------------------
# Helper 1 — Already existed in the project
# ----------------------------------------------------------
def get_kubernetes_version(api_client: client.ApiClient) -> str:
    version = client.VersionApi(api_client).get_code()
    return version.git_version


# ----------------------------------------------------------
# Helper 2 — New Deployment health logic
# ----------------------------------------------------------
def get_deployments_health(api_client: Optional[client.ApiClient] = None) -> dict:
    if api_client is None:
        api_client = client.ApiClient()

    apps_api = client.AppsV1Api(api_client)
    deployments = apps_api.list_deployment_for_all_namespaces().items

    results = []
    all_healthy = True

    for d in deployments:
        desired = d.spec.replicas or 0
        ready = d.status.ready_replicas or 0

        healthy = (desired == ready) and (desired > 0)

        if not healthy:
            all_healthy = False

        results.append({
            "namespace": d.metadata.namespace,
            "name": d.metadata.name,
            "desired": desired,
            "ready": ready,
            "healthy": healthy
        })

    status = "ok" if all_healthy else "degraded"

    return {
        "status": status,
        "deployments": results
    }


# ----------------------------------------------------------
# Server start logic (unchanged)
# ----------------------------------------------------------
def start_server(address):
    try:
        host, port = address.split(":")
    except ValueError:
        print("invalid server address format")
        return

    with socketserver.TCPServer((host, int(port)), AppHandler) as httpd:
        print("Server listening on {}".format(address))
        httpd.serve_forever()
