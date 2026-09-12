import copy
import json
import unittest
from pathlib import Path
from opsrag.domain import analyze

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path("examples/sample.json").read_text())
        self.workload = self.data["items"][0]

    def test_risky_workload(self):
        codes = {f["code"] for f in analyze(self.data)["findings"]}
        self.assertTrue({"LOW_REPLICAS", "PRIVILEGED", "MUTABLE_IMAGE", "MISSING_PROBE"} <= codes)

    def test_explicit_baseline_passes(self):
        self.workload["spec"]["replicas"] = 3
        container = self.workload["spec"]["template"]["spec"]["containers"][0]
        container.update(image="example/app:v1", readinessProbe={"httpGet": {"path": "/ready", "port": 8080}},
                         livenessProbe={"httpGet": {"path": "/live", "port": 8080}},
                         securityContext={"privileged": False, "runAsNonRoot": True, "allowPrivilegeEscalation": False},
                         resources={"requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "1", "memory": "256Mi"}})
        self.assertEqual(analyze(self.data)["assessment"], "starter-checks-passed")

    def test_secret_env_values_not_exported(self):
        self.workload["spec"]["template"]["spec"]["containers"][0]["env"] = [
            {"name": "PASSWORD", "value": "do-not-export-this"}]
        self.assertNotIn("do-not-export-this", json.dumps(analyze(self.data)))

    def test_pod_security_defaults_inherited(self):
        pod = self.workload["spec"]["template"]["spec"]
        pod["securityContext"] = {"runAsNonRoot": True}
        self.assertNotIn("NON_ROOT_UNSET", {f["code"] for f in analyze(self.data)["findings"]})

    def test_container_override_takes_precedence(self):
        pod = self.workload["spec"]["template"]["spec"]
        pod["securityContext"] = {"runAsNonRoot": True}
        pod["containers"][0]["securityContext"]["runAsNonRoot"] = False
        self.assertIn("NON_ROOT_UNSET", {f["code"] for f in analyze(self.data)["findings"]})

    def test_unsupported_resources_are_reported(self):
        result = analyze({"kind": "Secret", "metadata": {"name": "hidden"}})
        self.assertEqual(len(result["skipped_resources"]), 1)
        self.assertEqual(result["findings"][0]["code"], "NO_SUPPORTED_WORKLOADS")

    def test_invalid_containers_rejected(self):
        self.workload["spec"]["template"]["spec"]["containers"] = []
        with self.assertRaises(ValueError):
            analyze(self.data)

    def test_negative_replicas_rejected(self):
        self.workload["spec"]["replicas"] = -1
        with self.assertRaises(ValueError):
            analyze(self.data)
