"""Persistência multi-ano: SQLite local ou PostgreSQL gerido, via SQLAlchemy."""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
import os

import pandas as pd
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, MetaData, String, Time,
    Table, UniqueConstraint, create_engine, delete, insert, select, update,
)

BASE = Path(__file__).parent
MD = MetaData()

members = Table(
    'members', MD,
    Column('id', Integer, primary_key=True),
    Column('name', String(120), nullable=False),
    Column('start_year', Integer, nullable=False),
    Column('start_month', Integer, nullable=False),
    Column('end_year', Integer, nullable=True),
    Column('end_month', Integer, nullable=True),
    Column('needs_review', Boolean, nullable=False, default=False),
)
settings = Table(
    'year_settings', MD,
    Column('year', Integer, primary_key=True),
    Column('monthly_fee', Integer, nullable=False, default=3500),
    Column('late_fee', Integer, nullable=False, default=500),
    Column('due_day', Integer, nullable=False, default=10),
    Column('verified', Boolean, nullable=False, default=False),
)
payments = Table(
    'payments', MD,
    Column('id', Integer, primary_key=True),
    Column('member_id', Integer, ForeignKey('members.id'), nullable=False),
    Column('year', Integer, nullable=False),
    Column('month', Integer, nullable=False),
    Column('amount', Integer, nullable=False),
    Column('paid_on', Date, nullable=True),
    Column('origin', String(40), nullable=False, default='manual'),
    Column('note', String(250), nullable=False, default=''),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
)
expenses = Table(
    'expenses', MD,
    Column('id', Integer, primary_key=True),
    Column('expense_on', Date, nullable=False),
    Column('category', String(80), nullable=False),
    Column('description', String(250), nullable=False, default=''),
    Column('amount', Integer, nullable=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
)
incomes = Table(
    'other_incomes', MD,
    Column('id', Integer, primary_key=True),
    Column('received_on', Date, nullable=False),
    Column('category', String(80), nullable=False),
    Column('description', String(250), nullable=False, default=''),
    Column('amount', Integer, nullable=False),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
)
waivers = Table(
    'penalty_waivers', MD,
    Column('id', Integer, primary_key=True),
    Column('member_id', Integer, ForeignKey('members.id'), nullable=False),
    Column('year', Integer, nullable=False),
    Column('month', Integer, nullable=False),
    Column('reason', String(250), nullable=False, default=''),
    UniqueConstraint('member_id', 'year', 'month', name='uq_waiver_period'),
)

# Cada associado tem no máximo um registo por treino. Não se presumem faltas
# para membros sem registo de presença.
attendance = Table(
    'attendance', MD,
    Column('id', Integer, primary_key=True),
    Column('member_id', Integer, ForeignKey('members.id'), nullable=False),
    Column('session_on', Date, nullable=False),
    Column('arrived_at', Time, nullable=True),
    Column('attendance_status', String(20), nullable=False),
    Column('fine_due', Integer, nullable=False, default=0),
    Column('fine_paid', Integer, nullable=False, default=0),
    Column('paid_on', Date, nullable=True),
    Column('note', String(250), nullable=False, default=''),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
    UniqueConstraint('member_id', 'session_on', name='uq_attendance_member_session'),
)

# Lista recolhida das fotografias, APENAS nomes. Grafias duvidosas marcadas.
PHOTO_NAMES = [
    ('ABDEL', True), ('AFONSO', False), ('ALADE', True), ('ALCINDO', False),
    ('AMARO', False), ('AMILCAR', False), ('ATHAIR', True), ('BETO', False),
    ('BIFA', True), ('BUBA', False), ('CATEM', True), ('JARI', True),
    ('JAR RENATO', True), ('JEAN', False), ('JOSE', False), ('KUMEU', True),
    ('JUNILSON', False), ('JUNIOR BLACK', False), ('MADJER', True),
    ('MAMADU', False), ('MAMADY', False), ('MANE', False),
    ('MUANO', True), ('NEO', False), ('NELSON', False), ('PASCOAL PIRES', True),
    ('PAULO', False), ('SAMBA', False), ('SEBASTIEN', False), ('TCHF', True),
    ('TEOMARIO', True), ('VARI', True), ('WILSON', False),
]


def make_engine(db_url: str | None = None):
    if not db_url:
        db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        (BASE / 'data').mkdir(exist_ok=True)
        db_url = f"sqlite:///{(BASE / 'data' / 'amigos.db').as_posix()}"
    if db_url.startswith('postgres://'):
        db_url = 'postgresql+psycopg2://' + db_url[len('postgres://'):]
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    kwargs = {'pool_pre_ping': True}
    if db_url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 30}
    return create_engine(db_url, **kwargs)


