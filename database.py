"""Persistência multi-ano: SQLite local ou PostgreSQL gerido, via SQLAlchemy."""
from __future__ import annotations

APP_COMPAT_VERSION = '4.4'

from datetime import date, datetime, time
import csv
from pathlib import Path
import os
import logging

import pandas as pd
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, MetaData, String, Time,
    Table, UniqueConstraint, create_engine, delete, insert, inspect, select, text, update,
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

# Pagamentos do aluguer identificados pelo ANO/MÊS de utilização do pavilhão.
# São despesas efetivas apenas quando pagos; a obrigação é configurada por ano.
rent_plans = Table(
    'rent_plans', MD,
    Column('year', Integer, primary_key=True),
    Column('monthly_rent', Integer, nullable=False, default=0),
    Column('note', String(250), nullable=False, default=''),
)
rent_payments = Table(
    'rent_payments', MD,
    Column('id', Integer, primary_key=True),
    Column('year', Integer, nullable=False),
    Column('month', Integer, nullable=False),
    Column('amount', Integer, nullable=False),
    Column('paid_on', Date, nullable=False),
    Column('note', String(250), nullable=False, default=''),
    Column('created_at', DateTime, nullable=False, default=datetime.utcnow),
)
# Registo de correções da tesouraria. Não é uma contabilidade auditada; preserva
# ao menos o evento de uma alteração/remoção feita a partir do ecrã.
audit_log = Table(
    'audit_log', MD,
    Column('id', Integer, primary_key=True),
    Column('changed_at', DateTime, nullable=False, default=datetime.utcnow),
    Column('actor', String(100), nullable=False, default='financeiro'),
    Column('event', String(100), nullable=False),
    Column('details', String(500), nullable=False, default=''),
)

