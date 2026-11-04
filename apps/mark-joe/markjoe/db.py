"""Persistent store (SQLite) for the MARK & JOE command centre.

Every table that a recruiter can change goes through `update_record`, which
writes an audit row with the before and after values.
"""
import datetime
import json
import os
import re
import secrets
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
DEFAULT_DB = os.environ.get("MARKJOE_DB", os.path.join(os.path.dirname(HERE), "var", "markjoe.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS requirements (
  id TEXT PRIMARY KEY, title TEXT, jd_text TEXT, job_family TEXT,
  exp_min REAL, exp_max REAL, location TEXT, work_mode TEXT, salary_budget TEXT,
  notice_max_days INTEGER, immediate_joiner_pref TEXT, open_to_work_pref TEXT,
  domain TEXT, education TEXT, profiles_required INTEGER,
  target_companies TEXT DEFAULT '[]', excluded_companies TEXT DEFAULT '[]',
  mandatory_skills TEXT DEFAULT '[]', preferred_skills TEXT DEFAULT '[]',
  transferable_skills TEXT DEFAULT '[]', critical_skills TEXT DEFAULT '[]',
  weights TEXT, intake TEXT DEFAULT '{}', status TEXT DEFAULT 'intake',
  created_at TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY, full_name TEXT, current_company TEXT, current_designation TEXT,
  total_exp_years REAL, location TEXT, notice_period_days INTEGER,
  notice_status TEXT DEFAULT 'unknown', availability_verified INTEGER DEFAULT 0,
  availability_evidence TEXT, open_to_work TEXT DEFAULT 'unknown', open_to_work_evidence TEXT,
  linkedin_url TEXT, linkedin_norm TEXT, github_url TEXT, github_norm TEXT,
  email TEXT, email_norm TEXT, resume_link TEXT, resume_text TEXT,
  source_channel TEXT, source_url TEXT, sourced_by TEXT DEFAULT 'MARK',
  duplicate_of TEXT, created_at TEXT, updated_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cand_linkedin ON candidates(linkedin_norm) WHERE linkedin_norm IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cand_github ON candidates(github_norm) WHERE github_norm IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cand_email ON candidates(email_norm) WHERE email_norm IS NOT NULL;

CREATE TABLE IF NOT EXISTS candidate_skills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, skill TEXT, level TEXT,
  levels TEXT, evidence TEXT, confidence TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS candidate_projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, title TEXT, company TEXT,
  start TEXT, end TEXT, months INTEGER, technologies TEXT, description TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS pipeline (
  requirement_id TEXT, candidate_id TEXT, status TEXT DEFAULT 'identified',
  source_channel TEXT, match_score REAL, classification TEXT, joe_assessment TEXT,
  recruiter_remarks TEXT, recruiter_approved_submit INTEGER DEFAULT 0,
  created_at TEXT, updated_at TEXT, PRIMARY KEY (requirement_id, candidate_id));

CREATE TABLE IF NOT EXISTS sourcing_channels (
  id TEXT PRIMARY KEY, name TEXT UNIQUE, category TEXT, connected INTEGER DEFAULT 0,
  connection_evidence TEXT, connection_verified_at TEXT, access_permission TEXT DEFAULT 'not confirmed',
  methodology TEXT, filters TEXT, manual_only INTEGER DEFAULT 1, active INTEGER DEFAULT 1,
  approved INTEGER DEFAULT 0, recruiter_feedback TEXT, date_added TEXT, date_last_used TEXT,
  url TEXT, string_type TEXT DEFAULT 'boolean');

CREATE TABLE IF NOT EXISTS channel_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, requirement_id TEXT, job_family TEXT,
  search_methodology TEXT, boolean_strings TEXT, filters TEXT, target_designations TEXT,
  skill_combinations TEXT, approved_by TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS search_strategies (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, version INTEGER,
  payload TEXT, status TEXT DEFAULT 'proposed', notes TEXT, created_at TEXT, decided_at TEXT);

CREATE TABLE IF NOT EXISTS search_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, channel_id TEXT, query TEXT,
  executed_by TEXT, results_count INTEGER, evidence TEXT, at TEXT);

CREATE TABLE IF NOT EXISTS target_companies (
  id TEXT PRIMARY KEY, name TEXT, name_norm TEXT UNIQUE, category TEXT, industry TEXT,
  business_model TEXT, tech_ecosystem TEXT, source TEXT, verified INTEGER DEFAULT 0,
  research_date TEXT, created_at TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS company_talent_maps (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, company_id TEXT,
  relevance REAL, priority TEXT, relevant_titles TEXT, matched_skills TEXT,
  talent_pool_note TEXT, source TEXT, research_date TEXT,
  UNIQUE (requirement_id, company_id));

CREATE TABLE IF NOT EXISTS resume_evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, candidate_id TEXT,
  total REAL, classification TEXT, recommendation TEXT, breakdown TEXT, skill_evidence TEXT,
  missing_skills TEXT, critical_gaps TEXT, flags TEXT, screening_questions TEXT,
  relevant_exp_years REAL, total_exp_years REAL, challenges TEXT, weights TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS candidate_status_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, candidate_id TEXT,
  from_status TEXT, to_status TEXT, changed_by TEXT, note TEXT, at TEXT);

CREATE TABLE IF NOT EXISTS recruiter_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, candidate_id TEXT,
  channel_id TEXT, rating INTEGER, feedback TEXT, at TEXT);

