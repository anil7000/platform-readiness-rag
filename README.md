# Platform Readiness RAG

[![CI](https://github.com/anil7000/platform-readiness-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/anil7000/platform-readiness-rag/actions/workflows/ci.yml)

A deterministic static reviewer produces resource-specific findings, then retrieves local platform standards for an optional LLM explanation. The report separates starter checks from runtime health and unsupported resources.

**Owner and maintainer: [Anil Kumar Tangirala](https://github.com/anil7000).** Developed with AI assistance. Python 3.11+; no runtime package dependencies. Version 0.1 is a runnable reference implementation with synthetic examples, not a claim of production deployment.

## Problem it solves

Kubernetes reviews often alternate between generic best-practice lists and rules with no explanation. Reviewers need to know which workload triggered a finding and which platform policy explains it.

## How it works

```text
Kubernetes JSON export --> Workload-specific checks
Workload-specific checks --> Curated resource findings
Platform standards --> Retrieval
Curated resource findings --> Retrieval
Retrieval --> Optional LLM explanation
Optional LLM explanation --> Citation validation
Citation validation --> JSON or Markdown review
```

1. Validate the supplied JSON and run deterministic domain checks.
2. Select relevant operational facts instead of forwarding a complete raw export.
3. Redact common credential patterns and load bounded local Markdown/text knowledge.
4. Chunk knowledge into 220-word windows with a 40-word overlap; rank with BM25.
5. Optionally combine embedding similarity with BM25 using reciprocal-rank fusion.
6. Give the configured LLM the question, facts and retrieved evidence. Reject malformed answers or missing/unknown citation IDs.
7. Return facts, workflow results, evidence, uncertainty and advisory synthesis separately.

Citation-ID validation does not verify semantic entailment: a valid citation can still support a mistaken model interpretation. Human review is part of the workflow. No retrieved text is treated as authorization to run commands.

## Capabilities

| Check family | Review output |
| --- | --- |
| Availability | Single/zero replica review points for Deployments and StatefulSets |
| Resources | Missing or obvious zero CPU/memory requests and limits |
| Probes | Missing readiness and liveness probes |
| Images | Missing images, implicit latest and explicit latest tags |
| Security context | Privileged mode, non-root setting and privilege escalation |
| Host access | Host network/PID exposure |
| Scope transparency | Checked workloads, skipped resource kinds and known limitations |
| Policy explanation | Local runbook citations and optional LLM recommendations |

## Quick start: offline, no keys

```bash
git clone https://github.com/anil7000/platform-readiness-rag.git
cd platform-readiness-rag
python -m opsrag --input examples/sample.json --format markdown
# Review a local Kubernetes JSON export
python -m opsrag --input workloads.json --kb knowledge --format json
# Export only the supported workloads you intend to review:
# kubectl get deployments,statefulsets,daemonsets,pods -n YOUR_NAMESPACE -o json > workloads.json
```

Use a private knowledge directory for your approved platform policies. Review the built-in rules in opsrag/domain.py before using them in your team's process.

Accepts a Kubernetes JSON List or one Deployment, StatefulSet, DaemonSet or Pod. Container environment values are not included in analysis/model facts. Unsupported resource kinds are listed, not silently passed. CLI performs no kubectl calls.

### What the sample demonstrates

The included sandbox Deployment is intentionally under-specified: one replica, latest image, missing probes/resources and a privileged container. The report identifies each resource-specific gap and returns needs-review. A fixture with the explicit starter baseline passes in the test suite.

## Enable real LLM + RAG synthesis

Use a local Ollama server or another endpoint implementing the compatible chat-completions API. Install/pull your chosen model separately; this project does not download a model, supply an API key, or create paid resources.

```bash
export OPS_API_BASE=http://localhost:11434/v1
export OPS_MODEL=YOUR_INSTALLED_CHAT_MODEL
# Optional, for hybrid retrieval: install a compatible embedding model first.
# export OPS_EMBED_MODEL=YOUR_INSTALLED_EMBEDDING_MODEL
# For a hosted HTTPS endpoint, set OPS_API_KEY in your shell/secret manager.
python -m opsrag --input examples/sample.json --llm --format markdown
```

PowerShell equivalent:

```powershell
$env:OPS_API_BASE = 'http://localhost:11434/v1'
$env:OPS_MODEL = 'YOUR_INSTALLED_CHAT_MODEL'
python -m opsrag --input examples/sample.json --llm --format markdown
```

The .env.example file documents settings; it is **not automatically loaded**. Credentials belong in environment variables. Without --llm, all analysis and lexical retrieval run locally and no model calls occur. With --llm, curated facts, questions and retrieved chunks are sent to the configured endpoint. Setting OPS_EMBED_MODEL also sends question/runbook text for embeddings. Review your data and endpoint before enabling it.

The default endpoint is loopback-only HTTP. Remote endpoints must use HTTPS; embedded URL credentials and HTTP redirects are rejected. Model requests have a 45-second timeout and a 2 MB response limit. Corpus limits are 500 files, 256 KB/file and 2 MB total. These are basic safeguards, not comprehensive DLP or prompt-injection protection.

## Test and inspect

```bash
python -m unittest discover -s tests -v
python -m opsrag --input examples/sample.json --format json
```

Tests cover domain behavior and edge cases, retrieval ranking, abstention, invalid citations, redaction, and real HTTP transport against a deterministic local test double for chat and embeddings. The test double validates integration mechanics, **not live-model answer quality**. A live model has not been evaluated in this repository's initial build. GitHub Actions runs the suite on Python 3.11, 3.12 and 3.13.

Optional container CLI:

```bash
docker build -t platform-readiness-rag .
docker run --rm platform-readiness-rag
```

The image runs as a non-root user. The initial build was tested with Python; a Docker build requires Docker and is not represented as verified unless you run it. For the interactive bot, run the documented Python command on the host; the CLI Docker image is not configured as a network service.

## Repository map

```text
opsrag/domain.py       Domain checks and curated facts
opsrag/rag.py          BM25, optional embeddings, transport and citation checks
opsrag/cli.py          JSON/Markdown CLI
knowledge/runbook.md  Original synthetic starter knowledge
examples/sample.json  Reproducible synthetic input
tests/                Behavioral and transport tests
.github/workflows/    CI matrix
```

## Limits and next engineering steps

This is static exported-manifest review, not cluster access or admission enforcement. The starter standard is opinionated; CPU-limit and probe exceptions need workload-specific judgment. Full Kubernetes quantity validation, HPA/PDB/NetworkPolicy matching, init containers and Jobs are outside v0.1. A passed check is not a production-readiness certification.

Future work: broaden domain fixtures, evaluate retrieval/answer quality with a real model, implement enterprise identity/audit requirements before shared deployment, and add connector integrations only when their data/access scope is defined.

## Engineering references

- [Kubernetes: resource management for pods and containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Ollama's compatible API documentation](https://docs.ollama.com/api/openai-compatibility)

The operational rules and examples here are original starter implementations informed by public documentation. The three companion projects share an original retrieval/transport core while implementing different domain logic. Source code was developed with AI assistance and is maintained under this account; imported projects elsewhere in the profile retain their own upstream history and licenses.

## License

MIT. Copyright (c) 2026 Anil Kumar Tangirala. See [LICENSE](LICENSE).
