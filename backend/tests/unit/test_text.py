from app.schemas.filters import Experience
from app.services.text.jd_trimmer import extract_min_years, strip_html, trim_description
from app.services.text.prefilter import experience_fit, prefilter
from app.services.text.skills import canonical, expand_implied, extract_skills, is_grounded, normalize_skills
from tests.conftest import make_job


class TestSkills:
    def test_canonical_aliases(self):
        assert canonical("ReactJS") == "react"
        assert canonical("  Node JS ") == "node.js"
        assert canonical("Unknown Thing") == "unknown thing"

    def test_normalize_dedupes_preserving_order(self):
        assert normalize_skills(["Python", "py", "React.js", "", "react"]) == ["python", "react"]

    def test_extract_handles_symbols_and_longest_match(self):
        text = "We use C++, C#, Node.js and React Native; JavaScript and CI/CD."
        found = extract_skills(text)
        assert {"c++", "c#", "node.js", "react native", "javascript", "ci/cd"} <= set(found)
        assert "java" not in found
        assert "react" not in found  # swallowed by "react native"

    def test_no_false_positive_for_common_words(self):
        assert extract_skills("We excel at the rest of our goals") == []

    def test_grounding_rejects_invented_skills(self):
        text = "Must know Python and MongoDB"
        assert is_grounded("python", text)
        assert is_grounded("mongo", text)
        assert not is_grounded("kubernetes", text)

    def test_mern_implies_parts(self):
        assert {"react", "node.js", "mongodb", "express"} <= expand_implied(["mern"])


class TestTrimmer:
    def test_strip_html(self):
        assert strip_html("<p>Hello&nbsp;<b>world</b></p><li>React</li>") == "Hello world\nReact"

    def test_keeps_requirements_drops_benefits(self):
        jd = "About us:\nWe are great.\nRequirements:\nPython 3 years\nBenefits:\nFree snacks\nEqual opportunity employer"
        out = trim_description(jd)
        assert "Python 3 years" in out
        assert "snacks" not in out and "Equal" not in out
        assert "We are great" not in out

    def test_prefers_highlights_and_caps_length(self):
        assert trim_description("ignored", ["Know React", "Ship code"]) == "- Know React\n- Ship code"
        assert len(trim_description("x" * 10_000, max_chars=500)) == 500

    def test_min_years(self):
        assert extract_min_years("3-5 years of experience, ideally 2+ yrs with React") == 2.0
        assert extract_min_years("no experience needed") is None


class TestPrefilter:
    def test_experience_fit(self):
        assert experience_fit(2, Experience.ANY, 3) == 1.0
        assert experience_fit(5, Experience.ANY, 3) == 0.5
        assert experience_fit(None, Experience.ANY, None) == 0.7
        assert experience_fit(4, Experience.JUNIOR, None) == 0.75  # junior upper bound = 3

    def test_ranks_relevant_jobs_first_and_caps_top_k(self):
        jobs = [
            make_job(1, title="Python React Developer"),
            make_job(2, title="Accountant", desc="Requirements: Tally, GST filing, ms excel"),
            make_job(3, title="Senior Python Engineer", desc="Requirements: Python, FastAPI, 8 years"),
        ]
        kept = prefilter(jobs, "Python Developer", ["python", "react", "mongodb"], top_k=2)
        assert len(kept) == 2
        assert kept[0].job.external_id == "ext-1"
        assert all(c.job.title != "Accountant" for c in kept)


def test_split_requirements_by_cue_and_section():
    from app.services.text.skills import split_requirements

    text = "Requirements:\nPython and React\nDocker is a plus\nNice to have:\nAWS\nKubernetes"
    required, nice = split_requirements(text)
    assert required == ["python", "react"]
    assert nice == ["docker", "aws", "kubernetes"]


def test_frameworks_imply_language_and_web_basics():
    have = expand_implied(["react", "node.js", "redux", "fastapi"])
    assert {"javascript", "html", "css", "python", "rest api"} <= have
    assert "java" not in have


def test_normalize_splits_known_compound_skills():
    assert normalize_skills(["JavaScript/TypeScript"]) == ["javascript", "typescript"]
    assert normalize_skills(["ci/cd", "foo/bar"]) == ["ci/cd", "foo/bar"]  # known or unknown wholes stay intact
