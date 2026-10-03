from datetime import datetime, timezone
import hashlib

from database import upsert_university, get_db

# Demo-only values so every university profile has something to display.
# These are not official university facts.
DEFAULT_MAJORS = (
    "Computer Science|Engineering|Business|Economics|Psychology|"
    "Information Technology|Biology|Arts"
)
DEFAULT_DEGREES = "Bachelor|Master|Doctorate"
DEFAULT_ADMISSION = (
    "Academic transcripts; proof of English/language proficiency; "
    "program-specific documents; valid identification."
)
DEFAULT_DEADLINE = "Varies by program and intake"

KNOWN_TUITION = {
    "national university of singapore": (18000, 30000),
    "nanyang technological university": (17000, 29000),
    "university of toronto": (42000, 70000),
    "university of melbourne": (30000, 55000),
    "university of tokyo": (4500, 10000),
    "university of british columbia": (30000, 55000),
    "massachusetts institute of technology": (65000, 70000),
    "mit": (65000, 70000),
    "harvard university": (55000, 65000),
    "stanford university": (60000, 70000),
    "university of oxford": (30000, 60000),
    "university of cambridge": (30000, 60000),
    "imperial college london": (40000, 65000),
    "ucl": (30000, 55000),
    "eth zurich": (1500, 10000),
    "tsinghua university": (3500, 9000),
    "peking university": (3500, 9000),
    "seoul national university": (3000, 9000),
    "the university of hong kong": (18000, 30000),
    "university of sydney": (30000, 55000),
    "unsw sydney": (28000, 50000),
}

COUNTRY_TUITION = {
    "US": (35000, 65000), "CA": (25000, 55000), "GB": (22000, 50000),
    "AU": (25000, 52000), "SG": (16000, 30000), "JP": (4000, 10000),
    "DE": (1500, 18000), "FR": (2500, 18000), "NL": (10000, 25000),
    "CH": (1500, 20000), "CN": (3000, 12000), "KR": (3000, 10000),
    "HK": (12000, 30000), "TW": (3000, 12000), "IN": (1000, 10000),
    "ID": (1000, 8000), "MY": (3000, 12000), "TH": (2500, 12000),
    "NZ": (18000, 35000), "IE": (10000, 30000), "SE": (8000, 25000),
    "NO": (1000, 25000), "DK": (5000, 25000), "FI": (5000, 20000),
    "IT": (2000, 18000), "ES": (2000, 18000), "BR": (1000, 10000),
    "MX": (2000, 12000), "ZA": (2000, 12000), "AE": (12000, 30000),
}

COUNTRY_STUDENTS = {
    "US": (15000, 60000), "CA": (15000, 50000), "GB": (12000, 45000),
    "AU": (10000, 50000), "SG": (10000, 45000), "JP": (10000, 30000),
    "CN": (15000, 50000), "IN": (10000, 50000), "DE": (10000, 40000),
    "FR": (10000, 45000), "KR": (10000, 35000), "ID": (5000, 30000),
}

COUNTRY_INTL_PCT = {
    "US": 0.18, "CA": 0.28, "GB": 0.25, "AU": 0.30, "SG": 0.25,
    "JP": 0.12, "CN": 0.10, "IN": 0.08, "DE": 0.20, "FR": 0.18,
    "KR": 0.12, "ID": 0.08,
}


def clean_text(value):
    return (value or "").strip() or None


def _stable_int(name, low, high):
    digest = hashlib.sha256(name.lower().encode("utf-8")).hexdigest()
    n = int(digest[:12], 16)
    return low + (n % (high - low + 1))


def demo_tuition(name, country_code):
    key = (name or "").strip().lower()
    if key in KNOWN_TUITION:
        return KNOWN_TUITION[key]
    return COUNTRY_TUITION.get(country_code, (3000, 25000))


def demo_ranking(name):
    # A stable demo position, not a real ranking.
    return _stable_int(name or "university", 80, 900)


def demo_students(name, country_code):
    low, high = COUNTRY_STUDENTS.get(country_code, (5000, 30000))
    return _stable_int(name or "university", low, high)


