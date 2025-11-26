import unittest
import socket
import requests

from unittest.mock import MagicMock, patch   # extended to include patch
from socketserver import TCPServer
from threading import Thread
from kubernetes import client
from kubernetes.client.models import VersionInfo
from types import SimpleNamespace

from app import app


class TestGetKubernetesVersion(unittest.TestCase):
    def test_good_version(self):
        api_client = client.ApiClient()

        version = VersionInfo(
            build_date="",
            compiler="",
            git_commit="",
            git_tree_state="fake",
            git_version="1.25.0-fake",
            go_version="",
            major="1",
            minor="25",
            platform=""
        )
        api_client.call_api = MagicMock(return_value=version)

        version = app.get_kubernetes_version(api_client)
        self.assertEqual(version, "1.25.0-fake")

    def test_exception(self):
        api_client = client.ApiClient()
        api_client.call_api = MagicMock(side_effect=ValueError("test"))

        with self.assertRaisesRegex(ValueError, "test"):
            app.get_kubernetes_version(api_client)


class TestAppHandler(unittest.TestCase):
    def setUp(self):
        super().setUp()

        port = self._get_free_port()
        self.mock_server = TCPServer(("localhost", port), app.AppHandler)

        # Run the mock TCP server with AppHandler on a separate thread to avoid blocking the tests.
        self.mock_server_thread = Thread(target=self.mock_server.serve_forever)
        self.mock_server_thread.daemon = True
        self.mock_server_thread.start()

    def _get_free_port(self):
        """Returns a free port number from OS"""
        s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
        s.bind(("localhost", 0))
        __, port = s.getsockname()
        s.close()

        return port

    def _get_url(self, target):
        """Returns a URL to pass into the requests so that they reach this suite's mock server"""
        host, port = self.mock_server.server_address
        return f"http://{host}:{port}/{target}"

    def test_healthz_ok(self):
        resp = requests.get(self._get_url("healthz"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "ok")


# tests for Deployment Health logic

class TestGetDeploymentsHealth(unittest.TestCase):

    @patch("app.app.client.AppsV1Api")
    def test_all_deployments_healthy(self, mock_apps_api):
        """
        When all deployments have ready_replicas == spec.replicas
        the overall status should be 'ok'.
        """
        d1 = SimpleNamespace(
            metadata=SimpleNamespace(namespace="default", name="web"),
            spec=SimpleNamespace(replicas=3),
            status=SimpleNamespace(ready_replicas=3),
        )
        d2 = SimpleNamespace(
            metadata=SimpleNamespace(namespace="payments", name="payments-api"),
            spec=SimpleNamespace(replicas=2),
            status=SimpleNamespace(ready_replicas=2),
        )

        # Mock the Kubernetes API response
        mock_apps_api.return_value.list_deployment_for_all_namespaces.return_value = SimpleNamespace(
            items=[d1, d2]
        )

        result = app.get_deployments_health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["deployments"]), 2)

        web = result["deployments"][0]
        self.assertEqual(web["namespace"], "default")
        self.assertEqual(web["name"], "web")
        self.assertEqual(web["desired"], 3)
        self.assertEqual(web["ready"], 3)
        self.assertTrue(web["healthy"])

    @patch("app.app.client.AppsV1Api")
    def test_some_deployments_unhealthy(self, mock_apps_api):
        """
        If any deployment has ready_replicas != spec.replicas,
        overall status should be 'degraded'.
        """
        d1 = SimpleNamespace(
            metadata=SimpleNamespace(namespace="default", name="web"),
            spec=SimpleNamespace(replicas=3),
            status=SimpleNamespace(ready_replicas=3),
        )
        d2 = SimpleNamespace(
            metadata=SimpleNamespace(namespace="payments", name="payments-api"),
            spec=SimpleNamespace(replicas=4),
            status=SimpleNamespace(ready_replicas=2),
        )

        mock_apps_api.return_value.list_deployment_for_all_namespaces.return_value = SimpleNamespace(
            items=[d1, d2]
        )

        result = app.get_deployments_health()

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(len(result["deployments"]), 2)

        # Find the payments-api deployment
        unhealthy = [d for d in result["deployments"] if d["name"] == "payments-api"][0]
        self.assertFalse(unhealthy["healthy"])
        self.assertEqual(unhealthy["desired"], 4)
        self.assertEqual(unhealthy["ready"], 2)


if __name__ == '__main__':
    unittest.main()
