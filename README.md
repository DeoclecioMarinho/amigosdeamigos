# Amigos de Amigos — Streamlit v4.1 (correção ImportError)

Esta versão corresponde à v4 com uma verificação de compatibilidade dos módulos, para impedir o erro de importação caso o GitHub tenha ficheiros misturados de versões anteriores.

## Corrigir a aplicação no Streamlit Cloud

1. Abre o repositório GitHub `amigosdeamigos`, no mesmo ramo que está publicado no Streamlit Cloud.
2. **Substitui em conjunto, na raiz do repositório**, os ficheiros `app.py`, `database.py`, `finance.py`, `requirements.txt` e `historico_foto_2026_para_validar.csv`. Não basta atualizar apenas o `app.py`.
3. Envia também a pasta `assets` (contém `amigos_de_amigos_grupo.jpg`), para mostrar a fotografia na página inicial.
4. Confirma que `app.py`, `database.py` e `finance.py` aparecem no **mesmo nível**. O ZIP está organizado sem pasta extra para facilitar o upload.
5. Faz **Commit changes** no GitHub. O Streamlit Cloud deverá atualizar-se; se continuar a mostrar uma versão antiga, usa **Manage app > Reboot app**.
6. Se aparecer erro de ligação à base de dados, vai a **Manage app > Settings > Secrets** e confirma `DATABASE_URL` (se usares PostgreSQL). A senha do financeiro é configurada nesse mesmo local, não no código público.

**Não apagues a base de dados existente**: os pagamentos, multas e despesas confirmados são guardados na base atual. Atualizar ficheiros `.py` não elimina esses dados quando usas PostgreSQL persistente.

**Atenção:** Se a app usa SQLite local no Streamlit Community Cloud, não há garantia de conservação dos dados após reinícios. Para utilização real com pagamentos, usa PostgreSQL (por exemplo, Neon ou Supabase) e faz cópias de segurança.

## Credenciais e configuração

Em **Manage app > Settings > Secrets**, define:

```toml
FINANCE_USERNAME = "financeiro"
FINANCE_PASSWORD = "COLOCA_AQUI_A_TUA_PALAVRA_PASSE"
# DATABASE_URL = "postgresql://utilizador:senha@servidor/base?sslmode=require"
```

**Não publiques** o ficheiro `.streamlit/secrets.toml` com dados verdadeiros. O `.streamlit/secrets.toml.example` incluído é apenas um modelo. Como o código anterior foi partilhado no chat e pode ter sido carregado para o GitHub, troca o código do financeiro antes de divulgar a aplicação.

## O que foi mantido

- Fotografia original do grupo na página inicial e secção O Grupo.
- Presidente do grupo: Deoclecio Jayrson Ferreira Marinho.
- Mensalidades de 3 500 XOF e marcas históricas de 2026, por validar.
- Multa de 500 XOF por cada atraso no treino, com tolerância até às 20h15 à quarta e às 08h15 ao domingo.
- Gestão de quotas, presenças, despesas, aluguer do pavilhão e saldos anuais/acumulados.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para executar os testes com `pytest` instalado:

```bash
python -m pytest -q
```

Os ficheiros `data/*.db` e `.streamlit/secrets.toml` **não** são incluídos no pacote.
