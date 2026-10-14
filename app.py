"""Amigos de Amigos | Gestão de mensalidades e contas do futsal.

Iniciar: streamlit run app.py
Variáveis/secrets: FINANCE_PASSWORD (obrigatória para editar), DATABASE_URL (opcional, PostgreSQL).
"""
from __future__ import annotations

import hmac
import os
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Proteção contra a publicação de ficheiros de versões diferentes no GitHub.
# Esta verificação ocorre antes das importações das funções específicas.
try:
    import database as _db_module
    import finance as _finance_module
except ImportError:
    st.error('Não foi possível carregar os módulos da aplicação. Confirma os ficheiros e requirements.txt no GitHub.')
    st.stop()

if (getattr(_db_module, 'APP_COMPAT_VERSION', None) != '4.2'
        or getattr(_finance_module, 'APP_COMPAT_VERSION', None) != '4.2'):
    st.error('Ficheiros de versões diferentes detetados: atualiza app.py, database.py e finance.py em conjunto no mesmo repositório.')
    st.info('Não apagues a base de dados nem os registos de pagamentos. Substitui apenas o código e reinicia a aplicação.')
    st.stop()

from database import (
    add_expense, add_income, add_member, add_payment, change_member, csv_export,
    delete_record, get_rows, get_year_settings, import_photo_payments, init_db, DatabaseSchemaError,
    make_engine, members, payments, expenses, incomes, waivers, update_year,
    attendance, add_attendance, pay_attendance_fine, remove_attendance, session_times,
    photo_marks, resolve_photo_mark, set_member_month_status, update_payment,
    rent_payments, rent_plans, audit_log, rent_grid, get_rent_plan, set_rent_plan,
    add_rent_payment,
)
from finance import (
    EXPENSE_CATEGORIES, INCOME_CATEGORIES, MONTHS, MONTH_ABBR,
    is_expected, make_ledger, matrix_display, transaction_listing, xof, yearly_summary, arrival_outcome, monthly_breakdown,
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
    div[data-testid="stTabs"] button[data-baseweb="tab"] {font-size:1rem;font-weight:750; padding: .75rem .85rem; border-radius:10px 10px 0 0;}
    div[data-testid="stTabs"] button[aria-selected="true"] {background:#126c61; color:#fff;}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {gap:.2rem;}
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
except DatabaseSchemaError as ex:
    logging.exception('Falha de compatibilidade da base de dados')
    st.error('A estrutura da base de dados tem colunas essenciais incompatíveis com esta versão.')
    st.info(str(ex))
    st.info('Os dados não foram apagados. Solicita a correção da estrutura antes de continuar.')
    st.stop()
except Exception:
    logging.exception('Falha de ligação ou inicialização da base de dados')
    st.error('Não foi possível abrir ou atualizar a base de dados. Verifica os logs do Streamlit Cloud.')
    st.caption('Se a aplicação estiver online, confirma DATABASE_URL nos Secrets e a disponibilidade do serviço PostgreSQL.')
    st.stop()


def load_data():
    tables = (members, payments, expenses, incomes, waivers, attendance, photo_marks, rent_payments)
    result = []
    for table in tables:
        try:
            result.append(get_rows(engine, table))
        except Exception:
            logging.exception('Falha na consulta da tabela: %s', table.name)
            st.error(f'Erro ao consultar os registos de «{table.name}».')
            st.info('A consulta falhou, mas nenhum pagamento foi apagado. '
                    'Abre Manage app → Logs e consulta a última exceção completa.')
            st.stop()
    return tuple(result)


def reload_ok(message):
    st.session_state['notice'] = message
    st.rerun()


if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))

