"""Amigos de Amigos | Gestão de mensalidades e contas do futsal.

Iniciar: streamlit run app.py
Variáveis/secrets: FINANCE_PASSWORD (obrigatória para editar), DATABASE_URL (opcional, PostgreSQL).
"""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    add_expense, add_income, add_member, add_payment, change_member, csv_export,
    delete_record, get_rows, get_year_settings, import_photo_payments, init_db,
    make_engine, members, payments, expenses, incomes, waivers, update_year,
    attendance, add_attendance, pay_attendance_fine, remove_attendance, session_times,
)
from finance import (
    EXPENSE_CATEGORIES, INCOME_CATEGORIES, MONTHS, MONTH_ABBR,
    is_expected, make_ledger, matrix_display, transaction_listing, xof, yearly_summary, arrival_outcome,
)

st.set_page_config(page_title='Amigos de Amigos · Futsal', page_icon='⚽', layout='wide', initial_sidebar_state='expanded')
PHOTO_PATH = Path(__file__).parent / 'assets' / 'amigos_de_amigos_grupo.jpg'

st.markdown('''
<style>
    .block-container {padding-top: 1.6rem; max-width: 1480px;}
    [data-testid="stSidebar"] {background: #10243a;}
    [data-testid="stSidebar"] * {color: #f2f6fa;}
    [data-testid="stSidebar"] input {color: #182e48 !important;}
    [data-testid="stMetric"] {padding: 1.1rem; background: #eff5f8; border: 1px solid #e0e7ed; border-radius: 12px;}
    [data-testid="stMetricLabel"] {font-size: .89rem;}
    [data-testid="stMetricValue"] {font-size: 1.6rem;}
    h1,h2,h3 {color: #16334b;}
    .hint {color:#677588; font-size:.93rem;}
    .pill {display:inline-block; color:#06483b; background:#e6f8ef; border-radius: 20px; padding: .25rem .65rem; font-size:.82rem; font-weight:600;}
    .club-subtitle {font-size:1.25rem;font-weight:600;color:#2a525e;}
    .club-schedule {border-left:4px solid #147d66; padding-left:1rem; margin-top:1.4rem;line-height:1.8;}
</style>
''', unsafe_allow_html=True)


def secret(key):
    try:
        return str(st.secrets.get(key, os.environ.get(key, '')))
    except (FileNotFoundError, KeyError):
        return str(os.environ.get(key, ''))


@st.cache_resource(show_spinner='A ligar à base de dados...')
def engine_for(url):
    eng = make_engine(url or None)
    init_db(eng)
    return eng


try:
    engine = engine_for(secret('DATABASE_URL'))
except Exception as ex:
    st.error('Não foi possível ligar à base de dados. Confirma a configuração DATABASE_URL.')
    st.code(str(ex))
    st.stop()


def load_data():
    return (get_rows(engine, members), get_rows(engine, payments),
            get_rows(engine, expenses), get_rows(engine, incomes), get_rows(engine, waivers),
            get_rows(engine, attendance))


def reload_ok(message):
    st.session_state['notice'] = message
    st.rerun()


if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))

member_rows, pay_rows, expense_rows, income_rows, waive_rows, training_rows = load_data()
today = date.today()
first_year = min([2026] + [int(m['start_year']) for m in member_rows] + [int(p['year']) for p in pay_rows]
                 + [r['expense_on'].year for r in expense_rows] + [r['received_on'].year for r in income_rows])
last_year = max([today.year + 1, 2026] + [int(p['year']) for p in pay_rows] +
                [r['session_on'].year for r in training_rows])

