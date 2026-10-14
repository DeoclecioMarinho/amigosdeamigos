from sqlalchemy import create_engine, text
from database import (
    init_db, get_rows, members, payments, photo_marks,
    add_payment, read_photo_marks_safely,
)


def test_clean_db_reads_photo_marks(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "clean.db"}')
    init_db(engine)
    rows, ok, repaired = read_photo_marks_safely(engine)
    assert ok and not repaired
    assert len(rows) > 0


def test_deleted_photo_table_rebuilt_without_touching_payments(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "lost_photo.db"}')
    init_db(engine)
    mid = get_rows(engine, members)[0]['id']
    add_payment(engine, mid, 2026, 2, 3500)
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE photo_marks'))
    recovered, ok, repaired = read_photo_marks_safely(engine)
    assert ok and repaired
    assert len(recovered) > 0
    assert len(get_rows(engine, payments)) == 1
    assert get_rows(engine, payments)[0]['amount'] == 3500


def test_missing_optional_column_repaired_without_removing_rows(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "lost_col.db"}')
    init_db(engine)
    previous = get_rows(engine, photo_marks)
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE photo_marks'))
        conn.execute(text('CREATE TABLE photo_marks (id INTEGER PRIMARY KEY, member_id INTEGER, year INTEGER, month INTEGER, amount INTEGER)'))
        conn.execute(text("INSERT INTO photo_marks (id, member_id, year, month, amount) VALUES (1, 1, 2026, 1, 3500)"))
    recovered, ok, repaired = read_photo_marks_safely(engine)
    assert ok and repaired
    assert len(recovered) == 1
    assert recovered[0]['status'] == 'pendente'


def test_incompatible_table_kept_untouched_and_dashboard_can_continue(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "wrong_col.db"}')
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text('DROP TABLE photo_marks'))
        conn.execute(text('CREATE TABLE photo_marks (id INTEGER PRIMARY KEY, member_id INTEGER, year INTEGER, month INTEGER)'))
        conn.execute(text('INSERT INTO photo_marks(id,member_id,year,month) VALUES (1,1,2026,1)'))
    rows, ok, repaired = read_photo_marks_safely(engine)
    assert rows == [] and not ok and not repaired
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM photo_marks')).scalar() == 1
    assert len(get_rows(engine, members)) == 33
