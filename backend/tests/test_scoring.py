import unittest

from services.scoring_service import ScoringService


class ScoringTests(unittest.TestCase):
    def test_weights_sum_to_one(self):
        total = ScoringService.SEMANTIC_WEIGHT + ScoringService.SKILL_WEIGHT + ScoringService.EXPERIENCE_WEIGHT
        self.assertAlmostEqual(total, 1.0)

    def test_zero_required_skill_match_is_penalised(self):
        with_match = ScoringService.score_candidate(0.8, ["Python"], ["Python"], 4, 2)
        without = ScoringService.score_candidate(0.8, ["Java"], ["Python"], 4, 2)
        self.assertGreater(with_match["final_score"], without["final_score"] * 2)

    def test_no_required_skills_means_no_penalty(self):
        result = ScoringService.score_candidate(0.6, [], [], 3, None)
        self.assertGreater(result["final_score"], 0.4)

    def test_recommendation_bands(self):
        self.assertEqual(ScoringService.get_recommendation(0.75), "Strong Hire")
        self.assertEqual(ScoringService.get_recommendation(0.55), "Consider")
        self.assertEqual(ScoringService.get_recommendation(0.40), "Weak Fit")
        self.assertEqual(ScoringService.get_recommendation(0.39), "Not Recommended")

    def test_scoring_is_deterministic(self):
        args = (0.5, ["Python", "SQL"], ["Python", "Docker"], 3, 2)
        self.assertEqual(ScoringService.score_candidate(*args), ScoringService.score_candidate(*args))

    def test_more_experience_than_required_never_scores_below_meeting_it(self):
        meets = ScoringService.calculate_experience_match(2, 2)
        more = ScoringService.calculate_experience_match(4, 2)
        self.assertGreaterEqual(more, meets)

    def test_skill_matching_normalises_case_and_aliases(self):
        result = ScoringService.score_candidate(0.5, ["postgres", "k8s"], ["PostgreSQL", "Kubernetes"], 2, 1)
        self.assertEqual(sorted(result["matched_skills"]), ["Kubernetes", "PostgreSQL"])
        self.assertEqual(result["missing_skills"], [])

    def test_experience_differentiates_candidates_even_with_no_minimum_stated(self):
        # Regression test: this used to be a hard-coded 0.7 for every candidate
        # whenever a job had no minimum experience set (the common case, since
        # there's no UI field for nice_to_have_experience), which meant the
        # entire experience component of the score never differentiated anyone.
        none_years = ScoringService.calculate_experience_match(0, None)
        some_years = ScoringService.calculate_experience_match(2, None)
        ideal_years = ScoringService.calculate_experience_match(5, None)
        self.assertLess(none_years, some_years)
        self.assertLess(some_years, ideal_years)

    def test_experience_score_has_no_cliff_at_the_minimum(self):
        just_below = ScoringService.calculate_experience_match(4.9, 5)
        at_minimum = ScoringService.calculate_experience_match(5.0, 5)
        just_above = ScoringService.calculate_experience_match(5.1, 5)
        self.assertLess(at_minimum - just_below, 0.05)
        self.assertLess(just_above - at_minimum, 0.05)

    def test_unknown_experience_scores_lower_when_a_minimum_is_required(self):
        no_min = ScoringService.calculate_experience_match(None, None)
        with_min = ScoringService.calculate_experience_match(None, 5)
        self.assertGreater(no_min, with_min)

    def test_nice_to_have_skills_count_even_without_required_skills(self):
        full_match = ScoringService.calculate_skill_overlap(
            ["Docker", "Kubernetes"], [], ["Docker", "Kubernetes"]
        )
        no_match = ScoringService.calculate_skill_overlap(["Python"], [], ["Docker", "Kubernetes"])
        self.assertGreater(full_match["score"], no_match["score"])

    def test_unrecognized_required_skill_does_not_trigger_the_zero_match_penalty(self):
        # A required skill the taxonomy can't normalize (a typo, an obscure
        # tool) must not simultaneously get full coverage credit AND trigger
        # the zero-match penalty — an otherwise strong, relevant candidate
        # shouldn't be crushed by one unrecognized word in the requirements.
        result = ScoringService.score_candidate(0.85, ["Python", "FastAPI", "Docker"], ["Djangoo"], 5, 2)
        self.assertGreater(result["final_score"], 0.5)

    def test_zero_match_penalty_still_fires_for_a_real_missing_skill(self):
        result = ScoringService.score_candidate(0.85, ["Python", "FastAPI"], ["Java"], 5, 2)
        self.assertLess(result["final_score"], ScoringService.MIN_SCORE_THRESHOLD)

    def test_perfect_required_match_scores_full_marks_with_no_nice_to_have_requested(self):
        # Regression test: matching every required skill used to cap at 0.8
        # whenever no nice-to-have skills were specified at all — which is the
        # common case, since the Jobs page has no nice_to_have_skills field, so
        # this silently capped every application ranked there.
        result = ScoringService.calculate_skill_overlap(
            ["Python", "FastAPI", "Docker", "Kubernetes"],
            ["Python", "FastAPI", "Docker", "Kubernetes"],
            [],
        )
        self.assertEqual(result["score"], 1.0)

    def test_nice_to_have_bonus_still_applies_when_both_are_given(self):
        full_required_plus_nice = ScoringService.calculate_skill_overlap(
            ["Python", "Redis"], ["Python"], ["Redis"]
        )
        full_required_only = ScoringService.calculate_skill_overlap(["Python"], ["Python"], ["Redis"])
        self.assertGreater(full_required_plus_nice["score"], full_required_only["score"])