with st.sidebar:
    st.markdown('## ⚽ Amigos de Amigos')
    st.caption('Futsal · Pavilhão do INEFD')
    st.markdown('**Quartas 20h00 · Domingos 08h00**')
    st.divider()
    view_year = st.selectbox('Ano de consulta', list(range(last_year, first_year - 1, -1)),
                             index=max(0, last_year - max(today.year, first_year)), key='year_picker')
    st.caption('As contas acumuladas transitam automaticamente de um ano para o seguinte.')
    st.divider()
    st.markdown('#### 🔐 Acesso do financeiro')
    if st.session_state.auth:
        st.success('Sessão de gestão ativa')
        if st.button('Terminar sessão', use_container_width=True):
            st.session_state.auth = False
            st.rerun()
    else:
        if not secret('FINANCE_PASSWORD'):
            st.info('Consulta pública ativa. O responsável deve configurar FINANCE_PASSWORD para gerir.')
        else:
            with st.form('login_form'):
                password = st.text_input('Palavra-passe', type='password')
                login = st.form_submit_button('Entrar na gestão', use_container_width=True)
                if login:
                    if hmac.compare_digest(password.encode(), secret('FINANCE_PASSWORD').encode()):
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error('Palavra-passe incorreta')
    st.divider()
    st.caption('Transparência nas quotas, nas despesas e na utilização do dinheiro do grupo.')

cfg = get_year_settings(engine, view_year)
ledger = make_ledger(member_rows, pay_rows, waive_rows, cfg, view_year, today=today)
stats = yearly_summary(ledger, pay_rows, expense_rows, income_rows, view_year, training_rows)

head_text, head_photo = st.columns([1.05, 1.15], gap='large', vertical_alignment='center')
with head_text:
    st.title('⚽ Amigos de Amigos')
    st.markdown('<div class="club-subtitle">Mais do que futsal, uma amizade.</div>', unsafe_allow_html=True)
    st.markdown('<div class="club-schedule">'
                '📍 <b>Pavilhão do INEFD</b><br>'
                '⚽ <b>Quarta-feira</b> · 20h00 · tolerância até 20h15<br>'
                '⚽ <b>Domingo</b> · 08h00 · tolerância até 08h15<br>'
                f'💰 Mensalidade: <b>{xof(cfg["monthly_fee"])}</b> · Multa por atraso no treino: <b>{xof(cfg["late_fee"])}</b><br>'
                '⛔ Multa não paga no dia = sem autorização para treinar.'
                '</div>', unsafe_allow_html=True)
    st.markdown(f'<span class="pill">PAINEL DO GRUPO · {view_year}</span>', unsafe_allow_html=True)
with head_photo:
    if PHOTO_PATH.exists():
        st.image(str(PHOTO_PATH), use_container_width=True, caption='A nossa equipa · Amigos de Amigos')
    else:
        st.caption('Imagem do grupo não encontrada. Verifica a pasta assets.')

if not cfg['verified']:
    st.warning(f'**Contas de {view_year} ainda por conferir.** As marcas de pagamento nas fotografias de 2026 não foram importadas automaticamente. O financeiro deve confirmar os dados anteriores antes de validar os saldos.')

# Indicadores de caixa globais e anuais: saldo é caixa, dívida não conta como dinheiro recebido.
a, b, c, d, e = st.columns(5)
a.metric('Saldo acumulado em caixa', xof(stats['total_balance']))
b.metric(f'Receitas em {view_year}', xof(stats['receipts']))
c.metric(f'Despesas em {view_year}', xof(stats['costs']))
d.metric(f'Dívidas previstas em {view_year}', xof(stats['arrears']))
e.metric('Multas de treino pendentes', xof(stats['fine_debts']))
st.caption(f"Associados registados: {len(member_rows)} · Multas recebidas em {view_year}: {xof(stats['fine_income'])}")

public_tabs = st.tabs(['🏠 Visão geral', '📅 Mensalidades', '⏱️ Treinos e multas', '📒 Contas e movimentos', '📸 O nosso grupo'])

