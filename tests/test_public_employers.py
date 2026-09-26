import unittest

from employer_normalization import build_employers


class EmployerIdentityTests(unittest.TestCase):
    def test_safe_variants_merge_without_merging_other_brands(self):
        catalog, by_listing, _ = build_employers([
            (1, "EFLA"), (2, "EFLA hf."), (3, " efla "),
            (4, "JBT Marel"), (5, "Marel hf."),
            (6, "Example hf"), (7, "Example ehf"), (8, "Example"),
        ])
        self.assertEqual(by_listing[1], by_listing[2])
        self.assertEqual(by_listing[2], by_listing[3])
        self.assertNotEqual(by_listing[4], by_listing[5])
        self.assertEqual(len({by_listing[6], by_listing[7], by_listing[8]}), 3)
        self.assertEqual(sum(item["listings"] for item in catalog), 8)

    def test_unidentified_and_intermediary_remain_visible(self):
        catalog, by_listing, stats = build_employers([
            (1, "Fyrirtæki á höfuðborgarsvæðinu"), (2, "Aðstoð óskast"),
            (3, "Hagvangur"), (4, "Hagvangur ehf"),
        ])
        self.assertEqual(by_listing[1], by_listing[2])
        self.assertEqual(by_listing[3], by_listing[4])
        self.assertEqual({item["kind"] for item in catalog}, {"unidentified", "intermediary"})
        self.assertEqual(stats["unidentifiedListings"], 2)
