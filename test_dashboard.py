from datetime import date
from sqlalchemy import create_engine
import pytest

from database import (
    MD, init_db, members, payments, expenses, incomes, waivers, attendance, photo_marks,
    rent_payments, rent_plans, audit_log, get_rows, get_year_settings, rent_grid,
    resolve_photo_mark, set_member_month_status, add_rent_payment,
    set_rent_plan, get_rent_plan, delete_record, add_payment, update_payment,
)
from finance import make_ledger, yearly_summary, transaction_listing, monthly_breakdown, matrix_display


def fixture_engine():
    engine=create_engine('sqlite:///:memory:')
    MD.create_all(engine)
    init_db(engine)
    return engine


def context(e, year=2026):
    rows=get_rows(e, members); pays=get_rows(e,payments)
    photos=get_rows(e,photo_marks)
    ledger=make_ledger(rows,pays,get_rows(e,waivers),get_year_settings(e, year),
                       year,today=date(2026,10,14),photo_rows=photos)
    rent=get_rows(e,rent_payments)
    summ=yearly_summary(ledger,pays,get_rows(e,expenses),get_rows(e,incomes),year,
                        get_rows(e,attendance),rent)
    return rows,pays,photos,ledger,rent,summ


def test_photo_mark_is_visible_but_not_cash():
    e=fixture_engine()
    rows,pays,photos,ledger,rent,summ=context(e)
    assert len(rows)==33
    assert len(photos)==130
    assert len(pays)==0
    pending=ledger[ledger['Sinal']=='✓?']
    assert len(pending)==130
    assert '✓?' in matrix_display(ledger).to_string()
    assert summ['receipts']==0 and summ['total_balance']==0
    assert ledger['Por confirmar'].sum()==130*3500


def test_photo_confirm_reject_no_duplicate_cash():
    e=fixture_engine()
    mark=get_rows(e,photo_marks)[0]
    resolve_photo_mark(e,mark['member_id'],2026,mark['month'],True)
    assert context(e)[-1]['total_balance']==3500
    with pytest.raises(ValueError):
        resolve_photo_mark(e,mark['member_id'],2026,mark['month'],True)
    set_member_month_status(e,mark['member_id'],2026,mark['month'],True,3500)
    assert context(e)[-1]['total_balance']==3500


def test_unpaid_mark_rejected_only_explicitly():
    e=fixture_engine()
    mark=get_rows(e,photo_marks)[0]
    resolve_photo_mark(e,mark['member_id'],2026,mark['month'],False)
    assert len(get_rows(e,payments)) == 0
    assert context(e)[-1]['total_balance']==0
    assert context(e)[2][0]['status'] == 'rejeitada'


def test_pay_month_and_explicit_undo_keeps_audit():
    e=fixture_engine()
    person=get_rows(e,members)[0]
    set_member_month_status(e, person['id'], 2026, 1, True, 3500, date(2026, 1, 18))
    assert context(e)[-1]['total_balance'] == 3500
    with pytest.raises(ValueError):
        set_member_month_status(e, person['id'], 2026, 1, False, 3500)
    set_member_month_status(e, person['id'], 2026, 1, False, 3500, allow_undo=True)
    assert context(e)[-1]['total_balance'] == 0
    assert any(x['event']=='ANULAR_MENSALIDADE' for x in get_rows(e, audit_log))


def test_rent_is_expense_month_and_salary_accrual():
    e=fixture_engine()
    set_rent_plan(e,2026,15000)
    assert get_rent_plan(e,2026)['monthly_rent'] == 15000
    add_rent_payment(e,2026,8,10000,date(2026,8,12),'primeira parcela')
    add_rent_payment(e,2026,8,5000,date(2026,9,2),'resto')
    d=rent_grid(2026,15000,get_rows(e,rent_payments),date(2026,10,14))
    assert d[7]['Estado']=='✓ Pago'
    assert d[8]['Estado']=='· Por pagar'
    assert d[10]['Estado']=='A vencer'
    assert d[7]['Em falta']==0
    _,p,_,l,r,s=context(e)
    assert s['costs']==15000 and s['total_balance']==-15000
    assert s['rent_cost']==15000
    tx=transaction_listing(p,[],[],get_rows(e,members),2026,[],r)
    assert len(tx)==2 and tx['Saída'].sum()==15000
    monthly=monthly_breakdown(p,[],[],[],r,2026)
    assert monthly.iloc[7]['Aluguer pago']==10000
    assert monthly.iloc[8]['Aluguer pago']==5000


def test_rent_deletion_reconciles_balance():
    e=fixture_engine()
    add_rent_payment(e,2026,4,10000,date(2026,4,20))
    rent=get_rows(e,rent_payments)[0]
    delete_record(e,'aluguer',rent['id'])
    assert context(e)[-1]['total_balance']==0
    assert any(a['event']=='ELIMINAR_ALUGUER' for a in get_rows(e,audit_log))


def test_edit_payment_updates_actual_cash_no_duplicate():
    e=fixture_engine()
    person=get_rows(e,members)[0]
    add_payment(e,person['id'],2026,8,3500,date(2026,8,20))
    pay=get_rows(e,payments)[0]
    update_payment(e,pay['id'],person['id'],2026,9,5000,date(2026,9,1),'correção')
    assert context(e)[-1]['total_balance']==5000
    assert get_rows(e,payments)[0]['month']==9
    assert any(a['event']=='CORRIGIR_MENSALIDADE' for a in get_rows(e,audit_log))