# Marcas identificadas na fotografia original. NUNCA são dinheiro recebido
# até que o financeiro confirme manualmente cada marca. Registos recusados
# conservam-se para não reaparecerem após reiniciar a aplicação.
photo_marks = Table(
    'photo_marks', MD,
    Column('id', Integer, primary_key=True),
    Column('member_id', Integer, ForeignKey('members.id'), nullable=False),
    Column('year', Integer, nullable=False),
    Column('month', Integer, nullable=False),
    Column('amount', Integer, nullable=False),
    Column('status', String(16), nullable=False, default='pendente'),
    UniqueConstraint('member_id', 'year', 'month', name='uq_photo_member_month'),
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


# Atualizações compatíveis com as tabelas das versões anteriores.
# Nunca apaga tabelas nem registos. As colunas essenciais ausentes não são
# inventadas, porque isso corromperia o histórico de pagamentos.
SAFE_NEW_COLUMNS = {
    'members': {
        'end_year': 'INTEGER', 'end_month': 'INTEGER',
        'needs_review': 'BOOLEAN NOT NULL DEFAULT 0',
    },
    'year_settings': {
        'late_fee': 'INTEGER NOT NULL DEFAULT 500',
        'due_day': 'INTEGER NOT NULL DEFAULT 10',
        'verified': 'BOOLEAN NOT NULL DEFAULT 0',
    },
    'payments': {
        'paid_on': 'DATE', 'origin': "VARCHAR(40) NOT NULL DEFAULT 'manual'",
        'note': "VARCHAR(250) NOT NULL DEFAULT ''", 'created_at': 'TIMESTAMP',
    },
    'expenses': {
        'description': "VARCHAR(250) NOT NULL DEFAULT ''", 'created_at': 'TIMESTAMP',
    },
    'other_incomes': {
        'description': "VARCHAR(250) NOT NULL DEFAULT ''", 'created_at': 'TIMESTAMP',
    },
    'penalty_waivers': {'reason': "VARCHAR(250) NOT NULL DEFAULT ''"},
    'attendance': {
        'arrived_at': 'TIME', 'fine_due': 'INTEGER NOT NULL DEFAULT 0',
        'fine_paid': 'INTEGER NOT NULL DEFAULT 0', 'paid_on': 'DATE',
        'note': "VARCHAR(250) NOT NULL DEFAULT ''", 'created_at': 'TIMESTAMP',
    },
    'photo_marks': {'status': "VARCHAR(16) NOT NULL DEFAULT 'pendente'"},
    'rent_plans': {'note': "VARCHAR(250) NOT NULL DEFAULT ''"},
    'rent_payments': {'note': "VARCHAR(250) NOT NULL DEFAULT ''", 'created_at': 'TIMESTAMP'},
    'audit_log': {
        'changed_at': 'TIMESTAMP', 'actor': "VARCHAR(100) NOT NULL DEFAULT 'financeiro'",
        'details': "VARCHAR(500) NOT NULL DEFAULT ''",
    },
}


class DatabaseSchemaError(RuntimeError):
    """Existe uma tabela antiga incompatível que não pode ser alterada com segurança."""


def prepare_schema(engine):
    """Cria tabelas novas e acrescenta apenas colunas seguras em tabelas antigas.

    create_all() por si só não migra tabelas já existentes. As alterações são
    aditivas, transacionais quando suportado pelo motor, e não tocam em valores
    guardados. Colunas com data de registo podem ficar NULL em dados antigos.
    """
    MD.create_all(engine)
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in MD.sorted_tables:
            name = table.name
            if not inspector.has_table(name):
                raise DatabaseSchemaError(f'Tabela em falta: {name}')
            actual = {col['name'] for col in inspector.get_columns(name)}
            expected = {col.name for col in table.columns}
            missing = expected - actual
            essential = missing - set(SAFE_NEW_COLUMNS.get(name, {}))
            if essential:
                raise DatabaseSchemaError(
                    f'Tabela {name}: colunas essenciais em falta: {", ".join(sorted(essential))}. '
                    'É necessária uma migração manual sem perda de dados.'
                )
            for column in sorted(missing):
                sql_type = SAFE_NEW_COLUMNS[name][column]
                # Nomes das tabelas/colunas e expressões vêm apenas do código,
                # nunca de entrada do utilizador.
                conn.execute(text(f'ALTER TABLE "{name}" ADD COLUMN "{column}" {sql_type}'))
            # Algumas versões antigas poderão ter datas de auditoria em falta.
            if 'created_at' in missing:
                conn.execute(text(f'UPDATE "{name}" SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL'))
            if 'changed_at' in missing:
                conn.execute(text(f'UPDATE "{name}" SET changed_at = CURRENT_TIMESTAMP WHERE changed_at IS NULL'))


def init_db(engine):
    prepare_schema(engine)
    with engine.begin() as conn:
        if not conn.execute(select(members.c.id).limit(1)).first():
            conn.execute(insert(members), [
                {'name': name, 'start_year': 2026, 'start_month': 1, 'needs_review': uncertain}
                for name, uncertain in PHOTO_NAMES
            ])
        if not conn.execute(select(settings.c.year).where(settings.c.year == 2026)).first():
            conn.execute(insert(settings).values(year=2026, monthly_fee=3500, late_fee=500, due_day=10, verified=False))

        # Semente apenas uma vez. Idempotente na base já utilizada (SQLite/PostgreSQL).
        # As marcas NÃO entram em payments e não geram receita nem saldo.
        csv_path = BASE / 'historico_foto_2026_para_validar.csv'
        if csv_path.exists() and not conn.execute(select(photo_marks.c.id).limit(1)).first():
            ids = {r['name'].strip().upper(): r['id'] for r in
                   conn.execute(select(members.c.id, members.c.name)).mappings()}
            with csv_path.open(encoding='utf-8-sig', newline='') as fh:
                seen = set()
                new_rows = []
                for r in csv.DictReader(fh):
                    key = (r['nome'].strip().upper(), int(r['mes']))
                    if key in seen or key[0] not in ids or not 1 <= key[1] <= 12:
                        continue
                    seen.add(key)
                    new_rows.append(dict(member_id=ids[key[0]], year=2026,
                                         month=key[1], amount=int(r['valor']),
                                         status='pendente'))
                if new_rows:
                    conn.execute(insert(photo_marks), new_rows)


def get_rows(engine, table):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(select(table)).mappings()]


