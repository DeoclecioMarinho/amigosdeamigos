# ⚽ Amigos de Amigos — Painel completo de tesouraria (v4)

Sistema Streamlit de futsal no Pavilhão do INEFD, com **presidente Deoclecio Jayrson Ferreira Marinho**.

## Iniciar o programa

1. Instalar Python 3.10+ e executar `pip install -r requirements.txt`.
2. Executar `streamlit run app.py`.
3. Abrir a aplicação. **A Visão geral, Mensalidades, Treinos e Multas, Finanças, O Grupo e Aluguer do Campo são públicos**.
4. O financeiro inicia sessão na barra lateral com **utilizador `financeiro`** e **código `amgamg2026`**, já guardados no `.streamlit/secrets.toml` para a instalação local.

**Segurança:** o código é provisório e foi solicitado pelo grupo. Antes de partilhar a aplicação na Internet, **trocar o código**, não publicar o ficheiro `.streamlit/secrets.toml` e configurar as credenciais na secção **Settings → Secrets** do Streamlit Cloud. O ficheiro real está no `.gitignore`.

## O que está preparado

- Fotografia **original** do grupo (1080 × 809) mostrada na página inicial e na secção «O Grupo», sem cortar participantes.
- 33 nomes da folha fotografada (alguns com grafia por confirmar); nomes editáveis, novos membros, entrada e saída.
- **130 marcas de mensalidades** (2026) pré-carregadas como **✓? (por confirmar)**. Estas marcas são sugestões visíveis, **não são somadas às entradas de caixa** antes da conferência do financeiro. O financeiro pode confirmar em lote as verificadas ou rejeitar as erradas.
- Grelha janeiro–dezembro por membro para 2026 e qualquer ano futuro: **✓** pago confirmado, **✓?** marca da fotografia pendente, **◐** parcial, **·** sem confirmação, **—** não aplicável.
- Área do financeiro para assinalar meses pagos, anular com confirmação e histórico da alteração, adicionar parciais, editar valores, datas e meses dos lançamentos.
- Mensalidade **3 500 XOF**. Multa de **500 XOF por cada chegada tardia ao treino**, não por atraso de mensalidade. Quarta-feira treino 20h00, multa após 20h15. Domingo treino 08h00, multa após 08h15. A multa deve ser paga no próprio dia antes de treinar.
- Dashboard de **entradas (mensalidades, multas pagas, donativos)**, **saídas (lavagens, bolas, apitos, coletes, bombas, água e outras)**, **saldo acumulado** e **resumo mês a mês por ano**.
- **Aluguer do campo**: o financeiro configura o valor mensal do espaço para cada ano, regista cada pagamento ao pavilhão com mês de referência e data real e consulta o quadro mensal **pago, parcial, por pagar ou ainda a vencer**. Os montantes pagos entram automaticamente como despesas.
- Histórico de 2026 em diante, com saldo a transitar de um ano para o seguinte. CSV para exportação de membros, movimentos, multas, marcações da fotografia, aluguer e auditoria.

## Importante para ler o dashboard

1. A fotografia fornece um **pré-registo sujeito a validação**. O sistema não sabe a data real desses recebimentos nem confirma se todas as marcas representam pagamentos. O financeiro deve consultar os comprovativos originais.
2. Ao validar uma marca histórica sem data conhecida, o valor é contabilizado no **mês da mensalidade**, por aproximação apenas para o gráfico. Na **caixa acumulada** o montante é contado uma única vez.
3. Não há dados anteriores de **despesas, aluguer ou multas**, pois não foram fornecidos. O financeiro terá de os introduzir. **Não foi inventado qualquer montante pago ao pavilhão.**
4. Para anos futuros o valor da mensalidade e das multas pode ser ajustado em «Regras e exportação». O valor do aluguer é configurado na área «Aluguer do campo».
5. Se o grupo já tem dinheiro em caixa anterior ao período registado, utilizar uma só vez «Outra receita → Saldo inicial».
6. Os pagamentos de aluguer devem ser registados no separador dedicado. As despesas com equipamentos são registadas separadamente, para não duplicar valores de aluguer.

## Publicar online sem perder a base de dados

Para produção no **Streamlit Community Cloud**, usar uma base de dados PostgreSQL gerida (ex.: Neon ou Supabase). A SQLite local serve apenas para testar; os ficheiros podem desaparecer após uma reinicialização do Community Cloud.

Colocar o código no GitHub SEM `.streamlit/secrets.toml` e SEM `data/*.db`; configurar nos segredos do Streamlit Cloud:

```toml
FINANCE_USERNAME = "financeiro"
FINANCE_PASSWORD = "ALTERAR_PARA_UM_CODIGO_FORTE"
DATABASE_URL = "postgresql://utilizador:senha@host:5432/base?sslmode=require"
```

Nota de privacidade: o painel público expõe nomes, dívidas e fotografia dos jogadores a quem tenha o endereço da aplicação. Recomenda-se acordo expresso do grupo ou um controlo de acesso de leitura se necessário.

## Testes

```bash
python -m pytest -q
```

Os testes cobrem as regras de quota, limite de atraso nos treinos, receitas de multas, meses de campo, correções de mensalidades e histórico de 2026. A interface Streamlit precisa de confirmação visual depois de instalada.