def init_db(engine):
    MD.create_all(engine)
    with engine.begin() as conn:
        if not conn.execute(select(members.c.id).limit(1)).first():
            conn.execute(insert(members), [
                {'name': name, 'start_year': 2026, 'start_month': 1, 'needs_review': uncertain}
                for name, uncertain in PHOTO_NAMES
            ])
        if not conn.execute(select(settings.c.year).where(settings.c.year == 2026)).first():
            conn.execute(insert(settings).values(year=2026, monthly_fee=3500, late_fee=500, due_day=10, verified=False))


def get_rows(engine, table):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(select(table)).mappings()]


def get_year_settings(engine, year):
    with engine.begin() as conn:
        row = conn.execute(select(settings).where(settings.c.year == int(year))).mappings().first()
        if row:
            return dict(row)
        earlier = conn.execute(select(settings).where(settings.c.year < int(year)).order_by(settings.c.year.desc())).mappings().first()
        vals = {
            'year': int(year),
            'monthly_fee': int(earlier['monthly_fee']) if earlier else 3500,
            'late_fee': int(earlier['late_fee']) if earlier else 500,
            'due_day': int(earlier['due_day']) if earlier else 10,
            'verified': False,
        }
        conn.execute(insert(settings).values(**vals))
        return vals


def update_year(engine, year, monthly_fee, late_fee, due_day, verified):
    get_year_settings(engine, year)
    with engine.begin() as conn:
        conn.execute(update(settings).where(settings.c.year == int(year)).values(
            monthly_fee=int(monthly_fee), late_fee=int(late_fee),
            due_day=int(due_day), verified=bool(verified),
        ))


def add_payment(engine, member_id, year, month, amount, paid_on=None, note='', origin='manual'):
    if int(amount) <= 0 or not (1 <= int(month) <= 12):
        raise ValueError('Montante e mês inválidos')
    with engine.begin() as conn:
        conn.execute(insert(payments).values(
            member_id=int(member_id), year=int(year), month=int(month),
            amount=int(amount), paid_on=paid_on, note=note.strip(), origin=origin,
        ))


def add_expense(engine, expense_on, category, description, amount):
    if int(amount) <= 0:
        raise ValueError('Montante inválido')
    with engine.begin() as conn:
        conn.execute(insert(expenses).values(
            expense_on=expense_on, category=category, description=description.strip(), amount=int(amount)
        ))


def add_income(engine, received_on, category, description, amount):
    if int(amount) <= 0:
        raise ValueError('Montante inválido')
    with engine.begin() as conn:
        conn.execute(insert(incomes).values(
            received_on=received_on, category=category, description=description.strip(), amount=int(amount)
        ))


def add_member(engine, name, start_year, start_month, needs_review=False):
    name = name.strip().upper()
    if not name or not (1 <= int(start_month) <= 12):
        raise ValueError('Nome e mês de entrada obrigatórios')
    with engine.begin() as conn:
        conn.execute(insert(members).values(
            name=name, start_year=int(start_year), start_month=int(start_month), needs_review=bool(needs_review)
        ))


def change_member(engine, mid, name, start_year, start_month, end_year=None, end_month=None, needs_review=False):
    name = name.strip().upper()
    if not name or not (1 <= int(start_month) <= 12) or (end_month is not None and not (1 <= int(end_month) <= 12)):
        raise ValueError('Dados inválidos')
    if end_year is not None and (int(end_year), int(end_month)) < (int(start_year), int(start_month)):
        raise ValueError('A data de saída não pode preceder a entrada')
    with engine.begin() as conn:
        conn.execute(update(members).where(members.c.id == int(mid)).values(
            name=name, start_year=int(start_year), start_month=int(start_month),
            end_year=int(end_year) if end_year is not None else None,
            end_month=int(end_month) if end_month is not None else None,
            needs_review=bool(needs_review),
        ))


def set_waiver(engine, member_id, year, month, waive, reason=''):
    with engine.begin() as conn:
        filters = (waivers.c.member_id == int(member_id)) & (waivers.c.year == int(year)) & (waivers.c.month == int(month))
        conn.execute(delete(waivers).where(filters))
        if waive:
            conn.execute(insert(waivers).values(
                member_id=int(member_id), year=int(year), month=int(month), reason=reason.strip()
            ))


def delete_record(engine, typ, record_id):
    tables = {'pagamento': payments, 'despesa': expenses, 'receita': incomes}
    if typ not in tables:
        raise ValueError('Tipo inválido')
    with engine.begin() as conn:
        conn.execute(delete(tables[typ]).where(tables[typ].c.id == int(record_id)))


def csv_export(engine, typ):
    tables = {'membros': members, 'pagamentos': payments, 'despesas': expenses, 'outras_receitas': incomes, 'dispensas_multa': waivers, 'treinos_multas': attendance}
    return pd.DataFrame(get_rows(engine, tables[typ])).to_csv(index=False).encode('utf-8-sig')


