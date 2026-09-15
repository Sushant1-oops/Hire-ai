
from typing import List, Dict, Optional
from utils import logger
from skills_extractor import SkillsExtractor

class ScoringService:
    SEMANTIC_WEIGHT = 0.4
    SKILL_WEIGHT = 0.4
    EXPERIENCE_WEIGHT = 0.2
    MIN_SCORE_THRESHOLD = 0.40
    ZERO_SKILL_MATCH_PENALTY = 0.3

    @staticmethod
    def calculate_experience_match(candidate_experience, required_min_experience, nice_to_have_experience=None) -> float:
        required_min = required_min_experience or 0
        ideal = nice_to_have_experience or (required_min + 5)

        if candidate_experience is None:
            return 0.7 if required_min == 0 else 0.4

        if required_min == 0 and ideal == 5: return 0.7

        if candidate_experience < required_min:
            return (candidate_experience / required_min) * 0.4 if required_min != 0 else 0.5

        if candidate_experience <= ideal:
            progress = (candidate_experience - required_min) / (ideal - required_min) if ideal != required_min else 0
            return 0.6 + (progress * 0.35)

        overshoot = candidate_experience - ideal
        return max(0.75, 0.95 - overshoot * 0.02)

    @classmethod
    def calculate_skill_overlap(cls, candidate_skills: List[str], required_skills: List[str], nice_to_have_skills: Optional[List[str]] = None) -> Dict:
        extractor = SkillsExtractor()
        norm_candidate = set(extractor.extract_from_list(candidate_skills))
        norm_required = set(extractor.extract_from_list(required_skills))
        norm_nice = set(extractor.extract_from_list(nice_to_have_skills or []))

        matched_required = list(norm_candidate.intersection(norm_required))
        missing_required = list(norm_required.difference(norm_candidate))
        matched_nice = list(norm_candidate.intersection(norm_nice))

        required_coverage = len(matched_required) / len(norm_required) if norm_required else 1.0
        nice_coverage = len(matched_nice) / len(norm_nice) if norm_nice else 0

        score = (required_coverage * 0.8) + (nice_coverage * 0.2) if norm_required else 0.5

        return {
            "score": min(1.0, score),
            "matched_required": matched_required,
            "missing_required": missing_required,
            "matched_nice": matched_nice,
            "matched_count": len(matched_required)
        }

    @classmethod
    def calculate_final_score(cls, semantic_similarity, experience_match, skill_overlap, has_required_skills, matched_required_count) -> float:
        final_score = (cls.SEMANTIC_WEIGHT * semantic_similarity +
                       cls.SKILL_WEIGHT * skill_overlap +
                       cls.EXPERIENCE_WEIGHT * experience_match)
        
        if has_required_skills and matched_required_count == 0:
            final_score *= cls.ZERO_SKILL_MATCH_PENALTY
            
        return round(final_score, 4)

    @classmethod
    def score_candidate(cls, semantic_similarity: float, candidate_skills: List[str], required_skills: List[str], candidate_experience: Optional[float] = None, required_min_experience: Optional[float] = None, nice_to_have_skills: Optional[List[str]] = None, nice_to_have_experience: Optional[float] = None) -> Dict:
        semantic_score = max(0, min(1, semantic_similarity))
        experience_score = cls.calculate_experience_match(candidate_experience=candidate_experience, required_min_experience=required_min_experience, nice_to_have_experience=nice_to_have_experience)
        skill_result = cls.calculate_skill_overlap(candidate_skills, required_skills, nice_to_have_skills)
        
        final_score = cls.calculate_final_score(
            semantic_score, experience_score, skill_result["score"],
            bool(required_skills), skill_result["matched_count"]
        )

        return {
            "semantic_similarity": round(semantic_score, 4),
            "experience_match": round(experience_score, 4),
            "skill_overlap": round(skill_result["score"], 4),
            "final_score": final_score,
            "matched_skills": skill_result["matched_required"],
            "missing_skills": skill_result["missing_required"],
            "matched_nice_skills": skill_result["matched_nice"],
            "candidate_skills": candidate_skills
        }

    @staticmethod
    def get_recommendation(score: float) -> str:
        if score >= 0.75: return "Strong Hire"
        elif score >= 0.55: return "Consider"
        elif score >= 0.40: return "Weak Fit"
        else: return "Not Recommended"