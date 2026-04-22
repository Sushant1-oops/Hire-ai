"""
Scoring service for hybrid candidate ranking.
Combines semantic similarity, experience matching, and fuzzy skill overlap.
Rebalanced weights: 0.45 Semantic + 0.30 Skills + 0.25 Experience
"""

import json
import re
from typing import List, Dict, Optional
from utils import logger, safe_json_loads


class ScoringService:
    """
    Hybrid scoring system for ranking candidates.
    Final Score = 0.45 * Semantic + 0.30 * Skill Overlap + 0.25 * Experience Match
    """

    # Scoring weights — skills and experience matter more than pure semantic
    SEMANTIC_WEIGHT = 0.45
    SKILL_WEIGHT = 0.30
    EXPERIENCE_WEIGHT = 0.25

    # ── Skill Alias Map ────────────────────────────────────────────
    # Maps common variants to a canonical form for fuzzy matching.
    _SKILL_ALIASES = {
        "react": ["react.js", "reactjs", "react js"],
        "vue": ["vue.js", "vuejs", "vue js"],
        "angular": ["angularjs", "angular.js", "angular js"],
        "node.js": ["nodejs", "node js", "node"],
        "express": ["express.js", "expressjs"],
        "next.js": ["nextjs", "next js"],
        "nuxt.js": ["nuxtjs", "nuxt js"],
        "typescript": ["ts"],
        "javascript": ["js", "ecmascript", "es6", "es2015"],
        "python": ["python3", "python 3", "python2"],
        "c++": ["cpp", "c plus plus"],
        "c#": ["csharp", "c sharp"],
        "golang": ["go lang"],
        "postgresql": ["postgres", "psql"],
        "mongodb": ["mongo"],
        "kubernetes": ["k8s"],
        "docker": ["containerization"],
        "amazon web services": ["aws"],
        "google cloud platform": ["gcp", "google cloud"],
        "microsoft azure": ["azure"],
        "machine learning": ["ml"],
        "deep learning": ["dl"],
        "natural language processing": ["nlp"],
        "computer vision": ["cv"],
        "artificial intelligence": ["ai"],
        "continuous integration": ["ci/cd", "ci cd", "cicd"],
        "rest api": ["restful", "rest apis", "restful api"],
        "graphql": ["graph ql"],
        "sql": ["structured query language"],
        "nosql": ["no sql", "no-sql"],
        "html": ["html5"],
        "css": ["css3"],
        "sass": ["scss"],
        "tailwind css": ["tailwindcss", "tailwind"],
        "spring boot": ["springboot", "spring-boot"],
        "ruby on rails": ["rails", "ror"],
        "scikit-learn": ["sklearn", "scikit learn"],
        "tensorflow": ["tf"],
        "pytorch": ["torch"],
        "pandas": ["pd"],
        "numpy": ["np"],
    }

    # Build reverse map: alias -> canonical
    _ALIAS_TO_CANONICAL = {}
    for canonical, aliases in _SKILL_ALIASES.items():
        _ALIAS_TO_CANONICAL[canonical] = canonical
        for alias in aliases:
            _ALIAS_TO_CANONICAL[alias] = canonical

    @classmethod
    def _normalize_skill(cls, skill: str) -> str:
        """Normalize a skill string to its canonical form."""
        s = skill.lower().strip()
        return cls._ALIAS_TO_CANONICAL.get(s, s)

    @staticmethod
    def calculate_semantic_similarity(similarity: float) -> float:
        """Normalize semantic similarity score (0-1)."""
        return max(0, min(1, similarity))

    @staticmethod
    def calculate_experience_match(
        candidate_experience: Optional[float],
        required_min_experience: Optional[float],
        nice_to_have_experience: Optional[float] = None
    ) -> float:
        """
        Calculate experience match score (0-1) using a smooth curve.
        """
        if candidate_experience is None:
            return 0.4  # Low-neutral if unknown

        required_min = required_min_experience or 0
        ideal = nice_to_have_experience or (required_min + 5)

        if required_min == 0 and ideal == 5:
            # No experience requirement specified — be generous
            return 0.7

        # Below minimum: linear ramp 0 → 0.4
        if candidate_experience < required_min:
            if required_min == 0:
                return 0.5
            ratio = candidate_experience / required_min
            return ratio * 0.4

        # At minimum: 0.6
        # Between min and ideal: 0.6 → 0.95
        if candidate_experience <= ideal:
            if ideal == required_min:
                return 0.8
            progress = (candidate_experience - required_min) / (ideal - required_min)
            return 0.6 + progress * 0.35

        # Above ideal: slight decrease for overqualification but still high
        overshoot = candidate_experience - ideal
        return max(0.75, 0.95 - overshoot * 0.02)

    @classmethod
    def calculate_skill_overlap(
        cls,
        candidate_skills: List[str],
        required_skills: List[str],
        nice_to_have_skills: Optional[List[str]] = None
    ) -> Dict:
        """
        Calculate skill overlap score (0-1) with fuzzy matching.
        Returns dict with score, matched_skills, and missing_skills.
        """
        if not required_skills:
            return {
                "score": 0.5,
                "matched_required": [],
                "missing_required": [],
                "matched_nice": [],
            }

        # Normalize all skills
        candidate_normalized = {cls._normalize_skill(s): s for s in candidate_skills}
        required_normalized = {cls._normalize_skill(s): s for s in required_skills}
        nice_normalized = {cls._normalize_skill(s): s for s in (nice_to_have_skills or [])}

        # Match required skills
        matched_required = []
        missing_required = []
        for norm_skill, orig_skill in required_normalized.items():
            if norm_skill in candidate_normalized:
                matched_required.append(orig_skill)
            else:
                # Try substring match: "python" in "python programming"
                found = False
                for cand_norm in candidate_normalized:
                    if norm_skill in cand_norm or cand_norm in norm_skill:
                        matched_required.append(orig_skill)
                        found = True
                        break
                if not found:
                    missing_required.append(orig_skill)

        # Match nice-to-have skills
        matched_nice = []
        for norm_skill, orig_skill in nice_normalized.items():
            if norm_skill in candidate_normalized:
                matched_nice.append(orig_skill)
            else:
                for cand_norm in candidate_normalized:
                    if norm_skill in cand_norm or cand_norm in norm_skill:
                        matched_nice.append(orig_skill)
                        break

        # Calculate score
        required_coverage = len(matched_required) / len(required_normalized) if required_normalized else 0

        if nice_normalized:
            nice_coverage = len(matched_nice) / len(nice_normalized)
            score = (required_coverage * 0.75) + (nice_coverage * 0.25)
        else:
            score = required_coverage

        return {
            "score": min(1.0, score),
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_nice": matched_nice,
        }

    @classmethod
    def calculate_final_score(
        cls,
        semantic_similarity: float,
        experience_match: float,
        skill_overlap: float
    ) -> float:
        """
        Calculate final hybrid score.
        Final Score = 0.45 * Semantic + 0.30 * Skills + 0.25 * Experience
        """
        final_score = (
            cls.SEMANTIC_WEIGHT * semantic_similarity +
            cls.SKILL_WEIGHT * skill_overlap +
            cls.EXPERIENCE_WEIGHT * experience_match
        )
        return round(final_score, 4)

    @classmethod
    def score_candidate(
        cls,
        semantic_similarity: float,
        candidate_resume: Dict,
        required_skills: List[str],
        required_min_experience: Optional[float] = None,
        nice_to_have_skills: Optional[List[str]] = None,
        nice_to_have_experience: Optional[float] = None
    ) -> Dict:
        """
        Comprehensive scoring for a single candidate.
        Returns dict with all component scores, final score, and skill breakdown.
        """
        # Parse candidate data
        candidate_skills = safe_json_loads(
            candidate_resume.get("skills", "[]"),
            default=[]
        )
        if isinstance(candidate_skills, str):
            candidate_skills = [candidate_skills]

        candidate_experience = candidate_resume.get("experience_years")

        # Calculate component scores
        semantic_score = cls.calculate_semantic_similarity(semantic_similarity)

        experience_score = cls.calculate_experience_match(
            candidate_experience,
            required_min_experience,
            nice_to_have_experience
        )

        skill_result = cls.calculate_skill_overlap(
            candidate_skills,
            required_skills or [],
            nice_to_have_skills
        )
        skill_score = skill_result["score"]

        # Calculate final score
        final_score = cls.calculate_final_score(
            semantic_score,
            experience_score,
            skill_score
        )

        return {
            "semantic_similarity": round(semantic_score, 4),
            "experience_match": round(experience_score, 4),
            "skill_overlap": round(skill_score, 4),
            "final_score": final_score,
            "matched_skills": skill_result["matched_required"],
            "missing_skills": skill_result["missing_required"],
            "matched_nice_skills": skill_result["matched_nice"],
            "candidate_skills": candidate_skills,
            "weighted_scores": {
                "semantic": round(semantic_score * cls.SEMANTIC_WEIGHT, 4),
                "experience": round(experience_score * cls.EXPERIENCE_WEIGHT, 4),
                "skills": round(skill_score * cls.SKILL_WEIGHT, 4),
            }
        }

    @classmethod
    def rank_candidates(
        cls,
        candidates: List[Dict],
        score_key: str = "final_score"
    ) -> List[Dict]:
        """Rank candidates by score and add rank field."""
        ranked = sorted(
            candidates,
            key=lambda x: x.get(score_key, 0),
            reverse=True
        )

        for idx, candidate in enumerate(ranked, 1):
            candidate["rank"] = idx

        return ranked

    @staticmethod
    def get_recommendation(score: float) -> str:
        """Get recommendation based on final score."""
        if score >= 0.70:
            return "Strong Hire"
        elif score >= 0.50:
            return "Consider"
        elif score >= 0.35:
            return "Weak Fit"
        else:
            return "Not Recommended"


