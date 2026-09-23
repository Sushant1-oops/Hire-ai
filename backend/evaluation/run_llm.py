"""LLM output checks against a live provider (Groq or Ollama).

    python -m evaluation.run_llm --runs 3 resume1.txt resume2.txt --jd jd.txt

For each resume: repeats the match analysis N times and reports the share of runs
that produced schema-valid output and the share of strengths that have supporting
text in the resume (embedding-based, needs the indexed chunks so this uses the
resume text directly).
Costs LLM calls; not run by the test suite."""
import argparse
import json

from services import embedding_service
from ai.chunking import chunk_resume
from services.llm_service import MatchAnalysisRequest, analyze_candidate_match
from core.config import EVIDENCE_MIN_SIMILARITY
from ai.extraction import parse_resume
from services.scoring_service import ScoringService


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("resumes", nargs="+")
    ap.add_argument("--jd", required=True)
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    jd = open(args.jd, encoding="utf-8").read()

    report = []
    for path in args.resumes:
        text = open(path, encoding="utf-8").read()
        parsed = parse_resume(text)
        chunk_vecs = embedding_service.encode(chunk_resume(parsed["skills"], parsed["experience_years"], text))
        valid = failures = supported = claims = 0
        for _ in range(args.runs):
            result = analyze_candidate_match(MatchAnalysisRequest(candidate_resume=text, job_description=jd))
            if result is None:
                failures += 1
                continue
            valid += 1
            for claim, vec in zip(result.strengths, embedding_service.encode(result.strengths)):
                claims += 1
                supported += int(float((chunk_vecs @ vec).max()) >= EVIDENCE_MIN_SIMILARITY)
        report.append({
            "resume": path, "runs": args.runs, "schema_valid_rate": valid / args.runs, "failure_rate": failures / args.runs,
            "grounded_strength_rate": (supported / claims) if claims else None,
        })
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
