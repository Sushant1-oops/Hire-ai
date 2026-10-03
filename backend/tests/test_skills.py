import unittest

from ai.skills_extractor import SkillsExtractor

ex = SkillsExtractor()


class SkillNormalisationTests(unittest.TestCase):
    def test_known_skills_become_canonical_and_unknown_are_kept(self):
        out = ex.normalize_list(["postgres", "k8s", "Negotiation", "Cold calling"])
        self.assertEqual(out, ["PostgreSQL", "Kubernetes", "Negotiation", "Cold calling"])

    def test_duplicates_and_sentences_are_dropped(self):
        out = ex.normalize_list(["Python", "python 3", "PYTHON", "x " * 40])
        self.assertEqual(out, ["Python"])

    def test_go_is_found_only_in_list_position(self):
        self.assertIn("Golang", ex.extract("Languages: Python, Go, SQL"))
        self.assertNotIn("Golang", ex.extract("Experience in go-to-market strategy"))

    def test_mentions_is_whole_word_and_tolerates_hyphen_and_plural(self):
        self.assertTrue(ex.mentions("Led contract negotiations", "negotiation"))
        self.assertTrue(ex.mentions("Cold-calling prospects", "cold calling"))
        self.assertFalse(ex.mentions("Prenegotiationless", "negotiation"))

    def test_is_known(self):
        self.assertTrue(ex.is_known("PostgreSQL"))
        self.assertFalse(ex.is_known("Negotiation"))
