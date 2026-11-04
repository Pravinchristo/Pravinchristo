import os
import sys
import unittest
import zipfile
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixtures import JD_DATA, RESUME_KEYWORDS, RESUME_STRONG  # noqa: E402
from markjoe import analytics, evaluate, export, hunt, intake, service  # noqa: E402
from markjoe import skills as sk  # noqa: E402
from markjoe.db import DB, norm_url  # noqa: E402


def fresh():
    db = DB(":memory:")
    db.seed()
    return db


def live_requirement(db):
    r = intake.create_requirement(db, JD_DATA)
    intake.answer(db, r["id"], "10")
    ids = [c["id"] for c in db.q("SELECT id, name FROM sourcing_channels") if c["name"] in ("LinkedIn Recruiter", "Naukri")]
    hunt.confirm_channels(db, intake.get(db, r["id"]), ids)
    service.plan(db, r["id"])
    hunt.approve_plan(db, intake.get(db, r["id"]))
    return intake.get(db, r["id"])


ALPHA = {"full_name": "Test Candidate Alpha", "resume_text": RESUME_STRONG, "location": "Bengaluru",
         "current_company": "Example Bank Ltd", "linkedin_url": "https://www.linkedin.com/in/test-alpha/",
         "source_channel": "LinkedIn Recruiter", "notice_period_days": 45}
BETA = {"full_name": "Test Candidate Beta", "resume_text": RESUME_KEYWORDS, "location": "Pune",
        "source_url": "https://example.com/beta", "source_channel": "Naukri", "notice_status": "immediate"}


