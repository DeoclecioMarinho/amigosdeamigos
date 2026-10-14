from datetime import date
from sqlalchemy import create_engine, inspect, text
import pytest
from database import (
    MD, DatabaseSchemaError, init_db, get_rows, members, photo_marks,
    payments, attendance, rent_payments, audit_log, prepare_schema,
)


def test_updates_old_table_with_missing_optional_columns_without_losing_records(tmp_path):
    e=create_engine(f'sqlite:///{tmp_path / "past.db"}')
    with e.begin() as c:
        c.execute(text('CREATE TABLE members (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, start_year INTEGER NOT NULL, start_month INTEGER NOT NULL)'))
        c.execute(text("INSERT INTO members (id, name, start_year, start_month) VALUES (1, 'AFONSO', 2026, 1)"))
        c.execute(text('CREATE TABLE photo_marks (id INTEGER PRIMARY KEY, member_id INTEGER, year INTEGER, month INTEGER, amount INTEGER)'))
        c.execute(text('INSERT INTO photo_marks (id, member_id, year, month, amount) VALUES (1, 1, 2026, 1, 3500)'))
    init_db(e)
    rows=get_rows(e,members)
    assert any(r['name']=='AFONSO' and r['id']==1 for r in rows)
    assert len([r for r in rows if r['name']=='AFONSO']) == 1
    assert get_rows(e,photo_marks)[0]['status']=='pendente'
    assert {'needs_review','end_year','end_month'} <= {c['name'] for c in inspect(e).get_columns('members')}
    assert len(get_rows(e,rent_payments)) == 0
    # Ir novamente ao mesmo esquema deve ser seguro e preservar os registos.
    init_db(e)
    assert len(get_rows(e,photo_marks)) == 1


def test_existing_attendance_values_are_kept(tmp_path):
    e=create_engine(f'sqlite:///{tmp_path / "att.db"}')
    with e.begin() as c:
        c.execute(text('CREATE TABLE attendance (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, session_on DATE NOT NULL, attendance_status VARCHAR(20) NOT NULL)'))
        c.execute(text("INSERT INTO attendance(id,member_id,session_on,attendance_status) VALUES (1,1,'2026-10-07','Presente')"))
    prepare_schema(e)
    r=get_rows(e,attendance)[0]
    assert r['fine_due']==0 and r['fine_paid']==0 and r['attendance_status']=='Presente'
    assert r['session_on']==date(2026,10,7)


def test_fails_safely_if_essential_accounting_columns_are_missing(tmp_path):
    e=create_engine(f'sqlite:///{tmp_path / "bad.db"}')
    with e.begin() as c:
        c.execute(text('CREATE TABLE payments (id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL)'))
        c.execute(text('INSERT INTO payments(id,member_id,year,month) VALUES (1,1,2026,1)'))
    with pytest.raises(DatabaseSchemaError, match='payments.*amount'):
        prepare_schema(e)
    with e.connect() as c:
        assert c.execute(text('SELECT COUNT(*) FROM payments')).scalar()==1
        assert 'amount' not in {col['name'] for col in inspect(e).get_columns('payments')}


def test_full_current_schema_does_not_need_migration(tmp_path):
    e=create_engine(f'sqlite:///{tmp_path / "new.db"}')
    init_db(e)
    first=len(get_rows(e,members))
    assert first == 33
    init_db(e)
    assert len(get_rows(e,members)) == first
