import os
import sqlite3

from contextlib import contextmanager

from tuition_estimator import (
    estimate_tuition,
)


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_PATH = os.path.join(
    BASE_DIR,
    "data",
    "uniscout.db",
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS universities (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    country TEXT,

    country_code TEXT,

    city TEXT,

    website TEXT,

    logo_url TEXT,

    description TEXT,

    ranking INTEGER,

    tuition_min REAL,

    tuition_max REAL,

    tuition_currency TEXT,

    tuition_period TEXT,

    university_type TEXT,

    student_count INTEGER,

    international_student_count INTEGER,

    majors TEXT,

    degree_levels TEXT,

    admission_requirements TEXT,

    application_deadline TEXT,

    source TEXT,

    source_id TEXT,

    last_updated TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(source, source_id)
);


CREATE INDEX IF NOT EXISTS
idx_universities_name
ON universities(name);


CREATE INDEX IF NOT EXISTS
idx_universities_country
ON universities(country);


CREATE INDEX IF NOT EXISTS
idx_universities_city
ON universities(city);


CREATE INDEX IF NOT EXISTS
idx_universities_ranking
ON universities(ranking);


CREATE INDEX IF NOT EXISTS
idx_universities_type
ON universities(university_type);


CREATE TABLE IF NOT EXISTS university_stats (

    university_id INTEGER PRIMARY KEY,

    popularity INTEGER DEFAULT 0,

    views INTEGER DEFAULT 0,

    FOREIGN KEY(university_id)
        REFERENCES universities(id)
        ON DELETE CASCADE
);
"""


@contextmanager
def get_db():

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True,
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys=ON"
    )

    try:

        yield conn

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


def init_db():

    with get_db() as db:

        db.executescript(
            SCHEMA
        )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # This automatically gives existing universities
    # estimated tuition if their current tuition is empty.
    # --------------------------------------------------------

    fill_missing_tuition()


def row_to_dict(row):

    return (
        dict(row)
        if row
        else None
    )


def split_list(value):

    if not value:
        return []

    return [
        x.strip()
        for x in value.split("|")
        if x.strip()
    ]


# ============================================================
# TUITION BACKFILL
# ============================================================

def fill_missing_tuition():

    """
    Fill tuition for existing universities.

    This makes the feature work even if the database was
    created before the tuition estimator was added.
    """

    with get_db() as db:

        rows = db.execute(
            """
            SELECT
                id,
                name,
                country_code,
                university_type
            FROM universities
            WHERE tuition_min IS NULL
               OR tuition_max IS NULL
               OR tuition_currency IS NULL
            """
        ).fetchall()

        if not rows:

            return

        updated = 0

        for row in rows:

            try:

                tuition = (
                    estimate_tuition(
                        country_code=row[
                            "country_code"
                        ],

                        university_name=row[
                            "name"
                        ],

                        university_type=row[
                            "university_type"
                        ],
                    )
                )

                db.execute(
                    """
                    UPDATE universities

                    SET
                        tuition_min = ?,
                        tuition_max = ?,
                        tuition_currency = ?,
                        tuition_period = ?,
                        source =
                            CASE
                                WHEN source IS NULL
                                  OR source = ''
                                  OR source = 'OpenAlex'
                                THEN
                                    'OpenAlex + UniScout Tuition Estimate'
                                ELSE
                                    source
                            END

                    WHERE id = ?
                    """,

                    (
                        tuition["min"],
                        tuition["max"],
                        tuition["currency"],
                        tuition["period"],
                        row["id"],
                    ),
                )

                updated += 1

            except Exception as exc:

                print(
                    "Tuition estimation error:",
                    row["name"],
                    exc,
                )

        print(
            f"UniScout: estimated tuition for "
            f"{updated:,} universities."
        )


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_university(row):

    if not row:
        return None

    data = dict(row)

    data["majors_list"] = split_list(
        data.get("majors")
    )

    data["degree_levels_list"] = split_list(
        data.get("degree_levels")
    )

    data["tuition_estimated"] = (
        "Estimate"
        in (
            data.get("source")
            or ""
        )
    )

    return data


# ============================================================
# FILTER OPTIONS
# ============================================================

def list_distinct(
    column,
    country=None,
):

    allowed = {
        "country",
        "city",
        "majors",
        "university_type",
    }

    if column not in allowed:

        raise ValueError(
            "Invalid column"
        )

    with get_db() as db:

        if column == "majors":

            rows = db.execute(
                """
                SELECT majors
                FROM universities
                WHERE majors IS NOT NULL
                  AND majors != ""
                """
            ).fetchall()

            values = sorted(
                {
                    major.strip()

                    for row in rows

                    for major in split_list(
                        row["majors"]
                    )
                },

                key=str.lower,
            )

        else:

            if (
                column == "city"
                and country
            ):

                rows = db.execute(
                    """
                    SELECT DISTINCT city

                    FROM universities

                    WHERE city IS NOT NULL
                      AND city != ""
                      AND country = ?

                    ORDER BY
                        city COLLATE NOCASE
                    """,

                    (
                        country,
                    ),
                ).fetchall()

            else:

                rows = db.execute(
                    f"""
                    SELECT DISTINCT
                        {column}

                    FROM universities

                    WHERE {column} IS NOT NULL
                      AND {column} != ""

                    ORDER BY
                        {column} COLLATE NOCASE
                    """
                ).fetchall()

            values = [
                row[column]
                for row in rows
            ]

    return values


# ============================================================
# SEARCH
# ============================================================

def search_universities(
    q="",
    country="",
    city="",
    major="",
    min_tuition=None,
    max_tuition=None,
    university_type="",
    min_ranking=None,
    limit=60,
    offset=0,
):

    clauses = []

    params = []

    q = (
        q or ""
    ).strip()

    if q:

        like = f"%{q}%"

        clauses.append(
            """
            (
                name LIKE ?
                OR country LIKE ?
                OR city LIKE ?
                OR description LIKE ?
                OR majors LIKE ?
                OR country_code LIKE ?
            )
            """
        )

        params += [
            like
        ] * 6

    if country:

        clauses.append(
            "country = ?"
        )

        params.append(
            country
        )

    if city:

        clauses.append(
            "city = ?"
        )

        params.append(
            city
        )

    if major:

        clauses.append(
            "majors LIKE ?"
        )

        params.append(
            f"%{major}%"
        )

    if min_tuition is not None:

        clauses.append(
            """
            (
                tuition_max IS NULL
                OR tuition_max >= ?
            )
            """
        )

        params.append(
            min_tuition
        )

    if max_tuition is not None:

        clauses.append(
            """
            (
                tuition_min IS NULL
                OR tuition_min <= ?
            )
            """
        )

        params.append(
            max_tuition
        )

    if university_type:

        clauses.append(
            "university_type = ?"
        )

        params.append(
            university_type
        )

    if min_ranking is not None:

        clauses.append(
            """
            (
                ranking IS NOT NULL
                AND ranking <= ?
            )
            """
        )

        params.append(
            min_ranking
        )

    where = (
        " WHERE "
        + " AND ".join(
            clauses
        )
        if clauses
        else ""
    )

    order = """
        ORDER BY
        CASE
            WHEN ranking IS NULL
            THEN 999999
            ELSE ranking
        END ASC,

        name COLLATE NOCASE ASC
    """

    with get_db() as db:

        total = db.execute(
            f"""
            SELECT COUNT(*)

            FROM universities

            {where}
            """,

            params,
        ).fetchone()[0]

        rows = db.execute(
            f"""
            SELECT *

            FROM universities

            {where}

            {order}

            LIMIT ?
            OFFSET ?
            """,

            params + [
                limit,
                offset,
            ],
        ).fetchall()

    return [
        normalize_university(
            row
        )

        for row in rows
    ], total


# ============================================================
# SINGLE UNIVERSITY
# ============================================================

def get_university(uid):

    with get_db() as db:

        row = db.execute(
            """
            SELECT *

            FROM universities

            WHERE id = ?
            """,

            (
                uid,
            ),
        ).fetchone()

        if row:

            db.execute(
                """
                UPDATE university_stats

                SET views =
                    views + 1

                WHERE university_id = ?
                """,

                (
                    uid,
                ),
            )

    return normalize_university(
        row
    )


# ============================================================
# SEARCH SUGGESTIONS
# ============================================================

def suggestions(
    q,
    limit=10,
):

    q = (
        q or ""
    ).strip()

    if len(q) < 2:

        return []

    like = f"%{q}%"

    output = []

    with get_db() as db:

        rows = db.execute(
            """
            SELECT
                id,
                name,
                city,
                country

            FROM universities

            WHERE name LIKE ?

            ORDER BY name

            LIMIT ?
            """,

            (
                like,
                limit,
            ),
        ).fetchall()

        output += [

            {
                "type": "university",

                "label": row[
                    "name"
                ],

                "sub":
                    f"{row['city'] or 'Unknown city'}, "
                    f"{row['country'] or 'Unknown country'}",

                "value": row[
                    "name"
                ],
            }

            for row in rows
        ]

        remaining = (
            limit
            - len(output)
        )

        if remaining > 0:

            rows = db.execute(
                """
                SELECT DISTINCT country

                FROM universities

                WHERE country LIKE ?

                ORDER BY country

                LIMIT ?
                """,

                (
                    like,
                    remaining,
                ),
            ).fetchall()

            output += [

                {
                    "type": "country",

                    "label": row[
                        "country"
                    ],

                    "sub": "Country",

                    "value": row[
                        "country"
                    ],
                }

                for row in rows
            ]

        remaining = (
            limit
            - len(output)
        )

        if remaining > 0:

            rows = db.execute(
                """
                SELECT DISTINCT
                    city,
                    country

                FROM universities

                WHERE city LIKE ?

                ORDER BY city

                LIMIT ?
                """,

                (
                    like,
                    remaining,
                ),
            ).fetchall()

            output += [

                {
                    "type": "city",

                    "label": row[
                        "city"
                    ],

                    "sub":
                        row["country"]
                        or "City",

                    "value": row[
                        "city"
                    ],
                }

                for row in rows
            ]

        remaining = (
            limit
            - len(output)
        )

        if remaining > 0:

            rows = db.execute(
                """
                SELECT majors

                FROM universities

                WHERE majors LIKE ?

                LIMIT 30
                """,

                (
                    like,
                ),
            ).fetchall()

            majors = sorted(
                {
                    major

                    for row in rows

                    for major in split_list(
                        row["majors"]
                    )

                    if q.lower()
                    in major.lower()
                },

                key=str.lower,
            )[:remaining]

            output += [

                {
                    "type": "major",

                    "label": major,

                    "sub": "Major",

                    "value": major,
                }

                for major in majors
            ]

    return output[:limit]


# ============================================================
# UPSERT
# ============================================================

def upsert_university(
    record
):

    fields = [

        "name",

        "country",

        "country_code",

        "city",

        "website",

        "logo_url",

        "description",

        "ranking",

        "tuition_min",

        "tuition_max",

        "tuition_currency",

        "tuition_period",

        "university_type",

        "student_count",

        "international_student_count",

        "majors",

        "degree_levels",

        "admission_requirements",

        "application_deadline",

        "source",

        "source_id",

        "last_updated",
    ]

    data = {
        key: record.get(key)
        for key in fields
    }

    with get_db() as db:

        existing = None

        if (
            data["source"]
            and data["source_id"]
        ):

            existing = db.execute(
                """
                SELECT id

                FROM universities

                WHERE source = ?
                  AND source_id = ?
                """,

                (
                    data["source"],
                    data["source_id"],
                ),
            ).fetchone()

        if existing:

            update_fields = [
                key

                for key in fields

                if key not in (
                    "source",
                    "source_id",
                )
            ]

            sets = ", ".join(
                f"{key} = ?"

                for key in update_fields
            )

            values = [
                data[key]

                for key in update_fields
            ]

            values.append(
                existing["id"]
            )

            db.execute(
                f"""
                UPDATE universities

                SET {sets}

                WHERE id = ?
                """,

                values,
            )

            return (
                "updated",
                existing["id"],
            )

        duplicate = db.execute(
            """
            SELECT id

            FROM universities

            WHERE lower(name)
                = lower(?)

              AND lower(
                    COALESCE(
                        country,
                        ""
                    )
                  )
                =
                  lower(
                    COALESCE(
                        ?,
                        ""
                    )
                  )
            """,

            (
                data["name"],
                data["country"],
            ),
        ).fetchone()

        if duplicate:

            return (
                "skipped",
                duplicate["id"],
            )

        columns = ",".join(
            fields
        )

        marks = ",".join(
            "?"
            for _ in fields
        )

        cursor = db.execute(
            f"""
            INSERT INTO universities
                ({columns})

            VALUES
                ({marks})
            """,

            [
                data[key]
                for key in fields
            ],
        )

        uid = cursor.lastrowid

        db.execute(
            """
            INSERT OR IGNORE
            INTO university_stats
                (university_id)

            VALUES (?)
            """,

            (
                uid,
            ),
        )

        return (
            "new",
            uid,
        )
