import unittest
from datetime import datetime

import re

from ai.extraction import (
    extract_education, extract_email, extract_experience, extract_name, extract_phone,
    merged_months, normalize_phone, parse_resume,
)
from ai.skills_extractor import SkillsExtractor

NOW = datetime(2026, 9, 29)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.x = SkillsExtractor()

    def test_c_not_matched_from_cpp_or_grade(self):
        self.assertEqual(self.x.extract("Languages: Python, C++, Java\nGrade C. R&D"), ["C++", "Java", "Python"])

    def test_c_and_r_matched_in_list_position(self):
        found = self.x.extract("Skills: C, R and SQL")
        self.assertIn("C", found)
        self.assertIn("R", found)

    def test_prose_word_express_ignored_but_express_js_found(self):
        self.assertNotIn("Express", self.x.extract("I express interest in this role"))
        self.assertIn("Express", self.x.extract("Built APIs with Express.js"))

    def test_aliases_normalise(self):
        self.assertEqual(self.x.extract("postgres, k8s, sklearn"), ["Kubernetes", "PostgreSQL", "Scikit-learn"])

    def test_langchain_casing_normalises(self):
        self.assertEqual(self.x.extract("Used langchain and Langchain and LangChain"), ["LangChain"])

    def test_hugging_face_variants_collapse_to_one_skill(self):
        found = self.x.extract("Hugging Face Transformers, Hugging Face, HuggingFace")
        self.assertEqual(found, ["Hugging Face Transformers"])

    def test_curated_list_is_case_insensitive(self):
        self.assertEqual(self.x.extract_from_list(["python", "r"]), ["Python", "R"])

    def test_unrecognised_skills_reported(self):
        text = "Skills:\nLanguages: Python, Brainfuckish\n\nExperience"
        self.assertEqual(self.x.unrecognised_from_skills_section(text), ["Brainfuckish"])


class ExperienceTests(unittest.TestCase):
    def test_overlapping_jobs_counted_once(self):
        self.assertEqual(merged_months([(0, 24), (12, 36)]), 36)
        self.assertEqual(merged_months([(0, 12), (24, 36)]), 24)

    def test_education_dates_excluded(self):
        text = "Experience\nIntern  Jun 2025 - Aug 2025\n\nEducation\nB.Tech, ABC College 2019 - 2023"
        years, source = extract_experience(text, NOW)
        self.assertEqual(source, "computed")
        self.assertLess(years, 0.5)

    def test_education_lines_excluded_without_section_headers(self):
        text = "B.Tech at ABC College 2019 - 2023\nEngineer at X Jan 2024 - Dec 2024"
        years, _ = extract_experience(text, NOW)
        self.assertAlmostEqual(years, 0.9, delta=0.2)

    def test_stated_years_win(self):
        self.assertEqual(extract_experience("5+ years of experience in software", NOW), (5.0, "stated"))

    def test_stated_years_and_months_combo(self):
        years, source = extract_experience("I have 3 years and 6 months of experience in backend development", NOW)
        self.assertEqual(source, "stated")
        self.assertAlmostEqual(years, 3.5, delta=0.05)

    def test_present_end_date(self):
        years, _ = extract_experience("Experience\nDev  Sep 2024 - Present", NOW)
        self.assertAlmostEqual(years, 2.0, delta=0.1)

    def test_short_apostrophe_year_dates(self):
        years, source = extract_experience("Experience\nEngineer, Acme   Jun'23 - Aug'25", NOW)
        self.assertEqual(source, "computed")
        self.assertAlmostEqual(years, 2.2, delta=0.2)

    def test_short_numeric_year_dates(self):
        years, source = extract_experience("Experience\nAnalyst, Beta   06/22 - 01/24", NOW)
        self.assertEqual(source, "computed")
        self.assertAlmostEqual(years, 1.6, delta=0.2)

    def test_fresher_with_no_dates_is_zero_not_none(self):
        self.assertEqual(extract_experience("Fresher, actively looking for opportunities", NOW), (0.0, "stated"))

    def test_none_when_nothing_found(self):
        self.assertEqual(extract_experience("no dates here", NOW), (None, "none"))


class SectionAwareTests(unittest.TestCase):
    """Regression tests for a real resume: a student with no Experience section,
    where a degree's year range and an aspirational skills clause were being
    mistaken for work experience and current skills."""

    RESUME = (
        "Aadarsh Mishra\n"
        "Full-Stack Developer Intern Candidate | React, Node.js & TypeScript\n"
        "aadarsh@example.com | 7678386067\n\n"
        "Objective\n"
        "Third-year BTech student building production web apps.\n\n"
        "Technical Skills\n"
        "Languages: Python, JavaScript, TypeScript, C++, SQL "
        "(comfortable picking up new languages such as Java, Go, or Scala)\n"
        "Backend: Node.js, Express.js, REST API design\n\n"
        "Projects\n"
        "Xc Craft - AI Post Generator\n"
        "- Built with React, PostgreSQL, OAuth\n\n"
        "Education\n"
        "Delhi Technical Campus (GGSIPU) (2023-2027)\n"
        "Bachelor of Technology - Artificial Intelligence & Machine Learning\n"
        "CGPA: 8.5/10.0\n"
    )

    def test_degree_year_range_is_not_counted_as_experience(self):
        years, source = extract_experience(self.RESUME, NOW)
        self.assertIsNone(years)
        self.assertEqual(source, "none")

    def test_aspirational_languages_excluded_from_skills(self):
        parsed = parse_resume(self.RESUME)
        self.assertNotIn("Java", parsed["skills"])
        self.assertNotIn("Scala", parsed["skills"])

    def test_degree_major_not_extracted_as_a_skill(self):
        parsed = parse_resume(self.RESUME)
        self.assertNotIn("Machine Learning", parsed["skills"])

    def test_actual_stack_still_extracted(self):
        parsed = parse_resume(self.RESUME)
        for expected in ("Python", "TypeScript", "React", "Node.js", "PostgreSQL", "OAuth2"):
            self.assertIn(expected, parsed["skills"])

    def test_experience_header_present_still_computes_normally(self):
        text = self.RESUME.replace(
            "Education\nDelhi Technical Campus (GGSIPU) (2023-2027)",
            "Experience\nIntern, Acme  Jan 2024 - Jan 2025\n\nEducation\nDelhi Technical Campus (GGSIPU) (2023-2027)",
        )
        years, source = extract_experience(text, NOW)
        self.assertEqual(source, "computed")
        self.assertAlmostEqual(years, 1.0, delta=0.1)


