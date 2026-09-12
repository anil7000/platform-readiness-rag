import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from opsrag import rag
from opsrag.cli import main

class RetrievalTests(unittest.TestCase):
    def test_recursive_redaction_preserves_structure(self):
        value = {"message": 'request failed token="sensitive"', "nested": {"api_key": "hidden"}, "count": 3}
        cleaned = rag.scrub(value)
        self.assertEqual(cleaned["count"], 3)
        self.assertEqual(cleaned["nested"]["api_key"], "[REDACTED]")
        self.assertNotIn("sensitive", json.dumps(cleaned))
        self.assertNotIn("hidden", json.dumps(cleaned))

    def test_relevant_document_ranks_first(self):
        docs = [{"id": "a", "text": "Database timeout connection saturation"},
                {"id": "b", "text": "Container image digest release"}]
        hits, mode = rag.retrieve("database timeout", docs)
        self.assertEqual(hits[0]["id"], "a")
        self.assertEqual(mode, "bm25")

    def test_no_match_returns_no_evidence(self):
        self.assertEqual(rag.retrieve("unrelated", [{"id": "a", "text": "database"}])[0], [])

    def test_empty_corpus_abstains_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(rag.ModelClient, "generate", side_effect=AssertionError("must not call")):
                report = rag.investigate({}, "question", directory, True)
        self.assertIn("abstaining", report["answer"]["summary"])
        self.assertEqual(report["answer"]["citations"], [])

    def test_corpus_chunking_and_relative_citations(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "policy.md").write_text("database " * 450, encoding="utf-8")
            docs = rag.load_corpus(directory)
        self.assertEqual(len(docs), 3)
        self.assertEqual(docs[0]["id"], "policy.md#1")
        self.assertLessEqual(len(docs[0]["text"].split()), 220)

    def test_corpus_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "large.md").write_text("x" * 256_001)
            with self.assertRaises(ValueError):
                rag.load_corpus(directory)

    def test_redaction(self):
        text = rag.redact('password=hunter2 api_key="private-key" Bearer secretvalue AKIAABCDEFGHIJKLMNOP')
        for secret in ("hunter2", "private-key", "secretvalue", "AKIAABCDEFGHIJKLMNOP"):
            self.assertNotIn(secret, text)

    def test_unknown_citations_rejected(self):
        answer = {"summary": "Claim", "recommendations": [], "uncertainties": [], "citations": ["invented"]}
        with self.assertRaises(ValueError):
            rag.validate_answer(answer, [{"id": "real"}])

    def test_missing_citations_rejected(self):
        answer = {"summary": "Claim", "recommendations": [], "uncertainties": [], "citations": []}
        with self.assertRaises(ValueError):
            rag.validate_answer(answer, [{"id": "real"}])

    def test_malformed_model_structure_rejected(self):
        with self.assertRaises(ValueError):
            rag.validate_answer({"summary": "x", "recommendations": "bad"}, [{"id": "real"}])

    def test_cosine_dimensions_and_zero(self):
        self.assertEqual(rag.cosine([0, 0], [1, 2]), 0)
        self.assertAlmostEqual(rag.cosine([1, 0], [1, 0]), 1)
        with self.assertRaises(ValueError):
            rag.cosine([1], [1, 2])

    def test_insecure_remote_endpoint_rejected(self):
        with patch.dict(os.environ, {"OPS_API_BASE": "http://remote.example/v1"}):
            with self.assertRaises(ValueError):
                rag.ModelClient()

    def test_embedded_url_credentials_rejected(self):
        with patch.dict(os.environ, {"OPS_API_BASE": "https://secret:password@example.com/v1"}):
            with self.assertRaises(ValueError):
                rag.ModelClient()

    def test_offline_mode_never_calls_model(self):
        with patch.object(rag.ModelClient, "_post", side_effect=AssertionError("network forbidden")):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--input", "examples/sample.json"]), 0)

    def test_bad_json_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "input.json")
            path.write_text('{"invalid":NaN}')
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--input", str(path)]), 2)

class ModelHTTPTests(unittest.TestCase):
    """Real HTTP transport with a local deterministic test double, not a live LLM."""
    def test_chat_and_embedding_transport(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, payload))
                if self.path.endswith("/embeddings"):
                    body = {"data": [{"index": i, "embedding": [1.0, 0.5]}
                                     for i, _ in enumerate(payload["input"])]}
                else:
                    context = json.loads(payload["messages"][1]["content"])
                    answer = {"summary": "Review the supplied findings.",
                              "recommendations": ["Validate against the cited runbook."],
                              "uncertainties": ["Synthetic test only"],
                              "citations": [context["evidence"][0]["id"]]}
                    body = {"choices": [{"message": {"content": json.dumps(answer)}}]}
                encoded = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(encoded)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                Path(directory, "runbook.md").write_text("Database timeout investigation")
                with patch.dict(os.environ, {
                    "OPS_API_BASE": f"http://127.0.0.1:{server.server_port}/v1",
                    "OPS_MODEL": "test-chat", "OPS_EMBED_MODEL": "test-embedding", "OPS_API_KEY": ""
                }):
                    report = rag.investigate({"findings": []}, "database timeout", directory, True)
            self.assertEqual(report["mode"], "grounded-llm")
            self.assertEqual(report["retrieval"], "hybrid-bm25-embeddings")
            self.assertEqual(report["answer"]["citations"], ["runbook.md#1"])
            self.assertEqual([p for p, _ in calls], ["/v1/embeddings", "/v1/chat/completions"])
            self.assertIn("untrusted", calls[1][1]["messages"][0]["content"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

if __name__ == "__main__":
    unittest.main()
