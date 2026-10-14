from datetime import date, time
import pytest
from sqlalchemy import create_engine

from database import (
    MD, add_expense, add_income, add_member, add_payment, add_attendance,
    get_rows, get_year_settings, import_photo_payments, init_db, members, payments,
    expenses, incomes, waivers, attendance, pay_attendance_fine, remove_attendance,
    session_times,
)
from finance import arrival_outcome, make_ledger, yearly_summary, transaction_listing


def fixture_engine():
    engine = create_engine('sqlite:///:memory:')
    MD.create_all(engine)
    init_db(engine)
    return engine


def person(engine):
    return next(x for x in get_rows(engine, members) if x['name'] == 'AFONSO')


def selected_row(engine, name, year, month, today):
    cfg = get_year_settings(engine, year)
    led = make_ledger(get_rows(engine, members), get_rows(engine, payments),
                      get_rows(engine, waivers), cfg, year, today)
    return led[(led['Nome'] == name) & (led['mes'] == month)].iloc[0]


def summary(engine, year, today=None):
    led = make_ledger(get_rows(engine, members), get_rows(engine, payments),
                      get_rows(engine, waivers), get_year_settings(engine, year), year, today or date(year, 12, 31))
    return yearly_summary(led, get_rows(engine, payments), get_rows(engine, expenses),
                          get_rows(engine, incomes), year, get_rows(engine, attendance))


def test_monthly_payment_never_generates_fine():
    engine = fixture_engine()
    add_payment(engine, person(engine)['id'], 2026, 2, 3500, date(2026, 2, 17))
    row = selected_row(engine, 'AFONSO', 2026, 2, date(2026, 11, 1))
    assert row['Estado'] == 'Pago'
    assert row['Em dívida'] == 0
    assert row['Multa'] == 0


def test_early_payment_future_quota():
    engine = fixture_engine()
    add_payment(engine, person(engine)['id'], 2027, 1, 3500, date(2026, 12, 23))
    assert summary(engine, 2026)['receipts'] == 3500
    assert summary(engine, 2027)['receipts'] == 0
    assert summary(engine, 2027)['total_balance'] == 3500


def test_2026_photo_import_not_automatic():
    engine = fixture_engine()
    ins, skip = import_photo_payments(engine, [{'nome': 'AFONSO', 'mes': 1, 'valor': 3500}], 2026)
    assert (ins, skip) == (1, 0)
    row = selected_row(engine, 'AFONSO', 2026, 1, date(2026, 10, 14))
    assert row['Estado'] == 'Pago'
    assert row['Multa'] == 0
    assert import_photo_payments(engine, [{'nome': 'AFONSO', 'mes': 1, 'valor': 3500}], 2026) == (0, 1)


def test_future_members_and_months():
    engine = fixture_engine()
    add_member(engine, 'NOVO', 2027, 3)
    assert selected_row(engine, 'NOVO', 2027, 1, date(2027, 2, 2))['Estado'] == '—'
    row = selected_row(engine, 'NOVO', 2027, 3, date(2027, 2, 2))
    assert row['Estado'] == 'Futuro'
    assert row['Em dívida'] == 0


def test_balance_rolls_across_years_and_ignores_debt():
    engine = fixture_engine()
    add_payment(engine, person(engine)['id'], 2026, 6, 3500, date(2026, 6, 1))
    add_income(engine, date(2026, 1, 1), 'Saldo inicial', '', 2000)
    add_expense(engine, date(2027, 2, 1), 'Bolas', '', 1500)
    assert summary(engine, 2027)['total_balance'] == 4000
    assert summary(engine, 2027)['year_balance'] == -1500


def test_training_wednesday_and_sunday_thresholds():
    assert session_times(date(2026, 10, 14)) == (time(20, 0), time(20, 15))
    assert session_times(date(2026, 10, 18)) == (time(8, 0), time(8, 15))
    with pytest.raises(ValueError):
        session_times(date(2026, 10, 15))
    engine = fixture_engine()
    mid = person(engine)['id']
    assert add_attendance(engine, mid, date(2026, 10, 7), 'Presente', time(20, 15)) == 0
    assert add_attendance(engine, mid, date(2026, 10, 11), 'Presente', time(8, 16)) == 500
    entries = get_rows(engine, attendance)
    assert entries[0]['fine_due'] == 0
    assert entries[1]['fine_due'] == 500
    assert 'não treina' in arrival_outcome(entries[1])
    assert summary(engine, 2026)['fine_debts'] == 500
    assert summary(engine, 2026)['fine_income'] == 0


def test_fine_is_per_training_and_only_paid_receipts_count():
    engine = fixture_engine()
    mid = person(engine)['id']
    add_attendance(engine, mid, date(2026, 10, 7), 'Presente', time(20, 16), 500, True, date(2026, 10, 7))
    add_attendance(engine, mid, date(2026, 10, 11), 'Presente', time(8, 16))
    entries = get_rows(engine, attendance)
    assert arrival_outcome(entries[0]) == 'Multa paga no dia · pode treinar'
    assert summary(engine, 2026)['fine_debts'] == 500
    assert summary(engine, 2026)['fine_income'] == 500
    assert summary(engine, 2026)['receipts'] == 500
    assert summary(engine, 2026)['total_balance'] == 500
    with pytest.raises(ValueError):
        add_attendance(engine, mid, date(2026, 10, 7), 'Presente', time(20, 30))
    pay_attendance_fine(engine, entries[1]['id'], date(2026, 10, 12))
    updated = get_rows(engine, attendance)
    assert arrival_outcome(updated[1]) == 'Multa liquidada depois do treino'
    assert summary(engine, 2026)['fine_income'] == 1000
    assert summary(engine, 2026)['fine_debts'] == 0
    with pytest.raises(ValueError):
        remove_attendance(engine, entries[0]['id'])
    rows = transaction_listing(get_rows(engine, payments), get_rows(engine, expenses),
                               get_rows(engine, incomes), get_rows(engine, members), 2026, updated)
    assert (rows['Tipo'] == 'Multa de treino').sum() == 2


def test_absence_no_fine_and_correction_without_payment():
    engine = fixture_engine()
    mid = person(engine)['id']
    add_attendance(engine, mid, date(2026, 10, 11), 'Falta')
    row = get_rows(engine, attendance)[0]
    assert row['fine_due'] == 0
    assert arrival_outcome(row) == 'Faltou'
    remove_attendance(engine, row['id'])
    assert not get_rows(engine, attendance)


def test_fine_cannot_be_credited_before_session():
    engine = fixture_engine()
    mid = person(engine)['id']
    with pytest.raises(ValueError):
        add_attendance(engine, mid, date(2026, 10, 11), 'Presente', time(8, 16),
                       500, True, date(2026, 10, 7))