class CidArtifactTests(unittest.TestCase):
    def test_cid_glyph_placeholders_are_stripped_from_extracted_text(self):
        # Simulates pdfplumber's fallback output for an icon font it can't map,
        # as seen in a real resume that used icon glyphs for contact bullets.
        raw_like = "github (cid:239) linkedin (cid:128) portfolio"
        cleaned = re.sub(r"\(cid:\d+\)", " ", raw_like)
        self.assertNotIn("cid:", cleaned)


class ContactTests(unittest.TestCase):
    def test_email_lowercased(self):
        self.assertEqual(extract_email("Contact: Jane.Doe@Mail.COM."), "jane.doe@mail.com")

    def test_phone_normalisation(self):
        self.assertEqual(normalize_phone("+91 98107 38102"), "+919810738102")
        self.assertIsNone(normalize_phone("12345"))

    def test_phone_not_taken_from_long_digit_run(self):
        self.assertEqual(extract_phone("id 1234567890123 call 98107-38102"), "9810738102")


class NameTests(unittest.TestCase):
    def test_clean_name_scores_high(self):
        name, conf, method = extract_name("Jane Doe\nSenior Engineer\njane.doe@mail.com", "jane.doe@mail.com")
        self.assertEqual(name, "Jane Doe")
        self.assertGreaterEqual(conf, 0.9)

    def test_all_caps_is_title_cased(self):
        self.assertEqual(extract_name("SUSHANT THAKUR\nAI Engineer", None)[0], "Sushant Thakur")

    def test_name_on_line_with_pipe_separated_contact_info(self):
        text = "Sushant Thakur | Faridabad, Haryana | +91-9310738102 | thakursushant792@gmail.com"
        name, conf, _ = extract_name(text, "thakursushant792@gmail.com")
        self.assertEqual(name, "Sushant Thakur")
        self.assertGreaterEqual(conf, 0.6)

    def test_name_with_dash_separated_title_on_same_line(self):
        name, _conf, _ = extract_name("Priya Nair - Data Analyst\npriya.n@example.com", "priya.n@example.com")
        self.assertEqual(name, "Priya Nair")

    def test_role_line_not_a_name(self):
        name, conf, _ = extract_name("Senior Software Engineer\nBuilding things", None)
        self.assertLess(conf, 0.6)

    def test_email_fallback_is_low_confidence(self):
        name, conf, method = extract_name("12345\n!!!", "priya.nair@x.com")
        self.assertEqual((name, method), ("Priya Nair", "email"))
        self.assertLess(conf, 0.6)


class EducationTests(unittest.TestCase):
    def test_word_be_is_not_a_degree(self):
        self.assertEqual(extract_education("we should be ready to be there"), [])

    def test_be_degree_detected(self):
        self.assertEqual(extract_education("B.E. in Computer Science"), [{"degree": "B.E."}])

    def test_scrum_master_is_not_a_masters(self):
        self.assertEqual(extract_education("Certified Scrum Master"), [])


class ExtractionRegressionTests(unittest.TestCase):
    def test_experience_is_summed_over_every_experience_section(self):
        text = (
            "Jane Doe\nWORK EXPERIENCE\nEngineer, Acme  Jan 2020 - Dec 2021\n"
            "PROJECTS\nA side project\nINTERNSHIPS\nIntern, Foo  Jun 2018 - Dec 2018\n"
            "EDUCATION\nB.Tech 2014-2018\n"
        )
        years, source = extract_experience(text, now=datetime(2024, 1, 1))
        self.assertEqual(source, "computed")
        self.assertEqual(years, 2.4)  # 23 months of work + 6 months in the later INTERNSHIPS block (1.9 if it were ignored)

    def test_email_glued_to_following_word_is_trimmed(self):
        self.assertEqual(extract_email("jane.doe@mail.comLinkedIn linkedin.com/in/jane"), "jane.doe@mail.com")
        self.assertEqual(extract_email("Contact JANE@Example.org."), "jane@example.org")

    def test_degree_words_outside_the_education_section_are_ignored(self):
        text = "Led Master Data Management program\nSKILLS\nPython\nEDUCATION\nB.Tech, Delhi University"
        self.assertEqual(extract_education(text), [{"degree": "B.Tech"}])


if __name__ == "__main__":
    unittest.main()