def read_photo_marks_safely(engine):
    """Lê as marcas provisórias sem comprometer os movimentos financeiros.

    Se a tabela / coluna não existir, volta a aplicar as migrações aditivas e
    tenta ler novamente. Noutras falhas SQL, não tenta DDL nem apaga nada:
    a funcionalidade de conferência fica indisponível até haver diagnóstico.
    Devolve (marcas, disponivel, reparada).
    """
    try:
        return get_rows(engine, photo_marks), True, False
    except (OperationalError, ProgrammingError) as err:
        logging.exception('Consulta photo_marks falhou: %s', type(err).__name__)
        reason = str(getattr(err, 'orig', err)).lower()
        # Apenas erros de tabela/coluna ausente permitem uma tentativa segura.
        recoverable = (
            'no such table' in reason or 'no such column' in reason
            or ('does not exist' in reason and ('photo_marks' in reason or 'column' in reason))
            or 'undefinedtable' in reason or 'undefinedcolumn' in reason
        )
        if recoverable:
            try:
                init_db(engine)  # ADD COLUMN / CREATE TABLE sem DROP ou DELETE.
                rows = get_rows(engine, photo_marks)
                logging.warning('photo_marks recuperada através de migração aditiva')
                return rows, True, True
            except Exception:
                logging.exception('Não foi possível recuperar photo_marks sem intervenção')
        return [], False, False
    except Exception:
        logging.exception('Erro inesperado ao consultar photo_marks')
        return [], False, False


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
    tables = {'pagamento': payments, 'despesa': expenses, 'receita': incomes, 'aluguer': rent_payments}
    if typ not in tables:
        raise ValueError('Tipo inválido')
    with engine.begin() as conn:
        previous = conn.execute(select(tables[typ]).where(tables[typ].c.id == int(record_id))).mappings().first()
        if not previous:
            raise ValueError('Lançamento inexistente')
        conn.execute(delete(tables[typ]).where(tables[typ].c.id == int(record_id)))
        conn.execute(insert(audit_log).values(event='ELIMINAR_'+typ.upper(),
                    details=f'id={record_id}; anterior={dict(previous)}'[:500]))


def csv_export(engine, typ):
    tables = {'membros': members, 'pagamentos': payments, 'despesas': expenses, 'outras_receitas': incomes, 'dispensas_multa': waivers, 'treinos_multas': attendance, 'marcas_foto': photo_marks, 'aluguer': rent_payments, 'plano_aluguer': rent_plans, 'auditoria': audit_log}
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
            prior = conn.execute(select(payments.c.amount).where(
                (payments.c.member_id == mid) & (payments.c.year == int(year)) &
                (payments.c.month == month)
            )).scalars().all()
            missing = max(0, amount - sum(prior))
            if not missing:
                skipped += 1
                continue
            conn.execute(insert(payments).values(
                member_id=mid, year=int(year), month=month,
                amount=missing, paid_on=None,
                origin='foto_2026', note='Fotografia conferida; data histórica desconhecida',
            ))
            conn.execute(update(photo_marks).where(
                (photo_marks.c.member_id == mid) & (photo_marks.c.year == int(year)) &
                (photo_marks.c.month == month) & (photo_marks.c.status == 'pendente')
            ).values(status='confirmada'))
            inserted += 1
    return inserted, skipped