# ==================== ANALYTICS ====================
class ScoringAnalytics:
    """Analytics for scoring results."""

    @staticmethod
    def calculate_statistics(scores: List[float]) -> Dict:
        """Calculate statistics for a list of scores."""
        if not scores:
            return {
                "count": 0, "mean": 0, "median": 0,
                "min": 0, "max": 0, "std_dev": 0
            }

        import statistics
        sorted_scores = sorted(scores)
        return {
            "count": len(scores),
            "mean": round(statistics.mean(scores), 4),
            "median": round(statistics.median(sorted_scores), 4),
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
            "std_dev": round(statistics.stdev(scores) if len(scores) > 1 else 0, 4)
        }

    @staticmethod
    def categorize_scores(candidates: List[Dict]) -> Dict:
        """Categorize candidates by score ranges."""
        categories = {
            "strong_hire": [],
            "consider": [],
            "weak_fit": [],
            "not_recommended": [],
        }

        for candidate in candidates:
            score = candidate.get("final_score", 0)
            if score >= 0.70:
                categories["strong_hire"].append(candidate)
            elif score >= 0.50:
                categories["consider"].append(candidate)
            elif score >= 0.35:
                categories["weak_fit"].append(candidate)
            else:
                categories["not_recommended"].append(candidate)

        return {
            "strong_hire_count": len(categories["strong_hire"]),
            "consider_count": len(categories["consider"]),
            "weak_fit_count": len(categories["weak_fit"]),
            "not_recommended_count": len(categories["not_recommended"]),
            "distribution": categories
        }
