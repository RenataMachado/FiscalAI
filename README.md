# Sistema de Gestão de Notas Fiscais — estrutura dividida

O arquivo original `interprete_nota_finance.py` (2204 linhas, 51 funções) foi
dividido em módulos menores, mantendo **100% da lógica original intacta**
(nenhuma linha de código dentro das funções foi alterada — apenas
reorganizada em arquivos, com os imports necessários ajustados).

## Como rodar

```
streamlit run app.py
```

`app.py` fica **fora** do pacote `nfe_app/` de propósito, para evitar
problemas de "relative import" ao rodar com `streamlit run`.

## Estrutura

```
app.py                          # ponto de entrada: main() + navegação/sidebar
nfe_app/
    config.py                   # conexão com o Postgres (engine) e cliente Gemini (IA)
    ocr_utils.py                # conversão de PDF/imagem, leitura de QR Code, OCR tabular
    extract_nfe.py               # extração de dados da Nota Fiscal (NFS-e) via regex/OCR
    extract_contratos_ia.py      # extração de Contratos/Aditivos/Empenhos via IA (Gemini) e regex em PDF
    extract_empenho.py           # extração de dados da Nota de Empenho (padrão SIAFÍSICO SP)
    formatters.py                # formatação de valores, ISS, CNPJ, datas, câmbio
    ui_helpers.py                # alerta central e gravação de notas no banco
    excel_export.py              # geração das planilhas Excel (levantamento e cálculo de pagamento)
    pdf_export.py                # geração do PDF de balanço
    pages/
        processar_nota.py        # tela "Processador Nota"
        balanco.py                # tela "Balanço (Painel de Controle)"
        contratos.py              # tela "Resumos Contratuais"
        aditivos.py                # tela "Termos Aditivos"
        empenhos.py                # tela "Notas de Empenho"
        vigencia.py                 # tela "Acompanhamento de Vigência"
requirements.txt
```

## Verificações feitas antes da entrega

- **51 de 51 funções** do arquivo original foram localizadas nos novos arquivos,
  com o corpo **idêntico, byte a byte**, ao original (comparação automática).
- Todos os 18 arquivos `.py` compilam sem erro de sintaxe (`py_compile`).
- Checagem estática de nomes usados sem import correspondente — corrigida
  (ex.: `pages/balanco.py` também precisava de `formata_cnpj` e `formata_data`,
  além de `formata_valor`).
- Total de linhas nos arquivos novos: ~2300 (a diferença em relação às 2204
  originais é só docstrings de cada módulo, linhas de import e espaçamento
  entre arquivos — nenhuma lógica foi adicionada ou removida).

## Banco de dados: criação e controle de tabelas com Alembic

Antes, as 4 tabelas (`notas_fiscais`, `resumo_contratos`, `termos_aditivos`,
`notas_empenho`) eram criadas "na sorte" pelo `pandas.to_sql(...)`, na
primeira vez que alguém salvava alguma coisa, sem tipos definidos, sem
`id`, sem controle de versão do schema. Agora isso é controlado pelo
**Alembic**, então sempre que o projeto for transferido para outra máquina
basta rodar um comando para o banco ficar com a estrutura correta.

### Primeira vez em uma máquina nova

```bash
pip install -r requirements.txt
cp .env.example .env          # depois edite o .env com o DATABASE_URL real
python scripts/setup_db.py    # cria o BANCO (se não existir) e as tabelas
```

`scripts/setup_db.py` faz as duas coisas que faltavam pra isso ser
"transferi o projeto e não tive problema nenhum":
1. Roda `CREATE DATABASE` se o banco da `DATABASE_URL` ainda não existir
   (o Alembic sozinho não faz isso, ele só cria/altera tabelas *dentro*
   de um banco que já existe).
2. Chama `alembic upgrade head` pra criar as 4 tabelas.

Se a máquina nova **nem tem Postgres instalado ainda**, tem um
`docker-compose.yml` na raiz: `docker compose up -d` sobe um Postgres do
zero, idêntico em qualquer máquina, e aí sim roda o `setup_db.py` acima.

### Se você já tinha dados no banco (tabelas criadas pelo pandas, sem Alembic)

O Alembic vai tentar criar as tabelas do zero e vai dar erro se elas já
existirem. Nesse caso, sem apagar nada, apenas registre que o banco já
está "no estado da migration 0001", sem executá-la de fato:

```bash
alembic stamp 0001
```

A partir daí o Alembic passa a controlar o schema dali pra frente.

### Quando você mudar/adicionar uma coluna no futuro

1. Edite `nfe_app/db/models.py` (adicione/altere a coluna no model).
2. Gere a migration automaticamente comparando o model com o banco atual:
   ```bash
   alembic revision --autogenerate -m "descricao da mudanca"
   ```
3. **Abra o arquivo gerado em `alembic/versions/` e confira** se o Alembic
   entendeu certo (autogenerate erra tipo de coluna às vezes).
4. Aplique no banco:
   ```bash
   alembic upgrade head
   ```

### Estrutura adicionada

```
alembic.ini                        # config do Alembic (a URL do banco NÃO fica aqui, fica no .env)
alembic/
    env.py                         # lê o .env e usa nfe_app/db/models.py como referência do schema
    script.py.mako                 # template usado ao gerar novas migrations
    versions/
        0001_tabelas_iniciais.py   # migration inicial: cria as 4 tabelas
nfe_app/db/
    models.py                      # os 4 models SQLAlchemy (NotaFiscal, ResumoContrato, TermoAditivo, NotaEmpenho)
scripts/
    setup_db.py                    # cria o banco (CREATE DATABASE) se faltar + roda as migrations
docker-compose.yml                 # opcional: sobe um Postgres do zero se a máquina não tiver um
.env.example                       # modelo de .env pra copiar em cada máquina nova
```

> **Importante:** o app continua salvando/lendo dados exatamente como antes
> (`pandas.to_sql` / `pandas.read_sql`), o Alembic só cuida da *estrutura*
> das tabelas (criar, alterar colunas), não substitui a forma como os
> dados são gravados no dia a dia.

> **Não testei rodando de verdade** (este ambiente não tem acesso a rede
> nem Postgres para eu instalar `alembic`/`sqlalchemy` e validar de ponta a
> ponta). A sintaxe e a estrutura seguem o padrão oficial do Alembic e os
> nomes de tabela/coluna foram conferidos um a um contra o código original
>, mas rode `alembic upgrade head` num banco de teste primeiro e me
> avise se der algum erro.

## Observação sobre `client` (Gemini)

Em `config.py`, `client` só é criado se `GEMINI_API_KEY` estiver definida no
`.env` — exatamente como no arquivo original. Se você usa `client` em
`extract_contratos_ia.py` sem essa variável definida, vai dar erro de
`NameError`, igual acontecia antes da divisão (comportamento preservado, não
é um bug novo).
