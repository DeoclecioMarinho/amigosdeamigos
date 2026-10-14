# Amigos de Amigos — Streamlit v4.4 (menu lateral e login visível)

## Novidades da v4.4

- Menu **vertical à esquerda**, sempre visível, com uma secção pública de cada vez à direita.
- Opção **🔐 Acesso do financeiro** permanentemente no menu lateral. O formulário com nome de utilizador e código de acesso aparece na área direita.
- Quando o financeiro entra, surgem mais oito páginas de gestão na **mesma barra lateral**, incluindo mensalidades, associados, despesas, aluguer e histórico de 2026.
- A fotografia do grupo aparece na **Página principal** e em **O grupo**, não em todas as páginas.
- Mantém o tratamento de erros de `photo_marks` da versão 4.3; não elimina registos antigos.

## Ativar entrada do financeiro no Streamlit Cloud

1. Abre Streamlit Cloud → **Manage app → Settings → Secrets**.
2. Coloca as seguintes linhas substituindo o marcador por um código privado:

   ```toml
   FINANCE_USERNAME = "financeiro"
   FINANCE_PASSWORD = "COLOCA_AQUI_O_CODIGO_PRIVADO"
   ```

3. Guarda e reinicia a aplicação.
4. Seleciona **🔐 Acesso do financeiro** no menu lateral, escreve o nome de utilizador `financeiro` e o código configurado.

**IMPORTANTE:** Não graves a palavra-passe no GitHub, `app.py` ou `secrets.toml.example`. O código inicialmente combinado já foi partilhado nesta conversa; recomenda-se alterá-lo antes de usar o sistema publicamente. O formulário surge mesmo sem secrets, mas não permite editar enquanto não estiver configurado.

## Instalação / publicação

Atualiza em conjunto `app.py`, `database.py`, `finance.py`, `requirements.txt`, `assets` e CSV no repositório. É importante manter a mesma versão dos três módulos. Depois faz commit e Streamlit Cloud → Manage app → Reboot app.

A base de dados existente **não deve ser apagada**. As marcações de 2026 por confirmar não contam como receitas. Para persistência em produção, configura `DATABASE_URL` apontando para PostgreSQL externo e faz backups periódicos.

## Executar localmente

```bash
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

---

## Histórico da v4.3

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