with public_tabs[0]:
    left, right = st.columns([1.6, 1])
    with left:
        st.subheader('Movimento financeiro mensal')
        chart = stats['chart'].set_index('Mês')
        st.bar_chart(chart[['Receitas', 'Despesas']], height=315, stack=False)
        st.caption('Receitas = mensalidades, multas efetivamente recebidas e outras receitas. Despesas = valores pagos pelo financeiro.')
    with right:
        st.subheader('Resumo de tesouraria')
        st.metric(f'Resultado de {view_year}', xof(stats['year_balance']))
        st.metric('Recebido em mensalidades', xof(stats['member_income']))
        st.metric('Multas recebidas', xof(stats['fine_income']))
        st.metric('Outras receitas do ano', xof(stats['other_income']))
        st.caption('O saldo acumulado é calculado a partir de TODOS os anos. Um pagamento antecipado conta como dinheiro recebido, não como dívida.')
    st.divider()
    now_month = today.month if view_year == today.year else (12 if view_year < today.year else 1)
    summary_month = st.selectbox('Estado por mês', range(1, 13), index=now_month - 1,
                                 format_func=lambda x: MONTHS[x - 1], key='summary_month')
    filtered = ledger[(ledger['mes'] == summary_month) & ledger['Aplicável']]
    if len(filtered):
        statuses = filtered['Estado'].value_counts()
        cols = st.columns(4)
        for col, label in zip(cols, ['Pago', 'Parcial', 'Por pagar', 'Adiantado']):
            col.metric(label, int(statuses.get(label, 0)))
        preview = filtered[['Nome', 'Estado', 'Pago', 'Em dívida']].copy()
        st.dataframe(preview, hide_index=True, use_container_width=True,
                     column_config={'Pago': st.column_config.NumberColumn('Pago (XOF)', format='%d'),
                                    'Em dívida': st.column_config.NumberColumn('Em dívida (XOF)', format='%d')})
    else:
        st.info('Ainda não existem mensalidades aplicáveis neste mês.')

with public_tabs[1]:
    st.subheader(f'Mensalidades de {view_year}')
    st.caption(f"Quota mensal: {xof(cfg['monthly_fee'])}. A multa de {xof(cfg['late_fee'])} aplica-se exclusivamente a chegadas tardias aos treinos, nunca à mensalidade.")
    search = st.text_input('Pesquisar membro', placeholder='Escreve parte do nome...', key='search_public')
    selection = st.radio('Visualização', ['Ano completo', 'Um mês'], horizontal=True)
    if selection == 'Um mês':
        which_month = st.selectbox('Mês', range(1, 13), index=max(0, (today.month - 1)),
                                   format_func=lambda m: MONTHS[m - 1], key='month_public')
    else:
        which_month = None
    df_status = matrix_display(ledger, which_month, search)
    st.dataframe(df_status, hide_index=True, use_container_width=True, height=490)
    st.caption('Pago = quota regularizada · Parcial = quota incompleta · Por pagar = quota ainda sem pagamento · Futuro = mês não iniciado · — = mês fora da participação no grupo.')
    st.caption('A falta de registo digital não prova falta de pagamento. Confirma os dados históricos com o financeiro.')
    st.divider()
    st.subheader('Consultar a situação individual')
    candidates = sorted(member_rows, key=lambda x: x['name'])
    if candidates:
        member_names = {m['id']: f"{m['name']} (#{m['id']})" for m in candidates}
        mid = st.selectbox('Membro', list(member_names), format_func=lambda v: member_names[v], key='public_member')
        person = ledger[ledger['id'] == mid]
        st.dataframe(person[['mes', 'Estado', 'Pago', 'Devido', 'Em dívida']]
                     .assign(mes=lambda d: d['mes'].apply(lambda m: MONTHS[m - 1]))
                     .rename(columns={'mes':'Mês'}), hide_index=True, use_container_width=True)

