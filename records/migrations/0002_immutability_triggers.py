"""The database refuses to change or delete versions (#23 section 3.1, #37).

One trigger function for all versioned tables. An UPDATE passes only if it
sets `status` from `active` to `superseded` and leaves every other column as
it was, or if it sets one of the columns named as trigger arguments to NULL
and nothing else (SET NULL of `Encounter.appointment`). Comparing whole rows
as jsonb also covers columns that K3 to K5 add. Every DELETE is refused; the
way for the retention run comes with K8 (#27, open question 8).

A second, deferred trigger checks at commit that every row set to
`superseded` has a successor (`replaces` points at it). Otherwise raw SQL or
a stray `_supersede()` could hide a record without a new version, author and
reason. Deferred, because `services` supersedes the old head before it
inserts the new one (the database allows only one head per lineage).

Entries in error do not need an UPDATE: `mark_entered_in_error` adds a new
version with status `entered_in_error` and the reason, so who marked it, when
and why stays in the record like every other change.
"""

from django.db import migrations

TABLES = {
    "records_encounter": ["appointment_id"],
    "records_chartentry": [],
}

FUNCTION = r"""
CREATE FUNCTION records_protect_versions() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    nullable text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Fassungen in % werden nie gelöscht.', TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.status = 'active' AND NEW.status = 'superseded'
       AND to_jsonb(NEW) - 'status' = to_jsonb(OLD) - 'status' THEN
        RETURN NEW;
    END IF;
    FOREACH nullable IN ARRAY coalesce(TG_ARGV, '{}') LOOP
        IF to_jsonb(OLD) ->> nullable IS NOT NULL
           AND to_jsonb(NEW) ->> nullable IS NULL
           AND to_jsonb(NEW) - nullable = to_jsonb(OLD) - nullable THEN
            RETURN NEW;
        END IF;
    END LOOP;
    RAISE EXCEPTION 'Fassungen in % werden nie geändert, nur ersetzt.', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;
"""


SUCCESSOR_FUNCTION = r"""
CREATE FUNCTION records_require_successor() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    found boolean;
BEGIN
    IF OLD.status <> 'superseded' AND NEW.status = 'superseded' THEN
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE replaces_id = $1)', TG_TABLE_NAME)
            INTO found USING NEW.id;
        IF NOT found THEN
            RAISE EXCEPTION 'Fassung % in % ist ersetzt, aber ohne Nachfolger.',
                NEW.id, TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
"""


def _successor_trigger(table):
    return (
        f"CREATE CONSTRAINT TRIGGER {table}_require_successor AFTER UPDATE ON {table} "
        "DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION records_require_successor();"
    )


def _trigger(table, nullable):
    args = ", ".join(f"'{column}'" for column in nullable)
    return (
        f"CREATE TRIGGER {table}_protect_versions BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION records_protect_versions({args});"
    )


class Migration(migrations.Migration):
    dependencies = [("records", "0001_initial")]

    operations = [
        migrations.RunSQL(FUNCTION, "DROP FUNCTION records_protect_versions();"),
        *(
            migrations.RunSQL(
                _trigger(table, nullable),
                f"DROP TRIGGER {table}_protect_versions ON {table};",
            )
            for table, nullable in TABLES.items()
        ),
        migrations.RunSQL(SUCCESSOR_FUNCTION, "DROP FUNCTION records_require_successor();"),
        *(
            migrations.RunSQL(
                _successor_trigger(table),
                f"DROP TRIGGER {table}_require_successor ON {table};",
            )
            for table in TABLES
        ),
    ]