member_rows, pay_rows, expense_rows, income_rows, waive_rows, training_rows, photo_rows, rent_rows = load_data()
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
    st.markdown('#### 🔐 Conta do financeiro')
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
                username = st.text_input('Utilizador', value='financeiro')
                password = st.text_input('Código de acesso', type='password')
                login = st.form_submit_button('Entrar na gestão', use_container_width=True)
                if login:
                    if (hmac.compare_digest(username.strip().encode(), (secret('FINANCE_USERNAME') or 'financeiro').encode())
                            and hmac.compare_digest(password.encode(), secret('FINANCE_PASSWORD').encode())):
                        st.session_state.auth = True
                        st.rerun()
                    else:
                        st.error('Palavra-passe incorreta')
    st.divider()
    st.caption('Transparência nas quotas, nas despesas e na utilização do dinheiro do grupo.')

cfg = get_year_settings(engine, view_year)
ledger = make_ledger(member_rows, pay_rows, waive_rows, cfg, view_year, today=today, photo_rows=photo_rows)
stats = yearly_summary(ledger, pay_rows, expense_rows, income_rows, view_year, training_rows, rent_rows)
rent_cfg = get_rent_plan(engine, view_year)
rent_months = rent_grid(view_year, rent_cfg['monthly_rent'], rent_rows, today=today)
monthly = monthly_breakdown(pay_rows, expense_rows, income_rows, training_rows, rent_rows, view_year)

head_text, head_photo = st.columns([1.05, 1.15], gap='large', vertical_alignment='center')
with head_text:
    st.title('⚽ Amigos de Amigos')
    st.markdown('<div class="club-subtitle">Mais do que futsal, uma amizade.</div>', unsafe_allow_html=True)
    st.caption('Presidente: Deoclecio Jayrson Ferreira Marinho')
    st.markdown('<div class="club-schedule">'
                '📍 <b>Pavilhão do INEFD</b><br>'
                '⚽ <b>Quarta-feira</b> · 20h00 · tolerância até 20h15<br>'
                '⚽ <b>Domingo</b> · 08h00 · tolerância até 08h15<br>'
                f'💰 Mensalidade: <b>{xof(cfg["monthly_fee"])}</b> · Multa por atraso no treino: <b>{xof(cfg["late_fee"])}</b><br>'
                '⛔ Multa não paga no dia = sem autorização para treinar.'
                '</div>', unsafe_allow_html=True)
    st.markdown(f'<span class="pill">PAINEL FINANCEIRO · {view_year}</span>', unsafe_allow_html=True)
with head_photo:
    if PHOTO_PATH.exists():
        st.image(str(PHOTO_PATH), use_container_width=True, caption='Fotografia do nosso grupo · Amigos de Amigos')
    else:
        st.caption('Imagem do grupo não encontrada. Verifica a pasta assets.')

if not cfg['verified']:
    st.warning(f'**Histórico de {view_year} ainda por confirmar.** As marcas identificadas na fotografia de 2026 aparecem como ✓? e não entram no saldo até o financeiro confirmar o recebimento.')

# Indicadores de caixa globais e anuais: saldo é caixa, dívida não conta como dinheiro recebido.
a, b, c, d, e = st.columns(5)
a.metric('Saldo acumulado em caixa', xof(stats['total_balance']))
b.metric(f'Receitas em {view_year}', xof(stats['receipts']))
c.metric(f'Despesas em {view_year}', xof(stats['costs']))
d.metric(f'Dívidas previstas em {view_year}', xof(stats['arrears']))
e.metric('Multas de treino pendentes', xof(stats['fine_debts']))
st.caption(f"Associados registados: {len(member_rows)} · Multas recebidas em {view_year}: {xof(stats['fine_income'])}")

