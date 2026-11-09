#!/usr/bin/env python3
"""
Match join-form submissions against a list of institutions, tolerating the
different ways people write the same institution ("Uni Münster", "WWU",
"University of Muenster", "Universität Münster").

    python3 match_institutions.py --institutions partners.xlsx --submissions join.csv
    ./submissions.sh match partners.xlsx          (fetches the submissions itself)

The institution list can be .xlsx (first column, or a column whose header
contains "institution"/"name"), .csv, or .txt with one name per line.

Writes three groups: confident matches, possible matches to check by hand, and
everyone who matched nothing. The output CSV opens directly in Excel.
"""
import argparse, csv, difflib, io, re, sys, unicodedata
from pathlib import Path

STOP = {"university", "universitat", "universitaet", "universita", "universidad",
        "universidade", "universite", "uni", "of", "the", "and", "for", "de", "der",
        "des", "di", "du", "la", "le", "fur", "fuer", "in", "at", "an", "am",
        "applied", "sciences", "science", "angewandte", "wissenschaften",
        "hochschule", "fachhochschule", "fh", "hs", "school", "college", "institute",
        "institut", "technische", "technical", "technology", "technologie", "tu",
        "school", "business", "economics", "management", "-", "&"}

# Same institution, different names. Extend as you meet new ones.
ALIASES = {
    "wwu": "munster", "muenster": "munster", "ercis": "munster",
    "westfalische wilhelms": "munster",
    "tue": "eindhoven", "tu/e": "eindhoven",
    "rwth": "aachen",
    "hpi": "hasso plattner",
    "lmu": "ludwig maximilians munchen",
    "kit": "karlsruhe",
    "dtu": "denmark",
    "ost": "ostschweizer",
    "fau": "erlangen nurnberg",
    "wu": "wirtschaftsuniversitat wien",
    "corvinus": "corvinus budapest",
    "hsg": "st gallen",
    "tum": "munchen",
}

def fold(s):
    s = s.replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return s

def tokens(s):
    s = fold(s)
    s = s.replace("tu/e", " tue ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " " + " ".join(s.split()) + " "
    # multi-word aliases first, replacing the phrase so its parts do not also
    # count as separate words ("westfalische wilhelms" -> "munster")
    for k, v in ALIASES.items():
        if " " in k:
            s = s.replace(" %s " % k, " %s " % v)
    out = []
    for w in s.split():
        out.extend(ALIASES.get(w, w).split())
    return {w for w in out if w not in STOP and len(w) > 1}

def score(a, b):
    """Jaccard over distinctive words, so every word has to be accounted for on
    both sides. Dividing by the smaller set instead made a shared city name a
    perfect match: "HAW Hamburg" scored 1.0 against "University of Hamburg"."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return max(jac, ratio * 0.9)


# Header words, strongest first. A contact list has a person's "Name" column as
# well as an institution column, so "name" may only win when nothing more
# specific exists, or the matcher would compare people's names to institutions.
HEADER_PREFS = [
    r"institution|einrichtung|organi[sz]ation|affiliation|zugeh",
    r"universit|hochschule|university|partner",
    r"^\s*(institution|organisation)\s*name",
    r"\bname\b",
]
PERSON_HEADER = re.compile(r"vorname|nachname|first|last|surname|e-?mail|kontakt|ansprech|person", re.I)

def pick_column(headers):
    hs = [str(h or "").strip() for h in headers]
    for pat in HEADER_PREFS:
        for i, h in enumerate(hs):
            if h and re.search(pat, h, re.I) and not (pat == r"\bname\b" and PERSON_HEADER.search(h)):
                return i, h
    return 0, (hs[0] if hs else "")

def read_institutions(path):
    """Returns (names, report). report says which column was used per sheet, so a
    wrong guess is visible in the output rather than silently wrong."""
    p = Path(path)
    names, report = [], []
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading .xlsx needs openpyxl. On Debian/Ubuntu: apt install -y python3-openpyxl")
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [r for r in ws.iter_rows(values_only=True) if r and any(c is not None and str(c).strip() for c in r)]
            if not rows:
                continue
            col, head = pick_column(rows[0])
            vals = [str(r[col]).strip() for r in rows[1:] if col < len(r) and r[col] is not None and str(r[col]).strip()]
            names += vals
            report.append((ws.title, head, len(vals), sorted(set(vals))[:3]))
        return names, report
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".csv":
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t") if text.strip() else csv.excel
        rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
        if not rows:
            return [], []
        col, head = pick_column(rows[0])
        vals = [r[col].strip() for r in rows[1:] if len(r) > col and r[col].strip()]
        return vals, [("csv", head, len(vals), sorted(set(vals))[:3])]
    vals = [l.strip() for l in text.splitlines() if l.strip()]
    return vals, [("txt", "(one per line)", len(vals), vals[:3])]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--institutions", required=True)
    ap.add_argument("--submissions", default="-", help="CSV export, or - for stdin")
    ap.add_argument("--out", default="cluster-contacts.csv")
    ap.add_argument("--sure", type=float, default=0.85)
    ap.add_argument("--maybe", type=float, default=0.6)
    a = ap.parse_args()

    raw, report = read_institutions(a.institutions)
    insts = sorted(set(raw))
    print("Read from %s:" % a.institutions)
    for sheet, head, n, sample in report:
        print("  sheet %-22r column %-28r %4d rows   e.g. %s" % (sheet, head, n, "; ".join(sample)))
    print("  -> %d distinct institutions. If the column or the examples look wrong, stop here.\n" % len(insts))
    src = sys.stdin if a.submissions == "-" else open(a.submissions, encoding="utf-8-sig")
    subs = list(csv.DictReader(src))

    # one row per person: keep their latest submission
    latest = {}
    for r in subs:
        latest[r["email"].strip().lower()] = r
    people = list(latest.values())

    sure, maybe, none = [], [], []
    for r in people:
        best = max(((score(r["organisation"], i), i) for i in insts), default=(0, ""))
        (sure if best[0] >= a.sure else maybe if best[0] >= a.maybe else none).append((r, best))

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:   # BOM: Excel reads umlauts
        w = csv.writer(f, delimiter=";")                              # ; : German Excel
        w.writerow(["Status", "Name", "Institution (as entered)", "Matched partner institution",
                    "E-Mail", "Role", "Interests", "Note", "Joined"])
        for label, group in (("match", sure), ("check", maybe)):
            for r, (s, inst) in sorted(group, key=lambda x: x[0]["name"]):
                w.writerow([label, r["name"], r["organisation"], inst, r["email"], r["role"],
                            r["interest"], r.get("about", ""), r["received_at"][:10]])

    print("%d institutions in the list, %d people in the database (%d submissions)\n"
          % (len(insts), len(people), len(subs)))
    for title, group in (("MATCH", sure), ("CHECK BY HAND", maybe)):
        print("%s (%d)" % (title, len(group)))
        for r, (s, inst) in sorted(group, key=lambda x: x[0]["name"]):
            print("  %-28s %-34s -> %s  (%.2f)" % (r["name"][:28], r["organisation"][:34], inst, s))
        print()
    print("NO MATCH (%d)" % len(none))
    for r, (s, inst) in sorted(none, key=lambda x: x[0]["name"]):
        print("  %-28s %s" % (r["name"][:28], r["organisation"]))
    print("\nwrote %s  (matches and to-check only; open in Excel)" % a.out)

if __name__ == "__main__":
    main()
