import unittest

from vinnsyn.market_skills import CorpusPart, extract_explicit_skills


class MarketSkillExtractionTests(unittest.TestCase):
    def names(self, text: str) -> set[str]:
        return {match.name for match in extract_explicit_skills([CorpusPart("test", text)])}

    def test_extracts_english_and_icelandic_explicit_terms(self):
        names = self.names("Krafist er reynsla af Python, PostgreSQL og verkefnastjórnun. Ökuskírteini er kostur.")
        self.assertTrue({"Python", "PostgreSQL", "Project Management", "Driving Licence"}.issubset(names))

    def test_does_not_confuse_java_with_javascript(self):
        names = self.names("You will work with JavaScript and TypeScript.")
        self.assertIn("JavaScript", names)
        self.assertIn("TypeScript", names)
        self.assertNotIn("Java", names)

    def test_finds_symbol_based_programming_languages(self):
        names = self.names("C# and C++ experience is required.")
        self.assertTrue({"C#", "C++"}.issubset(names))

    def test_does_not_treat_a_website_domain_as_dotnet(self):
        self.assertNotIn(".NET", self.names("Read more at https://example.net/jobs."))
        self.assertIn(".NET", self.names("Experience with .NET is required."))

    def test_keeps_strongest_requirement_evidence(self):
        matches = extract_explicit_skills([CorpusPart("description", "Experience with Docker is a benefit."), CorpusPart("requirements", "Docker is required for this role.")])
        docker = next(match for match in matches if match.name == "Docker")
        self.assertEqual(docker.importance, "required")
        self.assertEqual(docker.source, "requirements")

    def test_does_not_treat_go_as_an_unqualified_word(self):
        self.assertNotIn("Go", self.names("We are ready to go and grow together."))
        self.assertIn("Go", self.names("Experience with Golang is required."))

    def test_keeps_languages_out_of_the_professional_skill_dimension(self):
        language = next(match for match in extract_explicit_skills([CorpusPart("test", "English is required.")]) if match.name == "English")
        self.assertEqual(language.dimension, "language")
