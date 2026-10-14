"""Contabilidade do grupo: quotas mensais + multas de chegada tardia aos treinos."""
from __future__ import annotations
from datetime import date
from collections import defaultdict
import pandas as pd

MONTHS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
MONTH_ABBR = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
EXPENSE_CATEGORIES = ['Aluguer do pavilhão', 'Lavagem de equipamentos', 'Bolas', 'Apitos',
                      'Coletes', 'Bomba de ar', 'Outros equipamentos', 'Água e consumíveis', 'Outras despesas']
INCOME_CATEGORIES = ['Contribuição extraordinária', 'Donativo', 'Saldo inicial', 'Outras receitas']


def xof(value):
    return f"{int(value):,}".replace(',', ' ') + ' XOF'


def is_expected(member, year, month):
    period = (int(year), int(month))
    start = (int(member['start_year']), int(member['start_month']))
    end = ((int(member['end_year']), int(member['end_month']))
           if member.get('end_year') is not None and member.get('end_month') is not None else None)
    return period >= start and (end is None or period <= end)


def make_ledger(member_rows, payment_rows, waiver_rows, cfg, year, today=None):
    """As mensalidades não têm multa automática. Multas só surgem de chegadas tardias."""
    today = today or date.today()
    paid_by_period = defaultdict(int)
    for p in payment_rows:
        if int(p['year']) == int(year):
            paid_by_period[(int(p['member_id']), int(p['month']))] += int(p['amount'])
    records = []
    for member in sorted(member_rows, key=lambda m: str(m['name']).casefold()):
        for month in range(1, 13):
            base = {'id': member['id'], 'Nome': member['name'], 'mes': month,
                    'Multa': 0, 'Rever nome': bool(member['needs_review'])}
            if not is_expected(member, year, month):
                records.append({**base, 'Estado': '—', 'Pago': 0, 'Devido': 0, 'Em dívida': 0,
                                'Aplicável': False})
                continue
            paid = paid_by_period[(int(member['id']), month)]
            due = int(cfg['monthly_fee'])
            future = date(year, month, 1) > today
            if paid >= due:
                status = 'Adiantado' if future else 'Pago'
            elif future:
                status = 'Futuro'
            elif paid > 0:
                status = 'Parcial'
            else:
                status = 'Por pagar'
            records.append({**base, 'Estado': status, 'Pago': paid, 'Devido': due,
                            'Em dívida': max(0, due - paid) if not future else 0,
                            'Aplicável': True})
    return pd.DataFrame(records)


def arrival_outcome(row):
    """Distingue pagamento posterior de multa e autorização no dia do treino."""
    if row['attendance_status'] == 'Falta':
        return 'Faltou'
    if not row['fine_due']:
        return 'Pontual · pode treinar'
    if row['fine_paid'] >= row['fine_due']:
        if row['paid_on'] == row['session_on']:
            return 'Multa paga no dia · pode treinar'
        return 'Multa liquidada depois do treino'
    return 'Multa por pagar · não treina'


def yearly_summary(ledger, payments, expenses, incomes, year, attendance_rows=()):
    """Receita pertence à data em que foi recebida, inclusive multas de treino."""
    year = int(year)
    month_payment = [sum(int(p['amount']) for p in payments
                         if p['paid_on'] is not None and (p['paid_on'].year, p['paid_on'].month) == (year, m))
                     + sum(int(p['amount']) for p in payments
                           if p['paid_on'] is None and (int(p['year']), int(p['month'])) == (year, m))
                     for m in range(1, 13)]
    month_fine = [sum(int(r['fine_paid']) for r in attendance_rows
                      if r['paid_on'] is not None and (r['paid_on'].year, r['paid_on'].month) == (year, m))
                  for m in range(1, 13)]
    month_income_other = [sum(int(i['amount']) for i in incomes if i['received_on'].year == year and i['received_on'].month == m) for m in range(1, 13)]
    month_expense = [sum(int(e['amount']) for e in expenses if e['expense_on'].year == year and e['expense_on'].month == m) for m in range(1, 13)]
    receipts = sum(month_payment) + sum(month_income_other) + sum(month_fine)
    costs = sum(month_expense)
    total_balance = (sum(int(p['amount']) for p in payments) + sum(int(i['amount']) for i in incomes)
                     + sum(int(r['fine_paid']) for r in attendance_rows) - sum(int(e['amount']) for e in expenses))
    arrears = int(ledger['Em dívida'].sum()) if not ledger.empty else 0
    fine_debts = sum(int(r['fine_due']) - int(r['fine_paid']) for r in attendance_rows if r['session_on'].year == year)
    series = pd.DataFrame({'Mês': MONTH_ABBR, 'Receitas': [a + b + c for a, b, c in zip(month_payment, month_fine, month_income_other)],
                           'Despesas': month_expense})
    return {'receipts': receipts, 'costs': costs, 'year_balance': receipts - costs,
            'total_balance': total_balance, 'arrears': arrears, 'fine_debts': fine_debts,
            'chart': series, 'other_income': sum(month_income_other),
            'member_income': sum(month_payment), 'fine_income': sum(month_fine)}


