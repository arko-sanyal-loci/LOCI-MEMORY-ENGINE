import unittest

from loci_engine.compressor import TfidfCompressor, approx_tokens, compress, split_sentences

DOC = (
    "The broker listens on port 8765 for MCP traffic. "
    "It was a sunny day and the weather was pleasant. "
    "Heat decays hyperbolically so old evidence never reaches zero. "
    "Lunch was rice and dal. "
    "The VRAM admission threshold theta_HOT is 0.70 after the sweep. "
    "Someone mentioned a nice cafe nearby. "
    "Glassbox entries are hash chained with SHA-256. "
    "The cat sat on the mat for a while."
) * 3


class CompressorTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(compress(DOC, "what port").text, compress(DOC, "what port").text)

    def test_hits_target_ratio_and_reports_it(self):
        r = TfidfCompressor().compress(DOC, "heat decay", target_ratio=4.0)
        self.assertGreaterEqual(r.ratio, 3.0)
        self.assertLess(r.compressed_tokens, r.original_tokens)
        self.assertAlmostEqual(r.savings, 1 - r.compressed_tokens / r.original_tokens)

    def test_query_relevant_sentence_survives(self):
        r = compress(DOC, "which port does the broker listen on", target_ratio=6.0)
        self.assertIn("8765", r.text)

    def test_exact_value_in_query_is_never_dropped(self):
        r = compress(DOC, "is 0.70 the threshold", max_tokens=1)
        self.assertIn("0.70", r.text)

    def test_preserves_original_order(self):
        r = compress("Alpha one. Beta two. Gamma three. Delta four.", "delta alpha", target_ratio=2)
        self.assertLess(r.text.find("Alpha"), r.text.find("Delta"))

    def test_empty(self):
        self.assertEqual(compress("").text, "")
        self.assertEqual(split_sentences(""), [])
        self.assertGreaterEqual(approx_tokens("x"), 1)

    def test_accepts_chunk_list(self):
        r = compress(["Port is 8765.", "Weather was fine."], "port", target_ratio=2)
        self.assertIn("8765", r.text)


if __name__ == "__main__":
    unittest.main()