def resolve_photo_mark(engine, member_id, year, month, confirmed, paid_on=None):
    """Confirma ou rejeita uma marca fotográfica; contabiliza só uma vez.

    Se já houver recebimentos suficientes, não cria pagamentos duplicados.
    A data None significa que o dia exato do recebimento histórico é desconhecido.
    """
    with engine.begin() as conn:
        stmt = select(photo_marks).where(
            (photo_marks.c.member_id == int(member_id)) &
            (photo_marks.c.year == int(year)) & (photo_marks.c.month == int(month))
        )
        mark = conn.execute(stmt).mappings().first()
        if not mark:
            raise ValueError('Marca da fotografia inexistente')
        if mark['status'] != 'pendente':
            raise ValueError('Esta marca já foi analisada')
        if confirmed:
            old = conn.execute(select(payments.c.amount).where(
                (payments.c.member_id == int(member_id)) &
                (payments.c.year == int(year)) & (payments.c.month == int(month))
            )).scalars().all()
            remainder = max(0, int(mark['amount']) - sum(old))
            if remainder:
                conn.execute(insert(payments).values(
                    member_id=int(member_id), year=int(year), month=int(month),
                    amount=remainder, paid_on=paid_on, origin='foto_confirmada',
                    note='Fotografia conferida pelo financeiro; data histórica não conhecida'
                    if paid_on is None else 'Marca da fotografia confirmada pelo financeiro',
                ))
        conn.execute(update(photo_marks).where(photo_marks.c.id == mark['id']).values(
            status='confirmada' if confirmed else 'rejeitada'))


def create_full_month_payment(engine, member_id, year, month, fee, paid_on=None):
    """Marca como pago sem duplicar montantes preexistentes nem sobrepagamentos."""
    year, month, fee = int(year), int(month), int(fee)
    if fee <= 0 or not 1 <= month <= 12:
        raise ValueError('Dados de pagamento inválidos')
    with engine.begin() as conn:
        past = conn.execute(select(payments.c.amount).where(
            (payments.c.member_id == int(member_id)) & (payments.c.year == year) &
            (payments.c.month == month))).scalars().all()
        remainder = max(0, fee - sum(past))
        if remainder:
            conn.execute(insert(payments).values(
                member_id=int(member_id), year=year, month=month, amount=remainder,
                paid_on=paid_on, origin='grelha_manual',
                note=('Regularização de marca histórica; dia exato não conhecido' if paid_on is None
                      else 'Mensalidade assinalada na grelha pelo financeiro'),
            ))
        conn.execute(update(photo_marks).where(
            (photo_marks.c.member_id == int(member_id)) & (photo_marks.c.year == year) &
            (photo_marks.c.month == month) & (photo_marks.c.status == 'pendente')
        ).values(status='confirmada'))
    return remainder


def update_payment(engine, payment_id, member_id, year, month, amount, paid_on, note):
    """Corrige um recebimento existente sem perder o identificador do lançamento."""
    if amount <= 0 or not 1 <= int(month) <= 12 or int(year) < 2020:
        raise ValueError('Confirma o valor, mês e ano')
    with engine.begin() as conn:
        row = conn.execute(select(payments).where(payments.c.id == int(payment_id))).first()
        if not row:
            raise ValueError('Pagamento não encontrado')
        conn.execute(update(payments).where(payments.c.id == int(payment_id)).values(
            member_id=int(member_id), year=int(year), month=int(month), amount=int(amount),
            paid_on=paid_on, note=note.strip(), origin='corrigido_pelo_financeiro',
        ))
        conn.execute(insert(audit_log).values(event='CORRIGIR_MENSALIDADE',
                    details=f'id={payment_id}; anterior={dict(row._mapping)}; novo={member_id}/{year}/{month}/{amount}/{paid_on}'[:500]))


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


# -------------------------- Aluguer do pavilhão --------------------------
def get_rent_plan(engine, year):
    with engine.connect() as conn:
        row = conn.execute(select(rent_plans).where(rent_plans.c.year == int(year))).mappings().first()
    return dict(row) if row else {'year': int(year), 'monthly_rent': 0, 'note': ''}


def set_rent_plan(engine, year, monthly_rent, note=''):
    if not 2020 <= int(year) <= 2100 or int(monthly_rent) < 0:
        raise ValueError('Ano ou montante de aluguer inválido')
    with engine.begin() as conn:
        old = conn.execute(select(rent_plans).where(rent_plans.c.year == int(year))).mappings().first()
        if old:
            conn.execute(update(rent_plans).where(rent_plans.c.year == int(year)).values(
                monthly_rent=int(monthly_rent), note=note.strip()))
        else:
            conn.execute(insert(rent_plans).values(year=int(year), monthly_rent=int(monthly_rent), note=note.strip()))
        conn.execute(insert(audit_log).values(event='ATUALIZAR_PLANO_ALUGUER',
                    details=f'ano={year}; anterior={dict(old) if old else None}; mensal={monthly_rent}'))


