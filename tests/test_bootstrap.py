import asyncio
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import ssl
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = load("worker", "bootstrap/worker.py")
parameters = load("parameters", "infra/azure/validate-parameters.py")
relay = load("relay", "bootstrap/tls-relay.py")
exporter = load("exporter", "bootstrap/export-session.py")


class ConfigurationTests(unittest.TestCase):
    def test_multiline_clipboard_handoff(self):
        payload = {"token": "synthetic-capability", "certificate": "x" * 6000}
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        lines = [encoded[i:i + 1000] for i in range(0, len(encoded), 1000)]
        pasted = "BEGIN GATEHOUSE BUNDLE\n" + "\n".join(lines) + "\nEND GATEHOUSE BUNDLE\n"
        self.assertEqual(worker.read_bundle(io.StringIO(pasted)), payload)

    @patch.object(exporter.Path, "read_text", return_value="public transport cert")
    @patch.object(exporter.urllib.request, "build_opener")
    def test_export_excludes_operator_credentials_and_requests_proxy_role(self, build_opener, read_text):
        responses = [
            io.BytesIO(b'{"token":"operator-secret"}'),
            io.BytesIO(b'{"token":"worker-capability","expires_at":"2099-01-01T00:00:00Z"}'),
            io.BytesIO(b"public MITM cert"),
        ]
        opener = Mock()
        opener.open.side_effect = responses
        build_opener.return_value = opener
        bundle = exporter.export("project", "owner@example.invalid", "owner-password", 3600)
        payload = json.loads(opener.open.call_args_list[1].args[0].data)
        self.assertEqual(payload["vault_role"], "proxy")
        self.assertEqual(payload["ttl_seconds"], 3600)
        serialized = json.dumps(bundle)
        self.assertNotIn("operator-secret", serialized)
        self.assertNotIn("owner-password", serialized)
        self.assertEqual(bundle["token"], "worker-capability")

    def bundle(self):
        return {"token": "token:';$(oops)@", "vault": "project/x", "ca_certificate": "certificate",
                "transport_certificate": "certificate",
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}

    @patch.object(worker.ssl, "create_default_context")
    def test_capability_is_url_encoded_and_no_gateway_bypass(self, context):
        env = worker.proxy_environment(self.bundle())
        self.assertIn("token%3A%27%3B%24%28oops%29%40:project%2Fx@127.0.0.1", env["HTTPS_PROXY"])
        self.assertNotIn("10.82.2.4", env["NO_PROXY"])
        self.assertNotIn("AGENT_VAULT_TOKEN", env)
        self.assertEqual(context.call_count, 2)

    def test_expired_session_rejected(self):
        bundle = self.bundle()
        bundle["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaises(ValueError):
            worker.proxy_environment(bundle)

    def test_invalid_certificate_rejected(self):
        with self.assertRaises(ssl.SSLError):
            worker.proxy_environment(self.bundle())

    def test_deployment_rejects_mutable_image_and_placeholders(self):
        document = {"parameters": {k: {"value": v} for k, v in {
            "agentVaultImage": "infisical/agent-vault@sha256:" + "a" * 64,
            "ubuntuImageVersion": "24.04.20260901", "sshPublicKey": "ssh-ed25519 AAAA example",
        }.items()}}
        parameters.validate(document)
        for value in ("latest", "REPLACE", "infisical/agent-vault:v1"):
            document["parameters"]["agentVaultImage"]["value"] = value
            with self.assertRaises(ValueError):
                parameters.validate(document)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cert = Path(self.directory.name) / "cert.pem"
        self.key = Path(self.directory.name) / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
                        "-keyout", str(self.key), "-out", str(self.cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(self.cert, self.key)

        async def echo(reader, writer):
            try:
                data = await reader.readexactly(4)
                writer.write(data)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        self.upstream = await asyncio.start_server(echo, "127.0.0.1", 0, ssl=server_context)
        self.addAsyncCleanup(self.close_server, self.upstream)
        self.port = self.upstream.sockets[0].getsockname()[1]

    async def close_server(self, server):
        server.close()
        await server.wait_closed()

    async def exchange(self, context):
        server = await asyncio.start_server(
            lambda r, w: relay.relay(r, w, "127.0.0.1", self.port, context), "127.0.0.1", 0)
        self.addAsyncCleanup(self.close_server, server)
        reader, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
        try:
            writer.write(b"test")
            await writer.drain()
            return await asyncio.wait_for(reader.read(4), 3)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_trusted_tls_carries_bytes(self):
        self.assertEqual(await self.exchange(ssl.create_default_context(cafile=str(self.cert))), b"test")

    async def test_untrusted_certificate_fails_closed(self):
        self.assertEqual(await self.exchange(ssl.create_default_context()), b"")


if __name__ == "__main__":
    unittest.main()