public_tabs = st.tabs(['🏠 VISÃO GERAL', '✅ MENSALIDADES', '⏱️ TREINOS E MULTAS', '💵 FINANÇAS', '📸 O GRUPO', '🏟️ ALUGUER DO CAMPO'])

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
        st.metric('Aluguer efetivamente pago', xof(stats['rent_cost']))
        st.caption('O saldo acumulado é calculado a partir de TODOS os anos. Os pagamentos históricos por confirmar não contam como receita.')
    st.subheader('Entradas e saídas por mês (XOF)')
    st.dataframe(monthly, use_container_width=True, hide_index=True, height=450)
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
    st.caption('**✓** pago e confirmado · **✓?** marca na folha de 2026 por confirmar · **◐** parcial · **·** sem pagamento confirmado · **—** não aplicável / mês futuro. As marcas ✓? não entram nas receitas nem no saldo.')
    st.caption('Uma célula sem ✓ não prova que a quota ficou por pagar. O financeiro deve completar o registo histórico antes de confirmar as contas.')
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
    st.metric('Aluguer do campo pago no ano', xof(stats['rent_cost']))
    st.metric('Outras despesas pagas no ano', xof(stats['other_cost']))
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
    if spend:
        st.subheader('Despesas por categoria e mês (XOF)')
        detail = pd.DataFrame(spend)
        detail['Mês'] = detail['expense_on'].map(lambda dt: MONTH_ABBR[dt.month-1])
        detail_matrix = detail.pivot_table(index='category', columns='Mês', values='amount',
                                          aggfunc='sum', fill_value=0).reindex(columns=MONTH_ABBR, fill_value=0)
        detail_matrix.loc['Aluguer do pavilhão'] = [sum(int(r['amount']) for r in rent_rows
                     if r['paid_on'].year == view_year and r['paid_on'].month == mon)
                     for mon in range(1,13)]
        st.dataframe(detail_matrix, use_container_width=True)
    elif rent_rows:
        st.subheader('Despesas com aluguer do campo')
        st.dataframe(monthly[['Mês','Aluguer pago']], hide_index=True, use_container_width=True)
    st.divider()
    st.subheader('Movimentos financeiros')
    tx = transaction_listing(pay_rows, expense_rows, income_rows, member_rows, view_year, training_rows, rent_rows)
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
    st.write('**Presidente:** Deoclecio Jayrson Ferreira Marinho')

with public_tabs[5]:
    st.subheader(f'🏟️ Aluguer do pavilhão · {view_year}')
    if not rent_cfg['monthly_rent']:
        st.info('O valor mensal do aluguer ainda não foi configurado. O financeiro deve introduzi-lo na área de gestão do campo.')
    else:
        st.caption(f"Custo previsto: {xof(rent_cfg['monthly_rent'])} / mês; o estado de cada mês é atualizado pelo financeiro.")
    rent_df = pd.DataFrame(rent_months)
    rent_df['Mês'] = rent_df['Mês'].map(lambda n: MONTHS[n-1])
    st.dataframe(rent_df.rename(columns={'Previsto':'Previsto (XOF)', 'Pago':'Pago (XOF)', 'Em falta':'Em falta (XOF)'}),
                 hide_index=True, use_container_width=True)
    due_months = [r for r in rent_months if r['Em falta'] > 0]
    r1, r2, r3 = st.columns(3)
    r1.metric('Total pago ao pavilhão', xof(sum(r['Pago'] for r in rent_months)))
    r2.metric('Meses totalmente pagos', sum(1 for r in rent_months if r['Estado'] == '✓ Pago'))
    r3.metric('Aluguer em falta (meses vencidos)', xof(sum(r['Em falta'] for r in due_months)))
    st.caption('Este quadro organiza o aluguer pelo mês a que respeita. O gráfico das finanças utiliza a data efetiva do pagamento.')
    old_rents = [e for e in expense_rows if e['category'] == 'Aluguer do pavilhão' and e['expense_on'].year == view_year]
    if old_rents:
        st.warning(f'Existem {len(old_rents)} despesa(s) antigas de aluguer sem mês de referência. Já contam nas despesas gerais, mas não neste quadro mensal. O financeiro deve conferir antes de as relançar, para não duplicar o custo.')