def add_rent_payment(engine, year, month, amount, paid_on, note=''):
    if not 1 <= int(month) <= 12 or not 2020 <= int(year) <= 2100 or int(amount) <= 0:
        raise ValueError('Confirma o mês, ano e montante do aluguer')
    if paid_on > date.today():
        raise ValueError('A data de pagamento não pode ser futura')
    with engine.begin() as conn:
        conn.execute(insert(rent_payments).values(year=int(year), month=int(month), amount=int(amount),
                      paid_on=paid_on, note=note.strip()))


def rent_grid(year, expected, rent_rows, today=None):
    today = today or date.today()
    rows = []
    for month in range(1, 13):
        paid = sum(int(r['amount']) for r in rent_rows
                   if int(r['year']) == int(year) and int(r['month']) == month)
        due = int(expected)
        future = date(int(year), month, 1) > today
        status = ('Não configurado' if due == 0 else '✓ Pago' if paid >= due
                  else '◐ Parcial' if paid else 'A vencer' if future else '· Por pagar')
        rows.append({'Mês': month, 'Previsto': due, 'Pago': paid,
                     'Em falta': max(due - paid, 0) if not future else 0,
                     'Estado': status})
    return rows


def set_member_month_status(engine, member_id, year, month, should_be_paid, fee,
                            paid_on=None, allow_undo=False):
    """Assinala/desfaz quota: nunca duplica; anulação exige confirmação no ecrã.

    Montante parcial não é apagado ao desmarcar sem autorização explícita.
    """
    member_id, year, month, fee = int(member_id), int(year), int(month), int(fee)
    if fee <= 0 or not 1 <= month <= 12:
        raise ValueError('Parâmetros de mensalidade inválidos')
    with engine.begin() as conn:
        current = conn.execute(select(payments).where((payments.c.member_id == member_id) &
            (payments.c.year == year) & (payments.c.month == month))).mappings().all()
        total = sum(int(r['amount']) for r in current)
        photo = conn.execute(select(photo_marks).where((photo_marks.c.member_id == member_id) &
            (photo_marks.c.year == year) & (photo_marks.c.month == month))).mappings().first()
        if should_be_paid:
            delta = max(fee - total, 0)
            if delta:
                conn.execute(insert(payments).values(member_id=member_id, year=year, month=month,
                    amount=delta, paid_on=paid_on, origin='validacao_financeiro',
                    note='Mensalidade confirmada pelo financeiro; dia histórico desconhecido' if paid_on is None
                    else 'Mensalidade marcada na grelha pelo financeiro'))
            if photo and photo['status'] == 'pendente':
                conn.execute(update(photo_marks).where(photo_marks.c.id == photo['id']).values(status='confirmada'))
            if delta:
                conn.execute(insert(audit_log).values(event='CONFIRMAR_MENSALIDADE',
                    details=f'membro={member_id}; {year}-{month:02d}; recebido={delta}; data={paid_on}'))
            return delta
        if total:
            if not allow_undo:
                raise ValueError('Para retirar um pagamento existente confirma a anulação na interface')
            conn.execute(delete(payments).where((payments.c.member_id == member_id) &
                (payments.c.year == year) & (payments.c.month == month)))
            conn.execute(insert(audit_log).values(event='ANULAR_MENSALIDADE',
                details=f'membro={member_id}; {year}-{month:02d}; lançamentos={[(r["id"],r["amount"]) for r in current]}'[:500]))
        if photo and photo['status'] != 'rejeitada':
            conn.execute(update(photo_marks).where(photo_marks.c.id == photo['id']).values(status='rejeitada'))
        return -total
