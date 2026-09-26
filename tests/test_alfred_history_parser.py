import json
import unittest

from scripts.fetch_alfred_history import extract_listing, metadata_snapshot


class AlfredHistoryParserTests(unittest.TestCase):
    url = "https://alfred.is/starf/adstod-i-eldhusi-help-in-kitchen"
    row = {
        "url": url, "canonical_url": url, "archive_index": "direct_alfred",
        "crawl_timestamp": "20260922103951", "content_digest": None,
    }

    def page(self, slug="adstod-i-eldhusi-help-in-kitchen"):
        job = {
            "id": 72561, "slug": slug,
            "title": "Aðstoð í eldhúsi/help in kitchen",
            "brand": {"name": "Matarkompani"},
            "published": "2022-05-31T08:50:19Z",
            "bodyhtml": "<p>almennt eldhús starf, þrif, undirbúningur</p>",
            "address": {"formatted": "Hlíðasmári 8, 201 Kópavogur"},
            "jobType": "Fullt starf",
        }
        payload = {"props": {"pageProps": {"initialJobData": {"job": job}}}}
        return (
            "<html><head><title>Aðstoð í eldhúsi/help in kitchen | Matarkompani</title></head>"
            "<body><h1>Aðstoð í eldhúsi/help in kitchen</h1>"
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
            "</body></html>"
        )

    def test_live_next_job_has_reliable_metadata(self):
        source = self.page()
        listing = extract_listing(self.row, source)
        self.assertIsNotNone(listing)
        self.assertEqual((listing.title, listing.company), ("Aðstoð í eldhúsi/help in kitchen", "Matarkompani"))
        self.assertEqual(listing.posted_date, "2022-05-31T08:50:19Z")
        self.assertEqual(listing.location, "Hlíðasmári 8, 201 Kópavogur")
        self.assertEqual(listing.description, "almennt eldhús starf, þrif, undirbúningur")
        self.assertEqual(metadata_snapshot(self.row, source)["posted_date_candidates"][0], "2022-05-31T08:50:19Z")

    def test_different_job_slug_is_not_imported_under_requested_url(self):
        self.assertIsNone(extract_listing(self.row, self.page("another-job")))

    def test_generic_alfred_page_is_not_a_listing(self):
        self.assertIsNone(extract_listing(self.row, "<html><head><title>Störf | Alfreð</title></head><body><h1>Störf</h1></body></html>"))


if __name__ == "__main__":
    unittest.main()
