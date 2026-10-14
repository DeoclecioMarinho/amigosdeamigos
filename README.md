# Amigos de Amigos — Streamlit v4.2 (correção de base de dados)

Esta versão corrige a causa possível de `sqlalchemy.exc.OperationalError` após atualizar
uma aplicação antiga: `create_all()` criava tabelas mas **não acrescentava colunas
novas nas tabelas existentes**. Agora verifica a estrutura e aplica apenas alterações
**aditivas e compatíveis**; não elimina nem substitui tabelas ou registos.

**Atenção:** O texto fornecido do traceback não contém a última linha com o erro SQL
original (`no such column`, `no such table`, `database is locked`, etc.). Assim,
não é possível confirmar exatamente o motivo sem essa linha nos logs.

## Atualizar a aplicação publicada

1. Se já tens pagamentos reais numa base PostgreSQL, faz primeiro uma cópia de segurança.
2. Extrai este ZIP e atualiza **em conjunto** os ficheiros `app.py`, `database.py`,
   `finance.py`, `requirements.txt`, o CSV histórico e a pasta `assets` na raiz do repositório.
3. Faz commit para o ramo usado pela aplicação no Streamlit Cloud.
4. No Streamlit Cloud, abre **Manage app → Reboot app** se necessário.
5. Se o erro permanecer, consulta **Manage app → Logs**. O novo código identifica no
   log a tabela cuja consulta falhou. Partilha a última linha do erro SQL sem qualquer
   senha, URL de ligação, token ou dado pessoal.

Não apagues o ficheiro da base de dados nem elimines tabelas para resolver o erro.

## Persistência e segurança

Para uso em produção, configura `DATABASE_URL` para uma base PostgreSQL persistente.
O ficheiro SQLite local no Streamlit Community Cloud pode desaparecer no reinício,
mesmo quando a estrutura está correta.

A conta do financeiro é configurada em **Manage app → Settings → Secrets**, por exemplo:

```toml
FINANCE_USERNAME = "financeiro"
FINANCE_PASSWORD = "COLOCA_AQUI_UM_CODIGO_PRIVADO"
# DATABASE_URL = "postgresql://utilizador:senha@servidor/base?sslmode=require"
```

Nunca publiques `.streamlit/secrets.toml` com palavras-passe no GitHub. O código de
acesso anteriormente partilhado deve ser alterado antes de disponibilizar a aplicação
à comunidade.

## Regras e histórico

- Presidente: Deoclecio Jayrson Ferreira Marinho.
- Fotografia original do grupo em `assets/amigos_de_amigos_grupo.jpg`.
- Mensalidade: 3 500 XOF; multa de atraso no **treino**: 500 XOF por ocorrência.
- Treinos no INEFD: quarta-feira 20h00 (até 20h15), domingo 08h00 (até 08h15).
- Multas pagas no dia; sem pagamento, não treina.
- Histórico de 2026 carregado **para validação**, não como receitas confirmadas.
- Despesas e aluguer de campo, balanço mensal, anual e acumulado.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para executar testes:

```bash
python -m pytest -q
```