class IntakeTests(unittest.TestCase):
    def test_parse_jd_reads_fields_and_sections(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        self.assertEqual(r["title"], "Senior Data Engineer")
        self.assertEqual((r["exp_min"], r["exp_max"]), (6.0, 10.0))
        self.assertEqual(r["work_mode"], "hybrid")
        self.assertEqual(r["notice_max_days"], 60)
        self.assertIn("Kafka", r["mandatory_skills"])
        self.assertIn("Airflow", r["preferred_skills"])
        self.assertNotIn("Airflow", r["mandatory_skills"])
        self.assertEqual(r["job_family"], "data_engineering")

    def test_does_not_ask_what_jd_answers_and_asks_one_at_a_time(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        q = intake.next_question(db, r)
        self.assertEqual(q["key"], "profiles_required")  # only essential gap
        keys = [x["key"] for x in intake.pending_questions(r, sk.library(db))]
        for k in ("title", "experience", "location", "work_mode", "notice_period", "mandatory_skills"):
            self.assertNotIn(k, keys)
        self.assertTrue(q["why"])

    def test_followup_relaxes_skill_without_promoting_related(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        intake.answer(db, r["id"], "10")
        r, q, info = intake.answer(db, r["id"], "No, Spark on EMR is fine", key="fu_databricks")
        self.assertNotIn("Databricks", r["mandatory_skills"])
        self.assertIn("Databricks", r["preferred_skills"])
        self.assertIn("AWS EMR", r["transferable_skills"])
        # related skills (e.g. Hive via Spark) are never made mandatory
        self.assertNotIn("Hive", r["mandatory_skills"])

    def test_followup_yes_sets_required_evidence_level(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        r, _, _ = intake.answer(db, r["id"], "yes", key="fu_kafka")
        self.assertEqual(r["intake"]["required_levels"]["Kafka"], "production")

    def test_contradictions(self):
        lib = sk.library()
        w = intake.market_warnings({"title": "Junior QA", "exp_min": 9, "exp_max": 5, "mandatory_skills": ["AWS", "Azure", "Selenium", "Playwright"], "intake": {}}, lib)
        types = " ".join(x["text"] for x in w)
        self.assertIn("higher than the maximum", types)
        self.assertIn("junior", types.lower())
        self.assertIn("AWS and Azure", types)
        self.assertIn("alternatives", types)

    def test_experience_parser(self):
        self.assertEqual(intake.parse_experience("5-8 years"), (5.0, 8.0))
        self.assertEqual(intake.parse_experience("6+ years"), (6.0, None))
        self.assertEqual(intake.parse_notice("2 months"), 60)
        self.assertEqual(intake.parse_notice("immediate"), 0)


class HuntTests(unittest.TestCase):
    def test_plan_requires_gate_and_builds_all_strings(self):
        db = fresh()
        r = live_requirement(db)
        plan = db.one("SELECT payload FROM search_strategies WHERE requirement_id=? AND status='approved'", (r["id"],))["payload"]
        b = plan["booleans"]
        for k in ("broad", "narrow", "skill_based", "designation_based", "immediate_joiner", "open_to_work", "alternative_skill"):
            self.assertTrue(b[k], k)
        self.assertTrue(b["xray"]["linkedin"].startswith("site:linkedin.com/in"))
        self.assertTrue(b["company_specific"])
        self.assertTrue(b["github"]["user_search"])
        for k in ("immediate_joiner", "open_to_work"):
            self.assertNotIn('""', b[k])  # phrases quoted once, not twice
        self.assertIn('"open to work"', b["open_to_work"])
        self.assertTrue(all(not s["connected"] for s in plan["channels"]))  # nothing claimed as connected
        mem = db.q("SELECT * FROM channel_memory WHERE requirement_id=?", (r["id"],))
        self.assertEqual(len(mem), 2)

    def test_cannot_add_candidates_before_approval(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        with self.assertRaises(PermissionError):
            service.add_candidate(db, r["id"], ALPHA)

    def test_search_needs_evidence(self):
        db = fresh()
        r = live_requirement(db)
        ch = db.one("SELECT id FROM sourcing_channels WHERE name='Naukri'")["id"]
        with self.assertRaises(ValueError):
            hunt.log_search(db, r["id"], ch, "q", 3, "")

    def test_excluded_companies_removed(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA + "\nExclude: Tiger Analytics\n")
        rows = hunt.map_companies(db, r, sk.library(db))
        self.assertNotIn("Tiger Analytics", [x["name"] for x in rows])


class JoeTests(unittest.TestCase):
    def test_strong_resume_scores_high_with_evidence(self):
        db = fresh()
        r = live_requirement(db)
        res = service.add_candidate(db, r["id"], ALPHA)["evaluation"]
        self.assertGreaterEqual(res["total"], 70)
        self.assertEqual(res["critical_gaps"], [])
        self.assertEqual(res["skill_evidence"]["Kafka"]["level"], "production")
        self.assertTrue(res["skill_evidence"]["Spark"]["evidence"])
        self.assertIn("Resume states 8 years", " ".join(f["text"] for f in res["flags"]))

    def test_keyword_resume_is_not_proof(self):
        db = fresh()
        r = live_requirement(db)
        res = service.add_candidate(db, r["id"], BETA)["evaluation"]
        self.assertLess(res["total"], 55)
        self.assertIn("Spark", res["critical_gaps"])
        self.assertEqual(res["skill_evidence"]["Spark"]["level"], "mentioned")
        # immediate claim without evidence is challenged and not counted
        self.assertTrue(any(c["by"] == "JOE" for c in res["challenges"]))
        s = analytics.state(db)
        self.assertEqual(s["overview"]["immediate_joiners"], 0)

    def test_sensitive_fields_ignored(self):
        lib = sk.library()
        req = {"mandatory_skills": ["Python"], "exp_min": 1}
        a = evaluate.evaluate(req, {"resume_text": "Gender: Male\nJan 2020 - Jan 2022 Built Python services."}, lib)
        b = evaluate.evaluate(req, {"resume_text": "Gender: Female\nJan 2020 - Jan 2022 Built Python services."}, lib)
        self.assertEqual(a["total"], b["total"])

    def test_critical_gap_flagged_even_with_high_score(self):
        lib = sk.library()
        req = {"mandatory_skills": ["Python", "SQL"], "critical_skills": ["SQL"], "exp_min": 2}
        txt = "Jan 2018 - Present\nBuilt Python services in production. Led a team of 4. Architected the Python platform. Skills: SQL"
        res = evaluate.evaluate(req, {"resume_text": txt, "location": "Pune", "notice_period_days": 0, "availability_verified": 1}, lib)
        self.assertIn("SQL", res["critical_gaps"])
        self.assertTrue(res["recommendation"].startswith("Hold") or res["total"] < 55)

    def test_experience_merges_overlaps_and_finds_gaps(self):
        import datetime
        e = evaluate.experience("A  Jan 2015 - Dec 2016\nB  Jun 2016 - Dec 2017\nC  Jan 2019 - Dec 2019", datetime.date(2026, 11, 4))
        self.assertEqual(e["total_years"], 4.0)
        self.assertEqual(e["gaps"][0]["months"], 12)

    def test_duplicates_by_normalised_url(self):
        db = fresh()
        r = live_requirement(db)
        service.add_candidate(db, r["id"], ALPHA)
        dup = service.add_candidate(db, r["id"], {"full_name": "Someone", "linkedin_url": "http://in.linkedin.com/in/Test-Alpha?trk=x", "source_channel": "Naukri"})
        self.assertTrue(dup["duplicate"])
        self.assertEqual(norm_url("https://www.linkedin.com/in/abc/"), "linkedin.com/in/abc")

    def test_agents_cannot_submit(self):
        db = fresh()
        r = live_requirement(db)
        cid = service.add_candidate(db, r["id"], ALPHA)["candidate_id"]
        with self.assertRaises(PermissionError):
            service.set_status(db, r["id"], cid, "submitted", actor="MARK")
        service.set_status(db, r["id"], cid, "submitted", actor="recruiter")
        self.assertEqual(analytics.state(db)["overview"]["submitted"], 1)

    def test_audit_trail_on_correction(self):
        db = fresh()
        r = live_requirement(db)
        cid = service.add_candidate(db, r["id"], ALPHA)["candidate_id"]
        service.update_candidate(db, cid, {"notice_period_days": 30, "availability_evidence": "Confirmed on call"})
        a = db.q("SELECT * FROM audit_log WHERE entity='candidates' AND action='update'")
        self.assertTrue(a)
        self.assertEqual(db.one("SELECT availability_verified FROM candidates WHERE id=?", (cid,))["availability_verified"], 1)


class AnalyticsTests(unittest.TestCase):
    def test_empty_database_has_no_invented_numbers(self):
        s = analytics.state(fresh())
        o = s["overview"]
        self.assertEqual(sum(v for k, v in o.items() if isinstance(v, int)), 0)
        self.assertEqual(s["candidates"], [])
        self.assertEqual(s["channel_performance"], [])

    def test_metrics_and_exports(self):
        db = fresh()
        r = live_requirement(db)
        service.add_candidate(db, r["id"], ALPHA)
        service.add_candidate(db, r["id"], BETA)
        s = analytics.state(db, {"requirement": r["id"]})
        self.assertEqual(s["overview"]["profiles_sourced"], 2)
        self.assertEqual(s["funnel"][0]["count"], 2)
        self.assertEqual({c["channel"] for c in s["channel_performance"]}, {"LinkedIn Recruiter", "Naukri"})
        self.assertEqual(len(analytics.candidate_rows(db, {"min_score": 70})), 1)
        csv = export.to_csv(s["candidates"]).decode("utf-8-sig")
        self.assertIn("Test Candidate Alpha", csv)
        z = zipfile.ZipFile(io.BytesIO(export.to_xlsx(s["candidates"])))
        self.assertIn("xl/worksheets/sheet1.xml", z.namelist())
        self.assertIn("Test Candidate Beta", z.read("xl/worksheets/sheet1.xml").decode())
        ref = hunt.refine(db, intake.get(db, r["id"]))
        self.assertEqual(ref["evaluated"], 2)


class PortalTests(unittest.TestCase):
    def test_recruiter_portals_seeded_and_preapproved(self):
        db = fresh()
        rows = {r["name"]: r for r in db.q("SELECT * FROM sourcing_channels WHERE name IN ('OctoHunt','SourceGo')")}
        self.assertEqual(rows["OctoHunt"]["url"], "https://octohunt.com/")
        self.assertEqual(rows["SourceGo"]["url"], "https://sourcego.blogspot.com/")
        for r in rows.values():
            self.assertEqual(r["approved"], 1)
            self.assertEqual(r["connected"], 0)  # never claimed as connected

    def test_plan_hands_each_portal_the_right_strings(self):
        db = fresh()
        r = intake.create_requirement(db, JD_DATA)
        intake.answer(db, r["id"], "10")
        ids = [c["id"] for c in db.q("SELECT id FROM sourcing_channels WHERE name IN ('OctoHunt','SourceGo')")]
        hunt.confirm_channels(db, intake.get(db, r["id"]), ids)
        steps = {s["channel"]: s for s in service.plan(db, r["id"])["channels"]}
        self.assertIn("language:", steps["OctoHunt"]["string"])
        self.assertIn("site:linkedin.com/in", steps["SourceGo"]["string"])
        self.assertTrue(steps["OctoHunt"]["execution"].startswith("manual"))

    def test_old_database_is_migrated_and_backfilled(self):
        import sqlite3
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE sourcing_channels (id TEXT PRIMARY KEY, name TEXT UNIQUE, category TEXT, connected INTEGER DEFAULT 0, connection_evidence TEXT, connection_verified_at TEXT, access_permission TEXT, methodology TEXT, filters TEXT, manual_only INTEGER DEFAULT 1, active INTEGER DEFAULT 1, approved INTEGER DEFAULT 0, recruiter_feedback TEXT, date_added TEXT, date_last_used TEXT)")
        con.execute("INSERT INTO sourcing_channels (id, name, category, approved) VALUES ('CH-1', 'GitHub', 'x', 1)")
        con.commit(); con.close()
        db = DB(path)
        db.seed()
        self.assertEqual(db.one("SELECT string_type FROM sourcing_channels WHERE id='CH-1'")["string_type"], "github")
        self.assertTrue(db.one("SELECT id FROM sourcing_channels WHERE name='OctoHunt'"))

    def test_custom_portal_with_url(self):
        db = fresh()
        c = service.upsert_channel(db, "My Portal", "Portal", url="https://example.org/", string_type="xray")
        self.assertEqual((c["url"], c["string_type"]), ("https://example.org/", "xray"))
        with self.assertRaises(ValueError):
            service.upsert_channel(db, "Bad", string_type="scrape")


if __name__ == "__main__":
    unittest.main()
