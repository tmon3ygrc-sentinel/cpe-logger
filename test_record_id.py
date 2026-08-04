# test_record_id.py — throwaway verification, delete after
# Confirms deterministic record_id construction (source+date+ep+seq), the
# Notion-seeded sequential index (prevents same-day two-run collisions — the
# exact shape of the 2026-07-16 ep0001/ep0716 incident), and record_exists()'s
# retry -> fail-closed -> failed_records.txt routing.
# See boards/sentinel_record_id_dedup_design.md for the design this verifies.
#
# No live Notion traffic: every notion.databases.query call is monkeypatched
# to a fake for the duration of each test block, restored immediately after.

import tempfile
import notion_logger_v7 as nl

failures = 0


def check(label, got, expected):
    global failures
    ok = got == expected
    status = "PASS" if ok else "FAIL"
    if not ok:
        failures += 1
    print(f"{status} {label}: {got!r}  (expect {expected!r})")


class FakeQueryCounter:
    """Every call succeeds, always returning `count` fake results —
    stands in for a prefix-count query with a known live-record count."""
    def __init__(self, count):
        self.count = count
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        return {"results": [{"id": f"fake-{i}"} for i in range(self.count)], "has_more": False}


class FakeQueryAlwaysFails:
    """Every call raises — simulates a persistent Notion outage."""
    def __init__(self):
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        raise RuntimeError("simulated Notion API outage")


class FakeQueryCountOnceThenFail:
    """First call (the prefix-count) succeeds; every call after (the
    exists-check and its retries) fails — isolates the record_exists()
    failure path specifically, separate from the prefix-count failure path."""
    def __init__(self, count):
        self.count = count
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {"results": [{"id": f"fake-{i}"} for i in range(self.count)], "has_more": False}
        raise RuntimeError("simulated Notion API outage on exists-check")


_orig_query = nl.notion.databases.query
_orig_sleep = nl.time.sleep
nl.time.sleep = lambda *a, **kw: None  # skip real retry backoff for every test below

# ===================================================================
# 1. Real episode-number extraction (RSS title regex)
# ===================================================================
check("ep number, standard form",
      nl._extract_episode_number("Top Cyber News NOW – Ep 1172 – Foo"), 1172)
check("ep number, 'Ep.' form",
      nl._extract_episode_number("Top Cyber News NOW – Ep. 1172 – Foo"), 1172)
check("ep number, no match",
      nl._extract_episode_number("Some Random Episode Title"), None)

# ===================================================================
# 1b. _resolve_episode_number() — prefers <itunes:episode> over title
#     text, per the 2026-08-04 incident (title lagged the real number
#     two days running while itunes:episode was already correct).
# ===================================================================
check("tag present, agrees with title -> tag wins (trivially correct)",
      nl._resolve_episode_number({"itunes_episode": "1186"},
                                  "Jul 31's Top Cyber News NOW! - Ep 1186"),
      1186)
check("tag present, DISAGREES with title -> tag wins, not title "
      "(the actual 08-03/08-04 shape)",
      nl._resolve_episode_number({"itunes_episode": "1187"},
                                  "Aug 3's Top Cyber News NOW! - Ep 1186"),
      1187)
check("tag absent -> falls back to title regex, old behavior unchanged",
      nl._resolve_episode_number({},
                                  "Top Cyber News NOW – Ep 1172 – Foo"),
      1172)
check("tag present but non-numeric garbage -> falls back to title regex",
      nl._resolve_episode_number({"itunes_episode": "N/A"},
                                  "Top Cyber News NOW – Ep 1172 – Foo"),
      1172)
check("tag absent AND no title match -> None, same as bare title regex",
      nl._resolve_episode_number({}, "Some Random Episode Title"),
      None)

# ===================================================================
# 2. Deterministic construction — the three format cases
# ===================================================================
nl.notion.databases.query = FakeQueryCounter(0)
rid = nl._construct_record_id("Simply Cyber Daily Threat Brief", "2026-07-13", 1172, {})
check("real ep number + real date", rid, "simplycyber-ep1172-2026-07-13-01")

nl.notion.databases.query = FakeQueryCounter(0)
rid = nl._construct_record_id("Simply Cyber Daily Threat Brief", "2026-07-15", None, {})
check("real date, no ep number", rid, "simplycyber-2026-07-15-01")

nl.notion.databases.query = FakeQueryCounter(0)
rid = nl._construct_record_id("Barricade Cyber", None, None, {})
today = nl.date.today().isoformat()
check("no reliable date -> manual bucket", rid, f"barricadecyber-manual-{today}-01")

