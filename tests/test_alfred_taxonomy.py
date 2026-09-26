import unittest

from vinnsyn.alfred_taxonomy import job_text_parts, profession_tags, source_categories, structured_skill_matches


class AlfredTaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.job = {
            "categories": [{"id": 2, "name": "Iðnaðarstörf", "slug": "idnadarstorf", "jobTags": [{"id": 68, "name": "Vélstjóri"}]}],
            "skills": [
                {"name": "Vélvirkjun", "subCategories": [{"name": "Löggildar iðngreinar"}]},
                {"name": "Stundvísi", "subCategories": [{"name": "Almennt"}]},
                {"name": "Hreint sakavottorð", "subCategories": [{"name": "Almenn skilyrði"}]},
            ],
            "languages": [{"languageName": "Enska", "skillName": "Mjög góð", "required": True}],
            "customSections": [{"label": "qualifications", "content": "<p>Lyftarapróf er kostur.</p>"}],
        }

    def test_categories_and_professions_are_first_party_taxonomy(self):
        area = source_categories(self.job)[0]
        self.assertEqual(area.area.key, "industrial-trades")
        self.assertEqual(profession_tags(self.job)[0].name, "Vélstjóri")

    def test_direct_skills_are_dimensioned_and_conditions_are_excluded(self):
        matches = {item.name: item for item in structured_skill_matches(self.job)}
        self.assertEqual(matches["Vélvirkjun"].dimension, "professional_skill")
        self.assertEqual(matches["Stundvísi"].dimension, "employer_quality")
        self.assertEqual(matches["English"].importance, "required")
        self.assertNotIn("Hreint sakavottorð", matches)

    def test_only_qualification_and_responsibility_sections_are_searchable(self):
        parts = job_text_parts(self.job)
        self.assertEqual([(part.source, part.text) for part in parts], [("alfred:custom:qualifications", "Lyftarapróf er kostur.")])
