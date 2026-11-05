import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import update_readme as u  # noqa: E402


def repo(name, stars=0, fork=False, desc="d", lang="Python", archived=False):
    return {"name": name, "stargazers_count": stars, "fork": fork, "description": desc, "language": lang,
            "archived": archived, "forks_count": 0, "html_url": f"https://github.com/x/{name}",
            "pushed_at": "2026-01-01T00:00:00Z"}


class Tests(unittest.TestCase):
    def test_featured_skips_forks_archived_and_profile_repo(self):
        out = u.render_featured([repo("a", 5), repo("b", 9, fork=True), repo("c", 1, archived=True), repo(u.USER, 99)])
        self.assertIn("[**a**]", out)
        for bad in ("[**b**]", "[**c**]", f"[**{u.USER}**]"):
            self.assertNotIn(bad, out)

    def test_featured_sorted_and_pipe_escaped(self):
        out = u.render_featured([repo("low", 1), repo("high", 7, desc="a|b")])
        self.assertLess(out.index("high"), out.index("low"))
        self.assertIn("a\\|b", out)

    def test_empty_description_fallback(self):
        self.assertIn("| — |", u.render_featured([repo("a", desc="")]))

    def test_null_pushed_at_does_not_crash(self):
        r = repo("empty")
        r["pushed_at"] = None
        self.assertIn("[**empty**]", u.render_featured([r, repo("b", 1)]))

    def test_truncation_never_splits_escape(self):
        out = u.render_featured([repo("a", desc="x" * 106 + "|" + "y" * 20)])
        row = out.splitlines()[-1]
        self.assertIn("\\|...", row)
        self.assertNotIn("\\ ", row)  # no dangling backslash before the cell separator
        self.assertEqual(row.count("|") - row.count("\\|"), 5)

    def test_badge_underscore_escaped(self):
        out = u.render_stats({"public_repos": 1, "followers": 1}, [repo("a", lang="my_lang")])
        self.assertIn("my__lang", out)

    def test_replace_section(self):
        t = "x<!--START_SECTION:s-->old<!--END_SECTION:s-->y"
        self.assertEqual(u.replace_section(t, "s", "new"), "x<!--START_SECTION:s-->\nnew\n<!--END_SECTION:s-->y")
        with self.assertRaises(KeyError):
            u.replace_section(t, "missing", "z")

    def test_activity(self):
        ev = [{"type": "PushEvent", "repo": {"name": "u/r"}, "payload": {"size": 2}, "created_at": "2026-01-02T00:00:00Z"},
              {"type": "GollumEvent", "repo": {"name": "u/r"}, "created_at": "2026-01-02T00:00:00Z"}]
        out = u.render_activity(ev)
        self.assertIn("Pushed 2 commits", out)
        self.assertEqual(out.count("\n"), 0)
        self.assertIn("No recent", u.render_activity([]))


if __name__ == "__main__":
    unittest.main()
