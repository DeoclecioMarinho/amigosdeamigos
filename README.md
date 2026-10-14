# Amigos de Amigos — Streamlit v4.3 (isolamento e recuperação de photo_marks)

## O que corrige

A versão anterior interrompia toda a aplicação quando a consulta da tabela
`photo_marks` falhava. Esta tabela contém **somente as marcas provisórias
transcritas das fotografias**, nunca a contabilidade efetiva.

A versão 4.3:

1. Em falhas que indiquem tabela/coluna ausente, tenta automaticamente executar
   uma migração aditiva e recupera o acesso sem DROP/DELETE.
2. Se o acesso não puder ser corrigido com segurança, o **dashboard continua** a
   apresentar mensalidades realmente registadas, multas, aluguer e despesas;
   mostra um aviso e bloqueia a validação de marcas da fotografia e a exportação
   dessa tabela até ser resolvida.
3. Mantém os dados persistentes e os módulos sincronizados (`APP_COMPAT_VERSION=4.3`).
4. Guarda no log a exceção SQL original para diagnóstico. Não assume que
   conhece a causa sem o erro completo dos logs.

**Atenção:** Se `photo_marks` for recriada a partir do CSV porque desapareceu,
precisa de nova validação. As marcas não são receitas até serem confirmadas.

## Como atualizar

1. Faz cópia de segurança dos dados financeiros se estiveres a usar PostgreSQL.
2. Extrai o ZIP e atualiza todos os ficheiros `app.py`, `database.py`,
   `finance.py`, `requirements.txt`, a pasta `assets` e o CSV histórico no GitHub.
3. Faz commit e reinicia a app em Streamlit Cloud.
4. Se aparecer aviso de erro de `photo_marks`, abre **Manage app → Logs** e copia
   as linhas da exceção que indiquem `no such column`, `no such table`,
   `permission denied`, `database is locked` ou outro erro específico.
   Não partilhes URLs com passwords, tokens ou `DATABASE_URL`.

O ficheiro SQLite em Streamlit Community Cloud não garante persistência em
reinícios. Para contas reais, usa PostgreSQL externo e backups regulares.

## Acesso protegido

Configura os segredos `FINANCE_USERNAME`, `FINANCE_PASSWORD` e `DATABASE_URL` nas
Settings do Streamlit Cloud. **Não coloques credenciais no GitHub.** Usa uma nova
palavra-passe, já que o código inicial foi partilhado na conversa.

## Funcionalidades

- Membros e mensalidades por ano/mês (3 500 XOF de referência), ✓ pago e ✓? por conferir.
- Multas por atraso em treinos (500 XOF por treino), quarta até 20h15 e domingo até 08h15.
- Aluguer de campo, equipamentos, lavagem, saldo mensal e anual.
- Fotografia original em `assets/amigos_de_amigos_grupo.jpg`.
- Presidente: Deoclecio Jayrson Ferreira Marinho.

## Testar localmente

```bash
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```
