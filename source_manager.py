from datetime import datetime, timezone

from database import upsert_university

from tuition_estimator import (
    estimate_tuition,
    estimate_major_tuition,
)


def clean_text(value):
    """
    Convert empty strings to None.
    """
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def normalize_openalex(item):
    """
    Convert an OpenAlex institution into the UniScout
    database format.

    Tuition is estimated automatically when OpenAlex
    does not provide it.
    """

    geo = item.get("geo") or {}

    country = clean_text(
        geo.get("country")
    )

    country_code = clean_text(
        geo.get("country_code")
    )

    city = clean_text(
        geo.get("city")
    )

    website = clean_text(
        item.get("homepage_url")
        or item.get("website_url")
    )

    ids = item.get("ids") or {}

    source_id = str(
        item.get("id")
        or ids.get("openalex")
        or ""
    )

    name = (
        clean_text(
            item.get("display_name")
            or item.get("name")
        )
        or "Unnamed institution"
    )

    university_type = (
        clean_text(
            item.get("type")
        )
        or "University"
    )

    # ========================================================
    # ESTIMATE TUITION
    # ========================================================

    tuition = estimate_tuition(
        country_code=country_code,
        university_name=name,
        university_type=university_type,
    )

    return {

        "name": name,

        "country": country,

        "country_code": country_code,

        "city": city,

        "website": website,

        "logo_url": clean_text(
            item.get("image_url")
        ),

        "description": None,

        "ranking": None,

        # ----------------------------------------------------
        # ESTIMATED TUITION
        # ----------------------------------------------------

        "tuition_min": tuition["min"],

        "tuition_max": tuition["max"],

        "tuition_currency": tuition["currency"],

        "tuition_period": tuition["period"],

        "university_type": university_type,

        "student_count": None,

        "international_student_count": None,

        # OpenAlex doesn't reliably give us a list of
        # majors for every institution.
        "majors": None,

        "degree_levels": None,

        "admission_requirements": None,

        "application_deadline": None,

        # ----------------------------------------------------
        # Mark this clearly as estimated data.
        # ----------------------------------------------------

        "source": "OpenAlex + UniScout Tuition Estimate",

        "source_id": source_id,

        "last_updated": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }


def import_records(records):
    """
    Import normalized university records.
    """

    stats = {
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    for record in records:

        try:

            status, _ = (
                upsert_university(
                    record
                )
            )

            stats[status] += 1

        except Exception as exc:

            stats["errors"] += 1

            print(
                "Import error:",
                exc,
            )

    return stats