CREATE TABLE IF NOT EXISTS agent_activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, requirement_id TEXT, action TEXT,
  detail TEXT, at TEXT);

CREATE TABLE IF NOT EXISTS connector_registry (
  id TEXT PRIMARY KEY, name TEXT UNIQUE, category TEXT, status TEXT DEFAULT 'not_connected',
  supported_actions TEXT DEFAULT '[]', bulk_sourcing INTEGER DEFAULT 0, permissions TEXT,
  evidence TEXT, verified_at TEXT, verified_by TEXT, notes TEXT);

CREATE TABLE IF NOT EXISTS recruitment_analytics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, requirement_id TEXT, snapshot TEXT, at TEXT);

CREATE TABLE IF NOT EXISTS skill_library (
  name TEXT PRIMARY KEY, payload TEXT, source TEXT, updated_at TEXT);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT, entity_id TEXT, action TEXT,
  before TEXT, after TEXT, actor TEXT, at TEXT);
"""

JSON_FIELDS = {
    "target_companies", "excluded_companies", "mandatory_skills", "preferred_skills",
    "transferable_skills", "critical_skills", "weights", "intake", "filters", "boolean_strings",
    "target_designations", "skill_combinations", "payload", "tech_ecosystem", "relevant_titles",
    "matched_skills", "breakdown", "skill_evidence", "missing_skills", "critical_gaps", "flags",
    "screening_questions", "challenges", "detail", "supported_actions", "snapshot", "technologies",
    "levels", "joe_assessment", "evidence",
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix):
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def norm_url(url):
    """Normalise a profile URL for duplicate checks (scheme, www/country subdomain, query, slash, case)."""
    if not url:
        return None
    u = url.strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^(www\.|[a-z]{2}\.|m\.)", "", u)
    u = u.split("?")[0].split("#")[0].rstrip("/")
    return u or None


def norm_email(email):
    if not email:
        return None
    e = email.strip().lower()
    return e if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e) else None


def norm_name(name):
    return re.sub(r"[^a-z ]", "", (name or "").lower()).strip()


class DB:
    def __init__(self, path=None):
        self.path = path or DEFAULT_DB
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """Add columns introduced after a database was created. Never drops anything."""
        added = {"sourcing_channels": [("url", "TEXT"), ("string_type", "TEXT DEFAULT 'boolean'")]}
        for table, cols in added.items():
            have = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            for name, typ in cols:
                if name not in have:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")

    # ---------- helpers ----------
    @staticmethod
    def _enc(k, v):
        if k in JSON_FIELDS and v is not None and not isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool):
            return int(v)
        return v

    @staticmethod
    def decode(row):
        if row is None:
            return None
        d = dict(row)
        for k, v in d.items():
            if k in JSON_FIELDS and isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except ValueError:
                    pass
        return d

    def q(self, sql, params=()):
        return [self.decode(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        return self.decode(self.conn.execute(sql, params).fetchone())

    def insert(self, table, rec, actor="system", audit=True):
        rec = {k: self._enc(k, v) for k, v in rec.items()}
        cols = ",".join(rec)
        cur = self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(rec))})", list(rec.values()))
        key = rec.get("id") or cur.lastrowid
        if audit:
            self.conn.execute("INSERT INTO audit_log (entity, entity_id, action, before, after, actor, at) VALUES (?,?,?,?,?,?,?)",
                              (table, str(key), "create", None, json.dumps(rec, ensure_ascii=False, default=str)[:20000], actor, now()))
        self.conn.commit()
        return key

    def update_record(self, table, where, changes, actor="recruiter"):
        """Update one row and write the audit trail. `where` is a dict of key columns."""
        wsql = " AND ".join(f"{k}=?" for k in where)
        before = self.one(f"SELECT * FROM {table} WHERE {wsql}", tuple(where.values()))
        if before is None:
            raise KeyError(f"{table} {where} not found")
        enc = {k: self._enc(k, v) for k, v in changes.items()}
        if "updated_at" in before:
            enc["updated_at"] = now()
        sets = ",".join(f"{k}=?" for k in enc)
        self.conn.execute(f"UPDATE {table} SET {sets} WHERE {wsql}", list(enc.values()) + list(where.values()))
        diff_before = {k: before.get(k) for k in changes}
        self.conn.execute("INSERT INTO audit_log (entity, entity_id, action, before, after, actor, at) VALUES (?,?,?,?,?,?,?)",
                          (table, json.dumps(where), "update", json.dumps(diff_before, default=str, ensure_ascii=False),
                           json.dumps(changes, default=str, ensure_ascii=False), actor, now()))
        self.conn.commit()
        return self.one(f"SELECT * FROM {table} WHERE {wsql}", tuple(where.values()))

    def log(self, agent, action, detail=None, requirement_id=None):
        self.conn.execute("INSERT INTO agent_activity (agent, requirement_id, action, detail, at) VALUES (?,?,?,?,?)",
                          (agent, requirement_id, action, json.dumps(detail or {}, ensure_ascii=False, default=str), now()))
        self.conn.commit()

    # ---------- seeding ----------
    def seed(self):
        """Load catalogues the first time. Never overwrites or removes existing rows."""
        ch = json.load(open(os.path.join(DATA_DIR, "channels.json")))
        for c in ch["channels"]:
            row = self.one("SELECT id, url, string_type FROM sourcing_channels WHERE name=?", (c["name"],))
            if not row:
                self.insert("sourcing_channels", {
                    "id": new_id("CH"), "name": c["name"], "category": c["category"], "connected": 0,
                    "access_permission": "not confirmed", "methodology": c["methodology"],
                    "filters": c["filters"], "manual_only": int(c.get("manual_only", True)),
                    "active": 1, "approved": int(bool(c.get("approved"))), "date_added": now(),
                    "url": c.get("url"), "string_type": c.get("string_type", "boolean")}, actor="system:seed")
            elif row["url"] is None and c.get("url"):  # back-fill only empty fields; recruiter edits are kept
                self.conn.execute("UPDATE sourcing_channels SET url=? WHERE id=?", (c["url"], row["id"]))
            if row and c.get("string_type") and (row["string_type"] in (None, "boolean")) and c["string_type"] != "boolean":
                self.conn.execute("UPDATE sourcing_channels SET string_type=? WHERE id=?", (c["string_type"], row["id"]))
        co = json.load(open(os.path.join(DATA_DIR, "companies.json")))
        for c in co["companies"]:
            n = norm_name(c["name"])
            if not self.one("SELECT id FROM target_companies WHERE name_norm=?", (n,)):
                self.insert("target_companies", {
                    "id": new_id("CO"), "name": c["name"], "name_norm": n, "category": c["category"],
                    "industry": c["industry"], "business_model": c["business_model"], "tech_ecosystem": c["tech"],
                    "source": "seed: general knowledge, verify", "verified": 0, "research_date": "2026-11-04",
                    "created_at": now(), "updated_at": now()}, actor="system:seed", audit=False)
        for name, cat, actions, bulk, note in CONNECTOR_CATALOG:
            if not self.one("SELECT id FROM connector_registry WHERE name=?", (name,)):
                self.insert("connector_registry", {
                    "id": new_id("CN"), "name": name, "category": cat,
                    "status": "built_in" if name in ("Excel", "Database / BI") else "not_connected",
                    "supported_actions": actions, "bulk_sourcing": bulk, "permissions": "not confirmed",
                    "notes": note}, actor="system:seed", audit=False)


# name, category, actions the integration is generally designed for, bulk candidate sourcing?, note
CONNECTOR_CATALOG = [
    ("LinkedIn", "Candidate sourcing", ["manual search", "job posting (where a hiring connector exists)"], 0,
     "No public API for bulk people search. Treat as manual unless a connector proves otherwise."),
    ("Common Room", "Candidate sourcing", ["community signals"], 0, "Depends on workspace data; verify."),
    ("Clay", "Candidate sourcing", ["enrichment", "list building"], 0, "Enrichment of existing records; verify plan and terms."),
    ("Public web search", "Candidate sourcing", ["web search", "X-Ray queries"], 0, "Returns public pages only; results must be verified."),
    ("GitHub", "Candidate sourcing", ["user search", "repository search"], 0, "Shows code evidence, not employment or availability."),
    ("The Org", "Candidate sourcing", ["people search by company/title", "org chart"], 0, "Max 25 results per search; uses credits."),
    ("Calendar", "Communication", ["create events"], 0, "Only with recruiter approval for each invite."),
    ("Gmail", "Communication", ["draft email"], 0, "Drafts only; never sends to candidates without approval."),
    ("Excel", "Analytics", ["export .xlsx"], 0, "Built-in export works without a connector."),
    ("Google Sheets", "Analytics", ["read/write sheets"], 0, "Verify the connector before syncing."),
    ("Database / BI", "Analytics", ["SQLite store", "query"], 0, "SQLite store is built in; external BI tools need their own connector."),
]