if __name__ == "__main__":
    unittest.main()


class UnknownSkillScoringTests(unittest.TestCase):
    def test_skill_outside_taxonomy_matches_on_resume_text(self):
        result = ScoringService.score_candidate(
            0.5, ["Excel"], ["Negotiation"], 3, 1, candidate_text="Led vendor negotiations for 3 years",
        )
        self.assertEqual(result["matched_skills"], ["Negotiation"])
        self.assertEqual(result["skill_overlap"], 1.0)

    def test_skill_outside_taxonomy_missing_from_text_lowers_score_without_penalty(self):
        with_skill = ScoringService.score_candidate(0.5, [], ["Negotiation"], 3, 1, candidate_text="negotiation")
        without = ScoringService.score_candidate(0.5, [], ["Negotiation"], 3, 1, candidate_text="Python developer")
        self.assertEqual(without["missing_skills"], ["Negotiation"])
        self.assertLess(without["final_score"], with_skill["final_score"])
        self.assertGreater(without["final_score"], 0.2)  # not crushed by the x0.3 zero-match penalty

    def test_without_resume_text_unknown_skills_are_unverified_not_missing(self):
        result = ScoringService.score_candidate(0.5, ["Python"], ["Python", "Negotiation"], 3, 1)
        self.assertEqual(result["unverified_skills"], ["Negotiation"])
        self.assertEqual(result["missing_skills"], [])

    def test_matched_and_missing_follow_the_required_order(self):
        result = ScoringService.score_candidate(0.5, ["Docker"], ["Python", "Docker", "Java"], 3, 1)
        self.assertEqual(result["matched_skills"], ["Docker"])
        self.assertEqual(result["missing_skills"], ["Python", "Java"])

    def test_semantic_calibration_is_monotonic_and_bounded(self):
        cal = ScoringService.calibrate_semantic
        self.assertEqual(cal(0.0), 0.0)
        self.assertEqual(cal(1.0), 1.0)
        self.assertLess(cal(0.3), cal(0.5))
        self.assertAlmostEqual(cal(0.4, floor=0.15, ceil=0.65), 0.5)
