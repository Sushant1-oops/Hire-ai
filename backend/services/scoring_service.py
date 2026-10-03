"""Deterministic candidate scoring: semantic similarity (from search/vector
retrieval) blended with skill overlap and experience fit into one final_score,
plus a human-readable recommendation band. The LLM is never involved here —
so every number this module returns must stand on its own.
"""
from typing import Dict, List, Optional

from ai.skills_extractor import SkillsExtractor
from core.config import SEMANTIC_CEIL, SEMANTIC_FLOOR

_extractor = SkillsExtractor()  # regex compilation is the expensive part; share one instance


class ScoringService:
    SEMANTIC_WEIGHT = 0.4
    SKILL_WEIGHT = 0.4
    EXPERIENCE_WEIGHT = 0.2
    MIN_SCORE_THRESHOLD = 0.40
    ZERO_SKILL_MATCH_PENALTY = 0.3

    # ------------------------------------------------------------------ semantic

    @staticmethod
    def calibrate_semantic(value: float, floor: float = SEMANTIC_FLOOR, ceil: float = SEMANTIC_CEIL) -> float:
        """Stretches the raw similarity window [floor, ceil] onto 0-1 (see core/config.py
        for why). Monotonic: ranking order never changes, only how much of the 40% semantic
        weight a genuinely good match can earn."""
        return max(0.0, min(1.0, (value - floor) / max(ceil - floor, 1e-6)))

    # ---------------------------------------------------------------- experience

    @staticmethod
    def calculate_experience_match(
        candidate_experience: Optional[float],
        required_min_experience: Optional[float],
        nice_to_have_experience: Optional[float] = None,
    ) -> float:
        """0-1 fit between what the job wants and what the candidate has.
        Continuous end to end — meeting the minimum, falling short of it, and
        exceeding it are all points on the same curve, not separate branches
        that can jump at the seam between them."""
        required_min = required_min_experience if required_min_experience is not None else 0.0
        # "Ideal" is where the score peaks before the overshoot taper. With no
        # explicit hint, guess 5 years past the minimum — but this must still
        # depend on required_min, or a job with no stated minimum would score
        # every candidate identically regardless of their actual experience.
        ideal = nice_to_have_experience if nice_to_have_experience is not None else required_min + 5.0

        if candidate_experience is None:
            # Extraction genuinely couldn't find a number for this resume (see
            # ai/extraction.py) — score as a plain unknown, lower when the job
            # actually asks for a minimum, and let semantic similarity and
            # skill overlap carry the rest of the candidate's score.
            return 0.5 if required_min <= 0 else 0.3

        if ideal <= required_min:
            # Misconfigured input (ideal at or below the minimum) — meeting the
            # minimum is already the ceiling; still scale below it.
            if candidate_experience >= required_min:
                return 0.85
            return (candidate_experience / required_min) * 0.55 if required_min > 0 else 0.55

        if candidate_experience < required_min:
            # Below the bar: scale smoothly from 0 up to the "meets minimum"
            # score (0.55) rather than a hard cliff right at the threshold.
            return (candidate_experience / required_min) * 0.55 if required_min > 0 else 0.55

        if candidate_experience <= ideal:
            progress = (candidate_experience - required_min) / (ideal - required_min)
            return 0.55 + progress * 0.4  # 0.55 at the minimum, up to 0.95 at "ideal"

        # Past "ideal": taper off gently rather than keep climbing — very
        # senior candidates for a junior-level role are a fine match, not
        # automatically the best possible one — but never drop below 0.75
        # for simply having more experience than asked for.
        overshoot = candidate_experience - ideal
        return max(0.75, 0.95 - overshoot * 0.02)

    # -------------------------------------------------------------------- skills

    @staticmethod
    def _partition(
        wanted: List[str], candidate_set: set, candidate_text: Optional[str]
    ) -> Dict[str, List[str]]:
        """Splits a wanted-skill list into matched / missing / unverified.

        * A skill the candidate's extracted skill list contains is matched.
        * A skill outside the taxonomy ("Negotiation", an in-house tool) cannot
          appear in the extracted list, so it is looked up as a whole word in
          the resume text when the text is available. Found -> matched,
          not found -> missing.
        * Without resume text such a skill cannot be judged either way, so it
          is left out of the score ("unverified") instead of counting against
          the candidate for something nobody could have checked.
        Order follows the wanted list, so output is stable between runs."""
        matched: List[str] = []
        missing: List[str] = []
        unverified: List[str] = []
        for skill in wanted:
            if skill.lower() in candidate_set:
                matched.append(skill)
            elif _extractor.is_known(skill):
                missing.append(skill)
            elif candidate_text is None:
                unverified.append(skill)
            elif _extractor.mentions(candidate_text, skill):
                matched.append(skill)
            else:
                missing.append(skill)
        return {"matched": matched, "missing": missing, "unverified": unverified}

    @classmethod
    def calculate_skill_overlap(
        cls,
        candidate_skills: List[str],
        required_skills: List[str],
        nice_to_have_skills: Optional[List[str]] = None,
        candidate_text: Optional[str] = None,
    ) -> Dict:
        candidate_set = {s.lower() for s in _extractor.normalize_list(candidate_skills)}
        required = cls._partition(_extractor.normalize_list(required_skills), candidate_set, candidate_text)
        nice = cls._partition(_extractor.normalize_list(nice_to_have_skills or []), candidate_set, candidate_text)

        required_scorable = len(required["matched"]) + len(required["missing"])
        nice_scorable = len(nice["matched"]) + len(nice["missing"])
        required_coverage = len(required["matched"]) / required_scorable if required_scorable else None
        nice_coverage = len(nice["matched"]) / nice_scorable if nice_scorable else None

        if required_coverage is not None and nice_coverage is not None:
            # Both kinds were given: required coverage drives the score and the
            # nice-to-haves add a bonus on top.
            score = required_coverage * 0.8 + nice_coverage * 0.2
        elif required_coverage is not None:
            # Required skills but no nice-to-haves (the common case: the Jobs
            # page has no such field). There is nothing for the remaining 20%
            # to evaluate, so it must not act as a hidden ceiling: matching
            # every required skill earns full credit.
            score = required_coverage
        elif nice_coverage is not None:
            # No judgeable required skills, but nice-to-haves were given.
            score = 0.4 + nice_coverage * 0.5
        else:
            # Nothing to compare against; semantic similarity and experience
            # carry the score.
            score = 0.5

        return {
            "score": min(1.0, score),
            "matched_required": required["matched"],
            "missing_required": required["missing"],
            "unverified_required": required["unverified"],
            "matched_nice": nice["matched"],
            "matched_count": len(required["matched"]),
            # The zero-match penalty is for a job that names skills we can
            # actually recognise and a candidate with none of them. A job whose
            # requirements are all outside the taxonomy never triggers it:
            # one unrecognised word must not crush an otherwise strong,
            # relevant candidate (it still lowers skill coverage, honestly).
            "has_required": any(_extractor.is_known(s) for s in required["matched"] + required["missing"]),
        }

    # --------------------------------------------------------------- combining

    @classmethod
    def calculate_final_score(
        cls, semantic_similarity: float, experience_match: float, skill_overlap: float,
        has_required_skills: bool, matched_required_count: int,
    ) -> float:
        final_score = (
            cls.SEMANTIC_WEIGHT * semantic_similarity
            + cls.SKILL_WEIGHT * skill_overlap
            + cls.EXPERIENCE_WEIGHT * experience_match
        )
        if has_required_skills and matched_required_count == 0:
            final_score *= cls.ZERO_SKILL_MATCH_PENALTY
        return round(final_score, 4)

    @classmethod
    def score_candidate(
        cls,
        semantic_similarity: float,
        candidate_skills: List[str],
        required_skills: List[str],
        candidate_experience: Optional[float] = None,
        required_min_experience: Optional[float] = None,
        nice_to_have_skills: Optional[List[str]] = None,
        nice_to_have_experience: Optional[float] = None,
        candidate_text: Optional[str] = None,
    ) -> Dict:
        semantic_score = max(0.0, min(1.0, semantic_similarity))
        experience_score = cls.calculate_experience_match(
            candidate_experience=candidate_experience,
            required_min_experience=required_min_experience,
            nice_to_have_experience=nice_to_have_experience,
        )
        skill_result = cls.calculate_skill_overlap(candidate_skills, required_skills, nice_to_have_skills, candidate_text)

        final_score = cls.calculate_final_score(
            semantic_score, experience_score, skill_result["score"],
            skill_result["has_required"], skill_result["matched_count"],
        )

        return {
            "semantic_similarity": round(semantic_score, 4),
            "experience_match": round(experience_score, 4),
            "skill_overlap": round(skill_result["score"], 4),
            "final_score": final_score,
            "matched_skills": skill_result["matched_required"],
            "missing_skills": skill_result["missing_required"],
            "unverified_skills": skill_result["unverified_required"],
            "matched_nice_skills": skill_result["matched_nice"],
        }

    @staticmethod
    def get_recommendation(score: float) -> str:
        if score >= 0.75:
            return "Strong Hire"
        if score >= 0.55:
            return "Consider"
        if score >= 0.40:
            return "Weak Fit"
        return "Not Recommended"
