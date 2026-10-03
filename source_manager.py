from datetime import datetime, timezone
from database import upsert_university


# ============================================================
# DEMO TUITION DATA
# ============================================================
# OpenAlex does not provide complete tuition data for institutions.
# For the demo, known universities get specific approximate annual
# international-student tuition ranges. Other universities use a
# country-based estimate so the UI does not show "Tuition unavailable".
#
# Values are USD per academic year and are DEMO estimates, not official
# quotes. Real tuition varies by programme, residency, degree and year.

KNOWN_TUITION = {
    "National University of Singapore": (18000, 30000),
    "Nanyang Technological University": (17000, 29000),
    "University of Toronto": (42000, 70000),
    "University of Melbourne": (30000, 55000),
    "University of Tokyo": (4500, 10000),
    "University of British Columbia": (30000, 55000),
    "Massachusetts Institute of Technology": (65000, 70000),
    "Harvard University": (55000, 65000),
    "Stanford University": (60000, 70000),
    "University of Oxford": (30000, 60000),
    "University of Cambridge": (30000, 60000),
    "Imperial College London": (40000, 65000),
    "University College London": (30000, 55000),
    "ETH Zurich": (1500, 5000),
    "Tsinghua University": (3500, 9000),
    "Peking University": (3500, 9000),
    "Seoul National University": (3000, 9000),
    "The University of Hong Kong": (18000, 30000),
    "University of Sydney": (30000, 55000),
    "UNSW Sydney": (28000, 50000),
}


# Broad annual international-student estimates by country.
# Used only when a university is not in KNOWN_TUITION.
COUNTRY_TUITION = {
    "US": (35000, 65000),
    "CA": (25000, 55000),
    "GB": (22000, 50000),
    "AU": (25000, 52000),
    "SG": (16000, 30000),
    "JP": (4000, 10000),
    "DE": (1000, 5000),
    "FR": (1000, 8000),
    "NL": (8000, 22000),
    "CH": (1500, 10000),
    "SE": (8000, 22000),
    "NO": (3000, 15000),
    "DK": (6000, 18000),
    "FI": (6000, 18000),
    "IE": (12000, 30000),
    "ES": (1500, 10000),
    "IT": (1000, 8000),
    "PT": (1500, 8000),
    "CN": (3000, 10000),
    "HK": (18000, 30000),
    "KR": (3000, 10000),
    "TW": (3000, 9000),
    "IN": (1000, 8000),
    "ID": (1000, 7000),
    "MY": (3000, 12000),
    "TH": (2500, 10000),
    "PH": (2000, 9000),
    "NZ": (18000, 35000),
    "BR": (1500, 10000),
    "MX": (2000, 10000),
    "ZA": (2000, 10000),
    "AE": (12000, 30000),
    "SA": (1000, 15000),
    "TR": (1000, 8000),
    "PL": (1500, 8000),
    "CZ": (1000, 7000),
    "AT": (1000, 8000),
    "BE": (1500, 10000),
    "IL": (10000, 25000),
}


# Used for the major field so search cards are populated too.
DEFAULT_MAJORS = (
    "Computer Science|Engineering|Business|Economics|"
    "Psychology|Information Technology|Biology|Arts"
)


def clean_text(v):
    return (v or '').strip() or None


def _normalise_name(name):
    return ' '.join((name or '').lower().split())


def demo_tuition(name, country_code):
    """Return a demo annual USD tuition range for every institution."""
    normalised = _normalise_name(name)

    for known_name, range_value in KNOWN_TUITION.items():
        if _normalise_name(known_name) == normalised:
            return range_value

    # Handle names that contain a known university name plus a campus suffix.
    for known_name, range_value in KNOWN_TUITION.items():
        known = _normalise_name(known_name)
        if known in normalised or normalised in known:
            return range_value

    # Country fallback guarantees a non-empty tuition value for the demo.
    return COUNTRY_TUITION.get(
        (country_code or '').upper(),
        (3000, 25000),
    )


def normalize_openalex(item):
    geo = item.get('geo') or {}
    country = geo.get('country') or ''
    cc = geo.get('country_code') or ''
    city = geo.get('city') or ''
    website = item.get('homepage_url') or item.get('website_url') or ''
    ids = item.get('ids') or {}

    name = clean_text(
        item.get('display_name') or item.get('name')
    ) or 'Unnamed institution'

    source_id = str(
        item.get('id') or ids.get('openalex') or ''
    )

    tuition_min, tuition_max = demo_tuition(name, cc)

    return {
        'name': name,
        'country': clean_text(country),
        'country_code': clean_text(cc),
        'city': clean_text(city),
        'website': clean_text(website),
        'logo_url': clean_text(item.get('image_url')),
        'description': None,

        # DEMO: OpenAlex does not supply complete tuition/ranking data.
        'ranking': None,
        'tuition_min': tuition_min,
        'tuition_max': tuition_max,
        'tuition_currency': 'USD',
        'tuition_period': 'year',

        'university_type': 'University',
        'student_count': None,
        'international_student_count': None,

        # DEMO fallback so majors are also searchable/displayable.
        'majors': DEFAULT_MAJORS,
        'degree_levels': 'Bachelor|Master|Doctorate',

        'admission_requirements': None,
        'application_deadline': None,

        'source': 'OpenAlex',
        'source_id': source_id,
        'last_updated': datetime.now(timezone.utc).isoformat()
    }


def import_records(records):
    stats = {
        'new': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    for record in records:
        try:
            status, _ = upsert_university(record)
            stats[status] += 1
        except Exception as exc:
            stats['errors'] += 1
            print('Import error:', exc)

    return stats