def demo_international_students(name, country_code, total):
    pct = COUNTRY_INTL_PCT.get(country_code, 0.12)
    base = int(total * pct)
    # Keep it positive for small demo institutions.
    return max(100, min(base, max(100, total - 100)))


def demo_type(name):
    key = (name or "").lower()
    private_markers = ("private", "inc.", "institute of technology")
    if any(marker in key for marker in private_markers):
        return "Private"
    return "University"


def normalize_openalex(item):
    geo = item.get("geo") or {}
    country = geo.get("country") or ""
    cc = geo.get("country_code") or ""
    city = geo.get("city") or ""
    name = clean_text(item.get("display_name") or item.get("name")) or "Unnamed institution"
    website = item.get("homepage_url") or item.get("website_url") or ""
    ids = item.get("ids") or {}
    source_id = str(item.get("id") or ids.get("openalex") or "")

    tuition_min, tuition_max = demo_tuition(name, cc)
    students = demo_students(name, cc)
    intl_students = demo_international_students(name, cc, students)

    return {
        "name": name,
        "country": clean_text(country),
        "country_code": clean_text(cc),
        "city": clean_text(city),
        "website": clean_text(website),
        "logo_url": clean_text(item.get("image_url")),
        "description": f"{name} is a higher-education institution in {city or country or 'its region'}, included in UniScout for university discovery.",
        "ranking": demo_ranking(name),
        "tuition_min": tuition_min,
        "tuition_max": tuition_max,
        "tuition_currency": "USD",
        "tuition_period": "year",
        "university_type": demo_type(name),
        "student_count": students,
        "international_student_count": intl_students,
        "majors": DEFAULT_MAJORS,
        "degree_levels": DEFAULT_DEGREES,
        "admission_requirements": DEFAULT_ADMISSION,
        "application_deadline": DEFAULT_DEADLINE,
        "source": "OpenAlex + demo enrichment",
        "source_id": source_id,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def enrich_existing_records():
    """Fill blank profile fields for every existing university in-place."""
    fields = {
        "description", "ranking", "tuition_min", "tuition_max",
        "tuition_currency", "tuition_period", "university_type",
        "student_count", "international_student_count", "majors",
        "degree_levels", "admission_requirements", "application_deadline",
    }
    updated = 0

    with get_db() as db:
        rows = db.execute("SELECT * FROM universities").fetchall()
        columns = {row["name"] if hasattr(row, "keys") else None for row in []}
        for row in rows:
            name = row["name"] or "Unnamed institution"
            country = row["country"] or ""
            cc = row["country_code"] or ""
            city = row["city"] or ""
            tuition_min, tuition_max = demo_tuition(name, cc)
            students = demo_students(name, cc)
            intl_students = demo_international_students(name, cc, students)

            values = {
                "description": f"{name} is a higher-education institution in {city or country or 'its region'}, included in UniScout for university discovery.",
                "ranking": demo_ranking(name),
                "tuition_min": tuition_min,
                "tuition_max": tuition_max,
                "tuition_currency": "USD",
                "tuition_period": "year",
                "university_type": row["university_type"] or demo_type(name),
                "student_count": students,
                "international_student_count": intl_students,
                "majors": DEFAULT_MAJORS,
                "degree_levels": DEFAULT_DEGREES,
                "admission_requirements": DEFAULT_ADMISSION,
                "application_deadline": DEFAULT_DEADLINE,
            }

            set_parts = []
            params = []
            for field, value in values.items():
                current = row[field]
                if current is None or str(current).strip() == "":
                    set_parts.append(f"{field} = ?")
                    params.append(value)

            if set_parts:
                params.append(row["id"])
                db.execute(
                    f"UPDATE universities SET {', '.join(set_parts)} WHERE id = ?",
                    params,
                )
                updated += 1

        db.commit()

    print(f"Demo profile enrichment: updated {updated:,} universities.")
    return updated


def import_records(records):
    stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}
    for record in records:
        try:
            status, _ = upsert_university(record)
            stats[status] += 1
        except Exception as exc:
            stats["errors"] += 1
            print("Import error:", exc)
    return stats
