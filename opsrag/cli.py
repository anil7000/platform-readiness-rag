"""Local JSON input; external model calls require an explicit --llm flag."""
import argparse
import json
import sys
from pathlib import Path
from .domain import analyze, DEFAULT_QUESTION, TITLE
from .rag import investigate, redact, scrub

def markdown(result):
    out = [f"# {TITLE}", "", f"Mode: {result['mode']} | retrieval: {result['retrieval']}",
           "", "## Deterministic findings", ""]
    for finding in result["facts"].get("findings", []):
        out.append(f"- [{finding['severity']}] {finding['message']}")
    if not result["facts"].get("findings"):
        out.append("No findings triggered by the implemented checks.")
    out += ["", "## Advisory synthesis", "", result["answer"]["summary"], ""]
    out += ["- " + item for item in result["answer"]["recommendations"]]
    out += ["", "## Unknowns", ""]
    out += ["- " + item for item in result["answer"]["uncertainties"]]
    out += ["", "## Retrieved evidence", ""]
    for evidence in result["evidence"]:
        out += [f"### {evidence['id']}", "", evidence["text"], ""]
    out += ["Human review is required before operational action.", ""]
    return "\n".join(out)

def main(argv=None):
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--input", required=True, help="Local JSON export; maximum 2 MB")
    parser.add_argument("--kb", default="knowledge")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--llm", action="store_true", help="Send redacted facts and evidence to configured model")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args(argv)
    try:
        path = Path(args.input)
        if path.stat().st_size > 2_000_000:
            raise ValueError("Input exceeds 2 MB")
        def reject_constant(value):
            raise ValueError("Nonfinite JSON number")
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
        facts = analyze(data)
        # Redact only the domain's curated facts, never a complete raw export.
        facts = scrub(facts)
        report = investigate(facts, args.question, args.kb, args.llm)
        print(markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as error:
        print("Unable to produce report: " + redact(str(error)), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