if st.session_state.auth:
    st.divider()
    st.header('🔐 Área do financeiro')
    management = st.tabs(['✅ Gerir mensalidades', '⏱️ Treinos e multas', '🧾 Despesas / receitas', '👥 Membros',
                          '🗂 Histórico 2026', '⚙️ Regras e exportação', '🛠 Corrigir movimentos', '🏟️ Aluguer do campo'])

    with management[0]:
        st.subheader('Atualizar a grelha de mensalidades dos associados')
        st.caption('Seleciona o membro, marca os meses com quota efetivamente recebida e guarda. '
                   'As marcas da fotografia (✓?) só viram receita quando confirmadas. Para desfazer um pagamento, '
                   'é necessário autorizar a anulação; a operação fica no histórico de alterações.')
        if member_rows:
            options = {m['id']: m for m in sorted(member_rows, key=lambda x: x['name'])}
            chosen_member = st.selectbox('Membro a atualizar', list(options),
                                          format_func=lambda x: options[x]['name'], key='grid_member')
            member_history = ledger[ledger['id'] == chosen_member].sort_values('mes')
            st.dataframe(member_history[['mes','Estado','Pago','Por confirmar','Em dívida']]
                         .assign(mes=lambda f: f['mes'].map(lambda m: MONTHS[m-1]))
                         .rename(columns={'mes':'Mês', 'Pago':'Recebido (XOF)',
                                          'Por confirmar':'Fotografia (XOF)', 'Em dívida':'Em falta (XOF)'}),
                         hide_index=True, use_container_width=True)
            with st.form(f'payment_grid_{view_year}_{chosen_member}'):
                st.markdown('**Meses com mensalidade confirmada:**')
                marks = {}
                for start in range(0, 12, 4):
                    cbs = st.columns(4)
                    for j, col in enumerate(cbs):
                        month = start+j+1
                        rec = member_history[member_history['mes'] == month].iloc[0]
                        with col:
                            marks[month] = st.checkbox(MONTH_ABBR[month-1] + (' (✓?)' if rec['Sinal']=='✓?' else ''),
                                                       value=bool(rec['Pago'] >= rec['Devido'] and rec['Devido']>0),
                                                       disabled=not bool(rec['Aplicável']), key=f'mrk_{view_year}_{chosen_member}_{month}')
                historical_unknown = st.checkbox('Data exata dos recebimentos antigos desconhecida', value=view_year==2026)
                actual_day = None
                if not historical_unknown:
                    actual_day = st.date_input('Data real de pagamento dos meses a marcar', value=today, max_value=today,
                                               key=f'dt_grid_{view_year}_{chosen_member}')
                undo_authorized = st.checkbox('Autorizo retirar quotas já recebidas que desmarquei (altera o saldo de caixa)', value=False)
                if st.form_submit_button('Guardar os 12 meses deste membro', type='primary'):
                    actions = []
                    for rec in member_history.to_dict('records'):
                        m = int(rec['mes'])
                        if not rec['Aplicável']:
                            continue
                        was_confirmed = rec['Pago'] >= rec['Devido'] and rec['Devido']>0
                        if marks[m] and not was_confirmed:
                            actions.append((m, True))
                        elif not marks[m] and rec['Pago'] >= rec['Devido'] and rec['Devido'] > 0:
                            actions.append((m, False))
                    if any(not is_paid for _, is_paid in actions) and not undo_authorized:
                        st.error('Há mensalidades a anular. Marca a confirmação de anulação ou volta a selecionar os meses.')
                    else:
                        try:
                            count, amounts = 0, 0
                            for m, yes in actions:
                                amounts += set_member_month_status(engine, chosen_member, view_year, m, yes,
                                          int(cfg['monthly_fee']), actual_day, allow_undo=undo_authorized)
                                count += 1
                            reload_ok(f'Grelha atualizada: {count} meses corrigidos; variação no saldo: {xof(amounts)}.')
                        except ValueError as exc:
                            st.error(str(exc))
        st.divider()
        st.subheader('Registar pagamentos parciais ou montantes específicos')
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
        st.divider()
        st.subheader('Editar um recebimento já registado')
        if pay_rows:
            p_map = {p['id']:p for p in pay_rows}
            p_edit_id = st.selectbox('Escolher o recebimento', list(reversed(sorted(p_map))),
                format_func=lambda n: f"#{n} · {options.get(p_map[n]['member_id'], {}).get('name', '—')} · " +
                f"{MONTHS[p_map[n]['month']-1]}/{p_map[n]['year']} · {xof(p_map[n]['amount'])}", key='edit_payment_id')
            record = p_map[p_edit_id]
            with st.form(f'edit_payment_{p_edit_id}'):
                cols = st.columns(3)
                emember = cols[0].selectbox('Membro', list(options), index=list(options).index(record['member_id']),
                                            format_func=lambda i: options[i]['name'])
                eyear = cols[1].number_input('Ano de referência', min_value=2020,max_value=2100,
                                              value=int(record['year']))
                emonth = cols[2].selectbox('Mês de referência', range(1,13), index=int(record['month'])-1,
                                           format_func=lambda i: MONTHS[i-1])
                ev = st.number_input('Montante efetivo (XOF)', min_value=1, step=500, value=int(record['amount']))
                date_not_known = st.checkbox('Data de recebimento desconhecida (histórico)',
                                              value=record['paid_on'] is None)
                ereceived = None if date_not_known else st.date_input('Data real de recebimento',
                    value=record['paid_on'] or today, max_value=today)
                enote = st.text_input('Observação', value=record['note'] or '')
                if st.form_submit_button('Guardar correção do pagamento', type='primary'):
                    try:
                        update_payment(engine, p_edit_id, emember, eyear, emonth, ev, ereceived, enote)
                        reload_ok('Lançamento corrigido. Mensalidades e saldos recalculados.')
                    except ValueError as exc:
                        st.error(str(exc))
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
                category = st.selectbox('Categoria (aluguer tem separador próprio)',
                                        [c for c in EXPENSE_CATEGORIES if c != 'Aluguer do pavilhão'])
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
        pending_marks = [r for r in photo_rows if r['year'] == 2026 and r['status'] == 'pendente']
        st.subheader(f'Marcas fotografadas por confirmar: {len(pending_marks)}')
        if pending_marks:
            with st.form('approve_photo_marks'):
                names = {m['id']:m['name'] for m in member_rows}
                candidates = pd.DataFrame([{'Confirmar': False, 'ID': x['id'], 'Associado': names.get(x['member_id'], '—'),
                                             'Mês': MONTHS[x['month']-1], 'Valor (XOF)': x['amount']}
                                            for x in sorted(pending_marks, key=lambda r:(names.get(r['member_id'],''), r['month']))])
                reviewed = st.data_editor(candidates, hide_index=True, use_container_width=True,
                                          disabled=['ID','Associado','Mês','Valor (XOF)'],
                                          column_config={'Confirmar':st.column_config.CheckboxColumn('Conferido?')})
                confirmed_photo = st.checkbox('Conferi os registos selecionados e confirmo que estes pagamentos foram recebidos.')
                if st.form_submit_button('Confirmar mensalidades selecionadas', type='primary'):
                    picked = reviewed[reviewed['Confirmar']]
                    if not confirmed_photo or picked.empty:
                        st.error('Seleciona os pagamentos e confirma a conferência.')
                    else:
                        for mark_id in picked['ID']:
                            entry = next(p for p in pending_marks if p['id']==mark_id)
                            resolve_photo_mark(engine, entry['member_id'], 2026, entry['month'], True)
                        reload_ok(f'{len(picked)} mensalidades conferidas; recebimentos integrados na tesouraria.')
        if pending_marks:
            st.markdown('**Rejeitar uma marca errada da fotografia**')
            reject_map = {r['id']:r for r in pending_marks}
            to_reject = st.selectbox('Marca a rejeitar', list(reject_map),
                format_func=lambda k: f"{names.get(reject_map[k]['member_id'], '—')} · {MONTHS[reject_map[k]['month']-1]}", key='reject_photo')
            check_reject = st.checkbox('Confirmei que esta marca não representa uma mensalidade paga', key='check_reject')
            if st.button('Rejeitar apenas esta marca', disabled=not check_reject):
                r = reject_map[to_reject]
                resolve_photo_mark(engine, r['member_id'], 2026, r['month'], False)
                reload_ok('Marca rejeitada; permanece no histórico sem afetar o saldo de caixa.')
        st.info('As marcas ✓? estão disponíveis na grelha pública, mas NÃO são ainda dinheiro registado. O financeiro confirma as corretas ou rejeita individualmente as erradas.')

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
        for typ in ['membros','pagamentos','despesas','outras_receitas','treinos_multas','marcas_foto','aluguer','plano_aluguer','auditoria']:
            st.download_button(f'Descarregar {typ.replace("_", " ")} (CSV)', csv_export(engine, typ),
                               file_name=f'{typ}_amigos.csv', mime='text/csv', key=f'csv_{typ}')
        st.caption('Estes ficheiros são cópias dos dados; é aconselhável descarregá-los periodicamente.')
        st.caption('Se a aplicação estiver no Streamlit Community Cloud, usa PostgreSQL externo (DATABASE_URL). Uma base SQLite local poderá ser perdida numa reinicialização/reinstalação.')

    with management[6]:
        st.subheader('Eliminar lançamentos errados')
        st.warning('Uma eliminação é definitiva. Para corrigir um montante, elimina o lançamento errado e regista-o novamente.')
        movements = transaction_listing(pay_rows, expense_rows, income_rows, member_rows, attendance_rows=training_rows, rent_rows=rent_rows)
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

    with management[7]:
        st.subheader(f'🏟️ Mensalidade do pavilhão · {view_year}')
        st.caption('Este painel é separado das despesas de equipamentos, para poderes controlar quais os meses de campo que já foram pagos.')
        with st.form('rent_settings'):
            rent_amount = st.number_input('Valor previsto de aluguer por mês (XOF)', min_value=0, step=500,
                                           value=int(rent_cfg['monthly_rent']))
            rent_note = st.text_input('Notas do contrato / responsável do pavilhão', value=rent_cfg.get('note',''))
            if st.form_submit_button('Guardar mensalidade do espaço'):
                set_rent_plan(engine, view_year, rent_amount, rent_note)
                reload_ok('Valor do aluguer mensal configurado.')
        st.divider()
        rent_table = pd.DataFrame(rent_months)
        rent_table['Mês'] = rent_table['Mês'].map(lambda m: MONTHS[m-1])
        st.dataframe(rent_table, hide_index=True, use_container_width=True)
        with st.form('new_rent_payment', clear_on_submit=False):
            st.markdown('**Registar pagamento ao pavilhão**')
            rent_m = st.selectbox('Mês de utilização', range(1,13), index=max(0,today.month-1),
                                   format_func=lambda m: MONTHS[m-1], key='rent_month_edit')
            chosen = rent_months[rent_m-1]
            still_due = max(chosen['Previsto'] - chosen['Pago'], 0)
            rent_paid = st.number_input('Montante efetivamente pago (XOF)', min_value=1, step=500,
                                         value=int(still_due if still_due else (rent_cfg['monthly_rent'] or 3500)))
            rental_paid_on = st.date_input('Data real do pagamento', value=today, max_value=today, key='rent_payment_date')
            rental_note = st.text_input('Observação / comprovativo', placeholder='Ex.: recibo de setembro, pagamento em numerário')
            if st.form_submit_button('Guardar pagamento do campo', type='primary'):
                try:
                    add_rent_payment(engine, view_year, rent_m, rent_paid, rental_paid_on, rental_note)
                    reload_ok('Pagamento do pavilhão registado: entra nas despesas e atualiza o mês de referência.')
                except ValueError as exc:
                    st.error(str(exc))
        st.caption('Se o campo for pago em parcelas, regista cada pagamento separadamente. Para corrigir um erro, usa «Corrigir movimentos».')

st.markdown('---')
st.caption('Amigos de Amigos · Presidente: Deoclecio Jayrson Ferreira Marinho · Gestão restrita ao financeiro')
