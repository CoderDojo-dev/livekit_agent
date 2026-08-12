"""§6: planning integrity audits - the two numbers that tell whether the weekly grid is sane.

Run against the live database; the supervisor dashboard renders these, so the SQL is kept here
where the data lives rather than buried in a view nobody can quote.
"""
from sqlalchemy import text

from persistence.engine import get_engine

WEEKLY_HOURS_PER_ADVISOR = text(
    """
    select a.full_name,
           a.language,
           sum(s.end_minute - s.start_minute) / 60.0 as weekly_hours
    from routing.advisors a
    join routing.advisor_shifts s on s.advisor_id = a.id
    where a.is_active and a.is_on_call and s.is_active
    group by a.full_name, a.language
    order by weekly_hours asc
    """
)

HOURS_PER_LANGUAGE = text(
    """
    select a.language,
           count(distinct a.id) as advisors,
           sum(s.end_minute - s.start_minute) / 60.0 as weekly_hours
    from routing.advisors a
    join routing.advisor_shifts s on s.advisor_id = a.id
    where a.is_active and a.is_on_call and s.is_active
    group by a.language
    order by weekly_hours asc
    """
)


def audit_weekly_hours():
    with get_engine().connect() as c:
        print("== weekly hours per advisor ==")
        for row in c.execute(WEEKLY_HOURS_PER_ADVISOR):
            print(row)
        print("== weekly hours per language ==")
        for row in c.execute(HOURS_PER_LANGUAGE):
            print(row)


if __name__ == "__main__":
    audit_weekly_hours()
