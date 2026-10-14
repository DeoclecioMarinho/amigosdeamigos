"""Testes estáticos da navegação para prevenir regressões na interface."""
from pathlib import Path
import ast

SOURCE = (Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)


def test_login_is_an_always_available_page():
    assert "LOGIN_PAGE = '🔐 Acesso do financeiro'" in SOURCE
    assert "PUBLIC_PAGES + [LOGIN_PAGE]" in SOURCE
    assert "if page == LOGIN_PAGE:" in SOURCE
    assert "with st.form('login_financeiro'" in SOURCE


def test_admin_actions_visible_only_when_authenticated():
    restricted = [n for n in TREE.body if isinstance(n, ast.If) and 'page == ADMIN_PAGES[' in ast.unparse(n.test)]
    assert len(restricted) == 8
    assert all('st.session_state.auth' in ast.unparse(n.test) for n in restricted)


def test_one_page_at_a_time_and_no_tabs():
    assert 'st.tabs(' not in SOURCE
    pages = [n for n in TREE.body if isinstance(n, ast.If) and 'page == PUBLIC_PAGES[' in ast.unparse(n.test)]
    assert len(pages) == 6
    assert "page = st.radio('Navegação do sistema'" in SOURCE


def test_group_photo_appears_on_home_and_group_page():
    photo_uses = [node for node in ast.walk(TREE) if isinstance(node, ast.Call) and ast.unparse(node.func) == 'st.image']
    assert len(photo_uses) == 2
    assert 'amigos_de_amigos_grupo.jpg' in SOURCE


def test_financial_code_is_not_embedded_in_app():
    assert 'amgamg2026' not in SOURCE
    assert "secret('FINANCE_PASSWORD')" in SOURCE