# ===================================================================
# 3. Sequential-index seeding — reproduces the exact 2026-07-16 incident
#    shape: two SEPARATE runs (fresh seq_cache each, as two separate process
#    invocations would have) against the SAME calendar date must not collide.
# ===================================================================
nl.notion.databases.query = FakeQueryCounter(0)  # run 1: nothing live yet
seq_cache_run1 = {}
run1_ids = [
    nl._construct_record_id("Simply Cyber Daily Threat Brief", "2026-07-15", None, seq_cache_run1)
    for _ in range(7)
]
check("run 1 (7 records) numbered -01..-07",
      run1_ids,
      [f"simplycyber-2026-07-15-{i:02d}" for i in range(1, 8)])

nl.notion.databases.query = FakeQueryCounter(7)  # run 2: run 1's 7 records are now live
seq_cache_run2 = {}  # fresh cache — a real second invocation would start empty
run2_ids = [
    nl._construct_record_id("Simply Cyber Daily Threat Brief", "2026-07-15", None, seq_cache_run2)
    for _ in range(8)
]
check("run 2 (8 more, same date) continues at -08, no collision with run 1",
      run2_ids,
      [f"simplycyber-2026-07-15-{i:02d}" for i in range(8, 16)])
check("zero ids shared between run 1 and run 2", sorted(set(run1_ids) & set(run2_ids)), [])

# ===================================================================
# 4. record_exists() — retries transient failures, then fails CLOSED
#    (raises, never silently returns False on a real query failure)
# ===================================================================
fake_fail = FakeQueryAlwaysFails()
nl.notion.databases.query = fake_fail
raised = False
try:
    nl.record_exists("simplycyber-2026-07-15-01")
except nl.DedupCheckError:
    raised = True
check("record_exists raises DedupCheckError after exhausting retries", raised, True)
check("record_exists actually retried 3x (not a give-up-on-attempt-1)", fake_fail.calls, 3)

# ===================================================================
# 5. push_record() routes dedup-check failures distinctly from real push
#    failures — both failure points covered (prefix-count query, and
#    record_exists() query after a successful construction).
# ===================================================================
nl.notion.databases.query = FakeQueryAlwaysFails()
success, reason = nl.push_record(
    {"record_id": "whatever-the-model-said", "title": "test"},
    "Simply Cyber Daily Threat Brief", "https://example.com/test",
    {}, "2026-07-15", None,
)
check("push_record fails closed when prefix-count query fails",
      (success, reason), (False, "dedup-check-failed"))

nl.notion.databases.query = FakeQueryCountOnceThenFail(0)
success, reason = nl.push_record(
    {"record_id": "whatever-the-model-said", "title": "test"},
    "Simply Cyber Daily Threat Brief", "https://example.com/test",
    {}, "2026-07-15", None,
)
check("push_record fails closed when record_exists() query fails (construction itself OK)",
      (success, reason), (False, "dedup-check-failed"))

# ===================================================================
# 6. push_all() -> failed_records.txt routing, with a distinct reason tag
#    (not conflated with an ordinary push-failed). Redirects SCRIPT_DIR to
#    a tempdir so the real project's failed_records.txt is never touched.
# ===================================================================
_orig_script_dir = nl.SCRIPT_DIR
with tempfile.TemporaryDirectory() as tmpdir:
    nl.SCRIPT_DIR = nl.Path(tmpdir)
    nl.notion.databases.query = FakeQueryAlwaysFails()
    dedup_failures = nl.push_all(
        [{"record_id": "x", "title": "test record"}],
        "Simply Cyber Daily Threat Brief", "https://example.com/test",
    )
    check("push_all() reports 1 dedup-check-failed record", dedup_failures, 1)
    fail_file = nl.Path(tmpdir) / "failed_records.txt"
    fail_text = fail_file.read_text(encoding="utf-8") if fail_file.exists() else ""
    check("failed_records.txt was written", fail_file.exists(), True)
    check("failed_records.txt tags the reason distinctly",
          "_fail_reason:: dedup-check-failed" in fail_text, True)
nl.SCRIPT_DIR = _orig_script_dir

# ===================================================================
# cleanup — restore real Notion query + real time.sleep
# ===================================================================
nl.notion.databases.query = _orig_query
nl.time.sleep = _orig_sleep

print()
if failures:
    print(f"❌ {failures} test(s) FAILED")
else:
    print("✅ all record_id / dedup tests passed")