def matrix_display(ledger, selected_month=None, search=''):
    if ledger.empty:
        return pd.DataFrame()
    df = ledger.copy()
    if search:
        df = df[df['Nome'].str.contains(search, case=False, regex=False, na=False)]
    if selected_month is not None:
        df = df[df['mes'] == int(selected_month)]
        return df[['Nome', 'Estado', 'Pago', 'Em dívida', 'Rever nome']].reset_index(drop=True)
    pivot = df.pivot(index=['id', 'Nome'], columns='mes', values='Estado').reindex(columns=range(1, 13))
    pivot.columns = MONTH_ABBR
    pivot = pivot.reset_index(drop=False).drop(columns='id')
    debt = df.groupby('Nome', as_index=False)['Em dívida'].sum().rename(columns={'Em dívida': 'Dívida (XOF)'})
    return pivot.merge(debt, on='Nome', how='left')


def transaction_listing(payments, expenses, incomes, members, year=None, attendance_rows=()):
    names = {m['id']: m['name'] for m in members}
    items = []
    for p in payments:
        if year is None or ((p['paid_on'].year if p['paid_on'] is not None else int(p['year'])) == int(year)):
            items.append({'Data': p['paid_on'] or date(int(p['year']), int(p['month']), 1),
                          'Tipo': 'Mensalidade', 'Nome / descrição': names.get(p['member_id'], '(membro removido)'),
                          'Detalhe': f"{MONTHS[int(p['month'])-1]} {p['year']} · {p['origin']}", 'Entrada': int(p['amount']),
                          'Saída': 0, 'ID': p['id'], 'classe': 'pagamento'})
    for r in attendance_rows:
        if int(r['fine_paid']) <= 0:
            continue
        if year is None or r['paid_on'].year == int(year):
            items.append({'Data': r['paid_on'], 'Tipo': 'Multa de treino',
                          'Nome / descrição': names.get(r['member_id'], '(membro removido)'),
                          'Detalhe': f"Treino {r['session_on'].strftime('%d/%m/%Y')} · chegada {r['arrived_at'].strftime('%H:%M')}",
                          'Entrada': int(r['fine_paid']), 'Saída': 0, 'ID': r['id'], 'classe': 'multa'})
    for e in expenses:
        if year is None or e['expense_on'].year == int(year):
            items.append({'Data': e['expense_on'], 'Tipo': 'Despesa', 'Nome / descrição': e['category'],
                          'Detalhe': e['description'], 'Entrada': 0, 'Saída': int(e['amount']),
                          'ID': e['id'], 'classe': 'despesa'})
    for i in incomes:
        if year is None or i['received_on'].year == int(year):
            items.append({'Data': i['received_on'], 'Tipo': 'Outra receita', 'Nome / descrição': i['category'],
                          'Detalhe': i['description'], 'Entrada': int(i['amount']), 'Saída': 0,
                          'ID': i['id'], 'classe': 'receita'})
    return pd.DataFrame(items).sort_values(by=['Data', 'ID'], ascending=[False, False], na_position='last') if items else pd.DataFrame()