with public_tabs[3]:
    st.subheader('Como o dinheiro do grupo é utilizado')
    spend = [e for e in expense_rows if e['expense_on'].year == view_year]
    if spend:
        df_spend = pd.DataFrame(spend)
        grouped = df_spend.groupby('category', as_index=False)['amount'].sum().sort_values('amount', ascending=False)
        st.bar_chart(grouped.set_index('category')['amount'], horizontal=True, height=280)
        st.dataframe(df_spend[['expense_on', 'category', 'description', 'amount']]
                     .rename(columns={'expense_on': 'Data', 'category': 'Categoria',
                                      'description': 'Descrição', 'amount': 'Montante (XOF)'}),
                     hide_index=True, use_container_width=True)
    else:
        st.info('Ainda não foram registadas despesas neste ano.')
    st.divider()
    st.subheader('Movimentos financeiros')
    tx = transaction_listing(pay_rows, expense_rows, income_rows, member_rows, view_year, training_rows)
    if not tx.empty:
        tx_show = tx[['Data', 'Tipo', 'Nome / descrição', 'Detalhe', 'Entrada', 'Saída']].copy()
        st.dataframe(tx_show, hide_index=True, use_container_width=True, height=400)
        st.download_button('Descarregar movimentos (CSV)', tx_show.to_csv(index=False).encode('utf-8-sig'),
                           file_name=f'contas_amigos_{view_year}.csv', mime='text/csv')
    else:
        st.info('Sem movimentos financeiros registados neste ano.')

with public_tabs[2]:
    st.subheader(f'Treinos e multas · {view_year}')
    st.caption(f'Quarta: início 20h00, sem multa até 20h15 · Domingo: início 08h00, sem multa até 08h15. '
               f'Cada chegada posterior ao limite gera {xof(cfg["late_fee"])}, a pagar no próprio dia para poder treinar.')
    sessions = sorted({r['session_on'] for r in training_rows if r['session_on'].year == view_year}, reverse=True)
    if not sessions:
        st.info('Ainda não foram registadas presenças ou multas de treinos neste ano. '
                'A ausência de registo não significa falta ao treino.')
    else:
        chosen_session = st.selectbox('Consultar treino', sessions,
                                      format_func=lambda d: d.strftime('%d/%m/%Y (%A)'), key='pub_session')
        selected_train = [r for r in training_rows if r['session_on'] == chosen_session]
        names = {m['id']: m['name'] for m in member_rows}
        rows = [{'Membro': names.get(r['member_id'], '—'),
                 'Chegada': r['arrived_at'].strftime('%H:%M') if r['arrived_at'] else '—',
                 'Situação no treino': arrival_outcome(r),
                 'Multa (XOF)': r['fine_due'], 'Recebido (XOF)': r['fine_paid'],
                 'Por pagar (XOF)': r['fine_due'] - r['fine_paid']} for r in selected_train]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption('Apenas membros com registo aparecem na tabela. Não são atribuídas faltas automaticamente.')
    pending = [r for r in training_rows if r['session_on'].year == view_year and r['fine_due'] > r['fine_paid']]
    st.metric('Multas de treino por regularizar', xof(sum(r['fine_due'] - r['fine_paid'] for r in pending)))
    if pending:
        names = {m['id']: m['name'] for m in member_rows}
        st.dataframe(pd.DataFrame([{'Membro': names.get(r['member_id'], '—'), 'Treino': r['session_on'],
                                    'Em dívida (XOF)': r['fine_due'] - r['fine_paid']} for r in pending]),
                     hide_index=True, use_container_width=True)

with public_tabs[4]:
    st.subheader('A nossa equipa')
    if PHOTO_PATH.exists():
        st.image(str(PHOTO_PATH), use_container_width=True, caption='Amigos de Amigos · Pavilhão do INEFD')
    st.markdown('**Mais do que futsal, uma amizade.** Somos um grupo unido pelo desporto, pelo convívio e pelo compromisso de todos.')
    st.write('Os treinos realizam-se às quartas-feiras, às 20h00, e aos domingos, às 08h00, no Pavilhão do INEFD.')

