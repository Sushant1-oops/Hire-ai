"""Field-level extraction quality on a labelled set.

    python -m evaluation.run_extraction [path/to/cases.json]

Reports skill precision/recall/F1 (micro-averaged over all cases), name and email
exact-match rate, and experience within a per-case tolerance. Runs with no models
and no database."""
import json
import os
import sys

from evaluation.metrics import mean, precision_recall_f1
from ai.extraction import extract_email, extract_experience, extract_name
from ai.skills_extractor import SkillsExtractor

DEFAULT = os.path.join(os.path.dirname(__file__), "datasets", "extraction_sample.json")


def run(path: str = DEFAULT) -> dict:
    cases = json.load(open(path, encoding="utf-8"))["cases"]
    extractor = SkillsExtractor()
    tp = fp = fn = 0
    name_hits, email_hits, exp_hits, exp_total = [], [], [], 0
    for case in cases:
        text, exp = case["text"], case["expected"]
        email = extract_email(text)
        name, _conf, _method = extract_name(text, email)
        years, _src = extract_experience(text)

        predicted, expected = set(extractor.extract(text)), set(exp["skills"])
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)

        name_hits.append(float((name or "").lower() == exp["name"].lower()))
        email_hits.append(float(email == exp["email"]))
        if "experience_years" in exp:
            exp_total += 1
            tol = exp.get("experience_tolerance", 0.5)
            exp_hits.append(float(years is not None and abs(years - exp["experience_years"]) <= tol))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "cases": len(cases),
        "skills": {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)},
        "name_exact": round(mean(name_hits), 3),
        "email_exact": round(mean(email_hits), 3),
        "experience_within_tolerance": round(mean(exp_hits), 3) if exp_total else None,
    }


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT), indent=2))
