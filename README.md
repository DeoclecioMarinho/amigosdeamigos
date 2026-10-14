# ⚽ Amigos de Amigos — Sistema do grupo de futsal

Aplicação em **Streamlit** para associados e tesouraria do grupo **Amigos de Amigos** (Pavilhão do INEFD). A fotografia do grupo encontra-se em `assets/amigos_de_amigos_grupo.jpg`, aparece na página inicial e na secção «O nosso grupo». A fotografia é mantida sem alterações.

## O que os associados podem ver (sem iniciar sessão)

- Fotografia do grupo, apresentação e horários habituais.
- Saldo acumulado, receitas (quotas, multas pagas e outras), despesas e respetivos movimentos.
- Situação das **mensalidades de cada membro**, por mês e por ano.
- **Presenças registadas**, chegadas tardias, multas por liquidar e multas efetivamente recebidas por treino.
- Histórico de vários anos. Os saldos de caixa transitam automaticamente entre anos.

A página pública não permite alterar pagamentos. Nota: caso a aplicação seja publicada sem autenticação geral, **a fotografia do grupo e a informação financeira tornam-se visíveis para qualquer pessoa com o endereço da aplicação**. Recomenda-se obter o acordo do grupo sobre essa publicação.

## O que o financeiro pode fazer (com palavra-passe)

- Adicionar, corrigir e desativar associados.
- Registar mensalidades completas, parciais e antecipadas.
- Criar o registo de cada treino regular (quarta-feira ou domingo), com nome, presença e hora de chegada; o sistema calcula automaticamente a multa aplicável.
- Registar o recebimento de uma multa no próprio dia ou numa data posterior, mantendo a data efetiva do pagamento.
- Registar despesas: aluguer do pavilhão, lavagem de equipamentos, bolas, apitos, coletes, bomba de ar e outras.
- Registar outras receitas, incluindo eventual saldo inicial.
- Exportar as tabelas e os movimentos em CSV.
- Corrigir um registo de treino **apenas se não existir multa recebida**; as multas recebidas não podem ser apagadas sem reconciliação contabilística.

## Regras do grupo (versão atual)

| Regra | Aplicação |
|---|---|
| Mensalidade | **3 500 XOF por mês** |
| Multa | **500 XOF por cada chegada tardia a um treino** |
| Quarta-feira | Treino às **20h00**; chegada até **20h15**, inclusive, sem multa |
| Domingo | Treino às **08h00**; chegada até **08h15**, inclusive, sem multa |
| Depois da tolerância | Multa de 500 XOF para o treino em causa |
| Pagamento da multa | Deve ser feito **no próprio dia, antes de treinar**. Enquanto estiver pendente, a aplicação mostra «não treina». |
| Atraso na mensalidade | **Não gera multa de treino**; é registado apenas como quota por pagar. |

O sistema **não presume faltas** dos associados sem registo de presença. A multa por atraso é calculada individualmente, por data e hora de chegada, e só entra na caixa quando o pagamento é registado. O valor de multa e da mensalidade pode ser configurado por ano. Registos históricos conservam os montantes originais.

## Instalação local

Requer **Python 3.10 ou superior**. Na pasta da aplicação:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para permitir gestão financeira, cria `.streamlit/secrets.toml` a partir de `.streamlit/secrets.toml.example` e preenche:

```toml
FINANCE_PASSWORD = "PALAVRA_PASSE_FORTE_AQUI"
```

Sem password a aplicação só permite consulta. Em ambiente local os dados são guardados no ficheiro `data/amigos.db` (SQLite). **Faz cópias de segurança regularmente.**

## Publicar no Streamlit Community Cloud

1. Coloca os ficheiros no GitHub, incluindo `assets/amigos_de_amigos_grupo.jpg` e excluindo `.streamlit/secrets.toml` e ficheiros `.db`.
2. Publica `app.py` no Streamlit Community Cloud.
3. Configura uma base PostgreSQL externa persistente (por exemplo, Neon ou Supabase). Usa a URL de ligação disponibilizada pelo serviço, não o URL do painel.
4. Em *Settings → Secrets*, define:

```toml
FINANCE_PASSWORD = "PALAVRA_PASSE_FORTE_AQUI"
DATABASE_URL = "postgresql://UTILIZADOR:SENHA@HOST:5432/BASE?sslmode=require"
```

**Não uses SQLite como armazenamento definitivo no Streamlit Community Cloud**: os ficheiros locais podem perder-se em reinicializações e recriações da aplicação. Não publiques as credenciais no GitHub.

## Importação da folha histórica de 2026

- Foram identificados 33 nomes provisórios nas fotografias da lista de pagamentos; alguns precisam de confirmação.
- `historico_foto_2026_para_validar.csv` contém marcações transcritas de forma **aproximada**. O ficheiro **não é importado automaticamente**.
- O financeiro deve corrigir os nomes, validar cada marca, importar apenas os pagamentos confirmados e inserir eventuais pagamentos/despesas que faltem.
- Datas de recebimento desconhecidas são tratadas como aproximações para consulta histórica, sem inventar uma data exata.
- A fotografia do grupo é apenas para apresentação, **não é usada para identificar automaticamente pessoas nem associar rostos a nomes**.

## Testes

Para verificar regras financeiras e multas:

```bash
pip install pytest
python -m pytest -q
```

## Notas sobre segurança e utilização

O login usa uma palavra-passe única para o financeiro. Não existe autenticação individual nem auditoria detalhada de quem alterou cada lançamento. Esta é uma aplicação simples para tesouraria de um grupo; pagamentos contestados ou correções de multas já liquidadas devem ser reconciliados antes de alterar a base de dados. Recomenda-se nomear o financeiro principal e um substituto para conferir periodicamente o saldo e os comprovativos.