if st.session_state.auth:
    st.divider()
    st.header('🔐 Área do financeiro')
    management = st.tabs(['💰 Mensalidades', '⏱️ Treinos e multas', '🧾 Despesas / receitas', '👥 Membros',
                          '🗂 Histórico 2026', '⚙️ Regras e exportação', '🛠 Corrigir movimentos'])

    with management[0]:
        st.subheader('Nova mensalidade')
        member_by_id = {m['id']: m for m in member_rows}
        if member_by_id:
            with st.form('new_payment', clear_on_submit=True):
                member_id = st.selectbox('Membro', list(sorted(member_by_id, key=lambda k: member_by_id[k]['name'])),
                                         format_func=lambda i: f"{member_by_id[i]['name']} (#{i})")
                c1,c2,c3 = st.columns(3)
                paid_year = c1.number_input('Ano da mensalidade', min_value=2020, max_value=2100, value=view_year, step=1)
                paid_month = c2.selectbox('Mês a que se refere', range(1,13), index=min(today.month-1,11),
                                          format_func=lambda x: MONTHS[x-1])
                amount = c3.number_input('Montante recebido (XOF)', min_value=1, step=500, value=int(cfg['monthly_fee']))
                payment_date = st.date_input('Data do recebimento', value=today, max_value=today)
                notes = st.text_input('Observações', placeholder='Ex.: quota de outubro; transferência bancária')
                if st.form_submit_button('Guardar recebimento', type='primary'):
                    if not is_expected(member_by_id[member_id], paid_year, paid_month):
                        st.error('Verifica a data de entrada do membro.')
                    else:
                        add_payment(engine, member_id, paid_year, paid_month, amount, payment_date, notes)
                        reload_ok('Pagamento registado. A situação do membro e a tesouraria foram atualizadas.')
        st.caption('Permite pagamentos parciais e antecipados. A mensalidade não tem multa de atraso. '
                   'As multas de chegada tardia são registadas no separador «Treinos e multas».')

    with management[1]:
        st.subheader('Registar presença e multa por atraso')
        st.caption('O estado é calculado automaticamente: depois de 20h15 à quarta ou 08h15 ao domingo '
                   'cobra-se a multa configurada para esse ano, por cada atraso. Se não pagar no dia, não está autorizado a treinar.')
        member_by_id = {m['id']: m for m in member_rows}
        if member_by_id:
            training_date = st.date_input('Data do treino', value=today, max_value=today, key='training_date')
            if training_date.weekday() not in (2, 6):
                st.warning('Escolhe uma quarta-feira ou um domingo para registar a presença.')
            with st.form('training_entry', clear_on_submit=False):
                c1, c2 = st.columns(2)
                member_id = c1.selectbox('Associado', list(sorted(member_by_id, key=lambda k: member_by_id[k]['name'])),
                                         format_func=lambda i: member_by_id[i]['name'], key='training_member')
                training_status = c2.selectbox('Comparência', ['Presente', 'Falta'])
                arrival_at = st.time_input('Hora de chegada (se presente)', value=time(8, 0) if training_date.weekday() == 6 else time(20, 0), step=60, key=f'arrival_{training_date}')
                paid_fine = st.checkbox('Multa recebida integralmente (caso se aplique)', value=False)
                payment_day = st.date_input('Data efetiva do recebimento', value=today, max_value=today)
                training_note = st.text_input('Observações do treino', placeholder='Ex.: atraso após o horário limite')
                if st.form_submit_button('Guardar registo do treino', type='primary'):
                    try:
                        _, limit = session_times(training_date)
                        is_late = training_status == 'Presente' and arrival_at > limit
                        if paid_fine and not is_late:
                            st.error('O associado não tem multa neste treino. Desmarca «Multa recebida».')
                        else:
                            due = add_attendance(
                                engine, member_id, training_date, training_status,
                                arrived_at if training_status == 'Presente' else None,
                                int(get_year_settings(engine, training_date.year)['late_fee']),
                                paid=paid_fine, paid_on=payment_day if paid_fine else None,
                                note=training_note,
                            )
                            if due:
                                outcome = 'multa recebida' if paid_fine and payment_day == training_date else (
                                    'multa liquidada fora do dia' if paid_fine else 'multa por cobrar; não treina')
                            else:
                                outcome = 'sem multa'
                            reload_ok(f'Registo guardado: {outcome}.')
                    except ValueError as exc:
                        st.error(str(exc))
        st.divider()
        st.subheader('Regularizar multas pendentes')
        pending = sorted([r for r in training_rows if r['fine_due'] > r['fine_paid']],
                         key=lambda r: r['session_on'], reverse=True)
        if not pending:
            st.success('Não há multas pendentes de pagamento.')
        else:
            with st.form('pay_training_fine'):
                pending_map = {r['id']: r for r in pending}
                rid = st.selectbox('Multa a liquidar', list(pending_map), format_func=lambda i:
                                   f"{member_by_id[pending_map[i]['member_id']]['name']} · "
                                   f"{pending_map[i]['session_on'].strftime('%d/%m/%Y')} · "
                                   f"{xof(pending_map[i]['fine_due'] - pending_map[i]['fine_paid'])}")
                received_at = st.date_input('Quando foi efetivamente recebida a multa?', value=today, max_value=today,
                                            key='fine_payment_date')
                if st.form_submit_button('Confirmar recebimento', type='primary'):
                    try:
                        pay_attendance_fine(engine, rid, received_at)
                        reload_ok('Multa paga e recebimento incluído nas contas do grupo.')
                    except ValueError as exc:
                        st.error(str(exc))
        st.divider()
        st.subheader('Corrigir presença registada por engano')
        st.caption('Só é possível apagar presenças sem multa recebida. Assim, um recebimento não desaparece das contas.')
        if training_rows:
            recent_entries = sorted(training_rows, key=lambda r: (r['session_on'], r['id']), reverse=True)[:300]
            recent_map = {r['id']: r for r in recent_entries}
            rid_bad = st.selectbox('Registo a corrigir', list(recent_map), format_func=lambda i:
                                   f"{recent_map[i]['session_on'].strftime('%d/%m/%Y')} · "
                                   f"{member_by_id.get(recent_map[i]['member_id'], {}).get('name', '—')} · "
                                   f"{arrival_outcome(recent_map[i])}", key='training_correct')
            if st.checkbox('Confirmo que este registo de treino está errado', key='confirm_del_training'):
                if st.button('Eliminar registo de presença incorreto'):
                    try:
                        remove_attendance(engine, rid_bad)
                        reload_ok('Registo corrigido. Podes voltar a introduzir a presença.')
                    except ValueError as exc:
                        st.error(str(exc))

    with management[2]:
        expense_col, income_col = st.columns(2)
        with expense_col:
            st.subheader('Nova despesa')
            with st.form('new_expense', clear_on_submit=True):
                expense_day = st.date_input('Data da despesa', value=today, max_value=today)
                category = st.selectbox('Categoria', EXPENSE_CATEGORIES)
                what = st.text_input('Descrição / fornecedor', placeholder='Ex.: aluguer INEFD, mês de outubro')
                expense_amount = st.number_input('Valor pago (XOF)', min_value=1, step=500, value=3500)
                if st.form_submit_button('Guardar despesa', type='primary'):
                    add_expense(engine, expense_day, category, what, expense_amount)
                    reload_ok('Despesa registada e saldo atualizado.')
        with income_col:
            st.subheader('Outra receita')
            with st.form('new_income', clear_on_submit=True):
                income_day = st.date_input('Data do recebimento extra', value=today, max_value=today)
                inc_category = st.selectbox('Tipo de receita', INCOME_CATEGORIES)
                inc_desc = st.text_input('Origem / observação', placeholder='Ex.: contribuição de um patrocinador')
                inc_amount = st.number_input('Montante da receita (XOF)', min_value=1, step=500, value=3500)
                if st.form_submit_button('Guardar outra receita', type='primary'):
                    add_income(engine, income_day, inc_category, inc_desc, inc_amount)
                    reload_ok('Receita extraordinária registada.')
        st.info('Para começar com dinheiro que já existe na caixa, regista-o como **Outra receita → Saldo inicial**, apenas uma vez. Nos anos seguintes o saldo transita automaticamente.')

    with management[3]:
        st.subheader('Associados')
        st.dataframe(pd.DataFrame(member_rows).rename(columns={
            'id': 'N.º', 'name':'Nome', 'start_year':'Ano entrada', 'start_month':'Mês entrada',
            'end_year':'Ano saída', 'end_month':'Mês saída', 'needs_review':'Nome por conferir'
        }), hide_index=True, use_container_width=True)
        left,right = st.columns(2)
        with left:
            st.markdown('**Adicionar membro**')
            with st.form('add_member', clear_on_submit=True):
                new_name = st.text_input('Nome')
                new_y = st.number_input('Ano de entrada', min_value=2020, max_value=2100, value=today.year)
                new_m = st.selectbox('Mês de entrada', range(1,13), index=today.month-1, format_func=lambda i: MONTHS[i-1])
                if st.form_submit_button('Adicionar'):
                    try:
                        add_member(engine, new_name, new_y, new_m)
                        reload_ok('Membro adicionado.')
                    except ValueError as exc:
                        st.error(str(exc))
        with right:
            st.markdown('**Corrigir nome, entrada ou saída**')
            edit_id = st.selectbox('Selecionar membro', list(sorted(member_by_id)),
                                   format_func=lambda i: f"{member_by_id[i]['name']} (#{i})", key='edit_member')
            selected = member_by_id[edit_id]
            with st.form(f'edit_m_{edit_id}'):
                edit_name = st.text_input('Nome oficial', value=selected['name'])
                b1,b2 = st.columns(2)
                from_y = b1.number_input('Ano entrada', min_value=2020,max_value=2100, value=int(selected['start_year']))
                from_m = b2.selectbox('Mês entrada', range(1,13), index=int(selected['start_month'])-1,
                                      format_func=lambda i: MONTHS[i-1])
                is_left = st.checkbox('O membro deixou o grupo', value=selected['end_year'] is not None)
                stop_y, stop_m = None, None
                if is_left:
                    c1,c2 = st.columns(2)
                    stop_y = c1.number_input('Ano de saída', min_value=2020, max_value=2100,
                                              value=int(selected['end_year'] or today.year))
                    stop_m = c2.selectbox('Mês de saída', range(1,13),
                                          index=int(selected['end_month'] or today.month)-1,
                                          format_func=lambda i: MONTHS[i-1])
                needs_review = st.checkbox('Grafia ainda por confirmar', value=bool(selected['needs_review']))
                if st.form_submit_button('Guardar alterações'):
                    try:
                        change_member(engine, edit_id, edit_name, from_y, from_m, stop_y, stop_m, needs_review)
                        reload_ok('Ficha do membro atualizada.')
                    except ValueError as exc:
                        st.error(str(exc))
        st.caption('A data de entrada/saída determina quais os meses com mensalidade devida. Os pagamentos antigos permanecem guardados.')

    with management[4]:
        st.subheader('Fotografias do registo de 2026')
        st.warning('Esta transcrição é uma **proposta**. Nem todas as grafias e cruzes são nítidas. Nenhum X significa falta de pagamento comprovada, e as datas dos pagamentos assinalados não são conhecidas.')
        example_path = Path(__file__).parent / 'historico_foto_2026_para_validar.csv'
        if example_path.exists():
            st.download_button('Descarregar proposta de transcrição (CSV)', example_path.read_bytes(),
                               file_name=example_path.name, mime='text/csv')
        uploaded = st.file_uploader('Carregar CSV da proposta ou ficheiro corrigido', type=['csv'], key='historical_upload')
        if uploaded is not None:
            try:
                candidate = pd.read_csv(uploaded, encoding='utf-8-sig', sep=None, engine='python').fillna('')
                must_have = {'nome','mes','valor'}
                if not must_have.issubset(candidate.columns):
                    st.error('O CSV deve conter as colunas nome, mes e valor.')
                else:
                    candidate.insert(0, 'importar', True)
                    st.caption('Podes desmarcar as linhas que não conseguiste verificar. A operação ignora duplicados anteriormente importados da fotografia.')
                    edited = st.data_editor(candidate, hide_index=True, use_container_width=True, num_rows='fixed', height=400,
                                            column_config={'importar': st.column_config.CheckboxColumn('Confirmado?'),
                                                           'nome': st.column_config.TextColumn('Nome'),
                                                           'mes': st.column_config.NumberColumn('Mês'),
                                                           'valor': st.column_config.NumberColumn('XOF')})
                    approve = st.checkbox('Conferi as marcas com os registos originais; autorizo que os selecionados entrem nas contas.', key='confirm_hist')
                    if st.button('Importar pagamentos selecionados de 2026', type='primary', disabled=not approve):
                        chosen = edited[edited['importar']].to_dict('records')
                        added, skipped = import_photo_payments(engine, chosen, year=2026)
                        reload_ok(f'Fotografia: {added} pagamentos importados, {skipped} ignorados/duplicados. Confirma também os nomes e as mensalidades em falta.')
            except Exception as exc:
                st.error(f'Não foi possível interpretar o CSV: {exc}')
        st.info('Os pagamentos importados têm **data desconhecida**. As mensalidades não geram multa. As multas de treino só podem surgir de chegadas tardias registadas individualmente.')

    with management[5]:
        st.subheader(f'Regras para {view_year}')
        with st.form('year_cfg'):
            c1,c2 = st.columns(2)
            q = c1.number_input('Mensalidade mensal (XOF)', min_value=1, value=int(cfg['monthly_fee']), step=500)
            f = c2.number_input('Multa por chegada tardia a cada treino (XOF)', min_value=0, value=int(cfg['late_fee']), step=100)
            verified = st.checkbox('Conferi o histórico deste ano e autorizo publicar as contas como verificadas',
                                   value=bool(cfg['verified']))
            if st.form_submit_button('Guardar regras do ano', type='primary'):
                update_year(engine, view_year, q, f, cfg['due_day'], verified)
                reload_ok(f'Regras financeiras de {view_year} guardadas.')
        st.warning('Alterar a mensalidade recalcula as quotas em dívida do ano escolhido. A multa por atraso só afeta novos registos de treino; os já registados mantêm o valor histórico.')
        st.subheader('Exportação / cópia dos dados')
        for typ in ['membros','pagamentos','despesas','outras_receitas','treinos_multas']:
            st.download_button(f'Descarregar {typ.replace("_", " ")} (CSV)', csv_export(engine, typ),
                               file_name=f'{typ}_amigos.csv', mime='text/csv', key=f'csv_{typ}')
        st.caption('Estes ficheiros são cópias dos dados; é aconselhável descarregá-los periodicamente.')
        st.caption('Se a aplicação estiver no Streamlit Community Cloud, usa PostgreSQL externo (DATABASE_URL). Uma base SQLite local poderá ser perdida numa reinicialização/reinstalação.')

    with management[6]:
        st.subheader('Eliminar lançamentos errados')
        st.warning('Uma eliminação é definitiva. Para corrigir um montante, elimina o lançamento errado e regista-o novamente.')
        movements = transaction_listing(pay_rows, expense_rows, income_rows, member_rows, attendance_rows=training_rows)
        if movements.empty:
            st.info('Não existem movimentos para corrigir.')
        else:
            choices = movements.to_dict('records')
            idx = st.selectbox('Escolher movimento', list(range(len(choices))),
                               format_func=lambda i: (f"{choices[i]['Tipo']} · #{choices[i]['ID']} · "
                                                      f"{choices[i]['Nome / descrição']} · "
                                                      f"{xof(choices[i]['Entrada'] or choices[i]['Saída'])}"))
            chosen = choices[idx]
            if chosen['classe'] == 'multa':
                st.info('As multas recebidas pertencem ao registo de treino e não podem ser apagadas neste ecrã. A correção exige reconciliação contabilística.')
            st.write({'Tipo': chosen['Tipo'], 'Data': chosen['Data'], 'Descrição': chosen['Detalhe'],
                      'Entrada': xof(chosen['Entrada']), 'Saída': xof(chosen['Saída'])})
            if st.checkbox('Confirmo que este lançamento foi registado incorretamente', key=f'del_{chosen["classe"]}_{chosen["ID"]}'):
                if st.button('Eliminar este lançamento', type='primary', disabled=chosen['classe'] == 'multa'):
                    delete_record(engine, chosen['classe'], chosen['ID'])
                    reload_ok('Lançamento eliminado. O saldo foi recalculado.')

st.markdown('---')
st.caption('Amigos de Amigos · Contas transparentes para todos os membros · Gestão restrita ao responsável financeiro')