def import_photo_payments(engine, rows, year=2026):
    """Importa somente pagamentos selecionados e aprovados pelo financeiro, evita duplicados da mesma fonte."""
    inserted, skipped = 0, 0
    with engine.begin() as conn:
        existing_members = {r['name'].upper(): r['id'] for r in conn.execute(select(members.c.id, members.c.name)).mappings()}
        for row in rows:
            name = str(row.get('nome', '')).strip().upper()
            mid = existing_members.get(name)
            month = int(row['mes'])
            amount = int(row['valor'])
            if not mid or not (1 <= month <= 12) or amount <= 0:
                skipped += 1
                continue
            prior = conn.execute(select(payments.c.id).where(
                (payments.c.member_id == mid) & (payments.c.year == int(year)) &
                (payments.c.month == month) & (payments.c.origin == 'foto_2026')
            )).first()
            if prior:
                skipped += 1
                continue
            conn.execute(insert(payments).values(
                member_id=mid, year=int(year), month=month,
                amount=amount, paid_on=None,
                origin='foto_2026', note='Marca na fotografia; data não conhecida, confirmar com tesouraria',
            ))
            inserted += 1
    return inserted, skipped


def session_times(session_on):
    """Hora de início e última chegada sem multa para treinos regulares."""
    from datetime import time
    if session_on.weekday() == 2:  # quarta-feira
        return time(20, 0), time(20, 15)
    if session_on.weekday() == 6:  # domingo
        return time(8, 0), time(8, 15)
    raise ValueError('Os treinos regulares são apenas à quarta-feira e ao domingo.')


def add_attendance(engine, member_id, session_on, status, arrived_at=None, fine_amount=500,
                   paid=False, paid_on=None, note=''):
    """Regista uma presença; a multa nasce apenas de chegada depois dos 15 minutos."""
    from sqlalchemy.exc import IntegrityError
    start, deadline = session_times(session_on)
    if session_on > date.today():
        raise ValueError('Não é possível registar presenças de treinos futuros')
    if status not in ('Presente', 'Falta'):
        raise ValueError('Estado de presença inválido')
    if status == 'Presente' and arrived_at is None:
        raise ValueError('A hora de chegada é obrigatória')
    if status == 'Falta' and paid:
        raise ValueError('Uma falta não gera multa de atraso')
    if int(fine_amount) < 0:
        raise ValueError('Montante de multa inválido')
    due = int(fine_amount) if status == 'Presente' and arrived_at > deadline else 0
    if paid and not due:
        raise ValueError('Não existe multa a pagar')
    if paid:
        if paid_on is None or paid_on < session_on or paid_on > date.today():
            raise ValueError('A data de recebimento da multa deve ser válida')
    with engine.begin() as conn:
        member = conn.execute(select(members).where(members.c.id == int(member_id))).mappings().first()
        if not member:
            raise ValueError('Membro não encontrado')
        current = (session_on.year, session_on.month)
        if current < (member['start_year'], member['start_month']) or (
            member['end_year'] is not None and current > (member['end_year'], member['end_month'])
        ):
            raise ValueError('Membro inativo na data do treino')
        existing = conn.execute(select(attendance.c.id).where(
            (attendance.c.member_id == int(member_id)) & (attendance.c.session_on == session_on)
        )).first()
        if existing:
            raise ValueError('Já existe registo deste associado neste treino. Evita duplicados.')
        try:
            conn.execute(insert(attendance).values(
                member_id=int(member_id), session_on=session_on,
                arrived_at=arrived_at if status == 'Presente' else None,
                attendance_status=status, fine_due=due,
                fine_paid=due if paid else 0,
                paid_on=paid_on if paid else None,
                note=note.strip(),
            ))
        except IntegrityError as exc:
            raise ValueError('Já existe registo deste associado neste treino.') from exc
    return due


def pay_attendance_fine(engine, attendance_id, paid_on):
    with engine.begin() as conn:
        row = conn.execute(select(attendance).where(attendance.c.id == int(attendance_id))).mappings().first()
        if not row or row['fine_due'] <= 0 or row['fine_paid'] >= row['fine_due']:
            raise ValueError('Não existe multa pendente nesse registo')
        if paid_on < row['session_on'] or paid_on > date.today():
            raise ValueError('Confirma a data efetiva de pagamento')
        conn.execute(update(attendance).where(attendance.c.id == int(attendance_id)).values(
            fine_paid=row['fine_due'], paid_on=paid_on
        ))


def remove_attendance(engine, attendance_id):
    """Só permite corrigir presenças sem pagamentos; recebimentos requerem regularização."""
    with engine.begin() as conn:
        row = conn.execute(select(attendance).where(attendance.c.id == int(attendance_id))).mappings().first()
        if not row:
            raise ValueError('Registo inexistente')
        if row['fine_paid']:
            raise ValueError('Já existe uma multa paga. Não é possível apagar um recebimento sem regularizar as contas.')
        conn.execute(delete(attendance).where(attendance.c.id == int(attendance_id)))
