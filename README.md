# Lingua Kindle

Uma ferramenta de terminal que transforma os destaques do arquivo `My Clippings.txt` do Kindle em cartões enriquecidos para o Anki:

- frase original em inglês;
- tradução natural para pt-BR;
- até três itens de vocabulário;
- uma observação gramatical curta quando for útil;
- título, autor e posição do destaque;
- campo vazio para áudio gerado pelo AwesomeTTS.

Os destaques são enviados ao OpenRouter em pequenos lotes. O arquivo inteiro do livro nunca é enviado, e as requisições usam `data_collection: "deny"` por padrão.

## Instalação

É necessário Python 3.12 ou mais recente. Com `uv`:

```bash
uv tool install .
```

Para desenvolver no repositório:

```bash
uv sync --extra dev
uv run lingua --help
```

## Configuração inicial

Crie uma chave específica para o projeto no workspace do OpenRouter e defina um limite de gastos. Exporte a chave apenas no terminal atual ou coloque-a no gerenciador de segredos do seu shell:

```bash
export OPENROUTER_API_KEY="sua-chave"
lingua init
lingua doctor "/caminho/para/My Clippings.txt"
```

Como alternativa, copie `.env.example` para `.env` no diretório do projeto e preencha a chave. O `.env` é carregado automaticamente, não sobrescreve uma variável já definida no terminal e está ignorado pelo Git:

```bash
cp .env.example .env
```

O `lingua init` cria `.lingua/config.toml` e `.lingua/lingua.db`. A chave não é gravada nesses arquivos.

## Fluxo diário

Liste os livros reconhecidos:

```bash
lingua books "/caminho/para/My Clippings.txt"
```

Prepare somente os destaques ainda não exportados. Sem `--book`, a CLI mostra um menu:

```bash
lingua prepare "/caminho/para/My Clippings.txt"
```

Abra o TSV criado em `drafts/` no LibreOffice, Excel ou editor de texto. Você pode corrigir qualquer campo e definir `Include` como `no` para descartar um cartão. Preserve os nomes e a ordem das colunas.

Depois exporte:

```bash
lingua export "drafts/nome-do-livro-data.tsv"
```

O arquivo de `exports/` já contém as diretivas de importação do Anki. As marcações só são registradas como exportadas depois que esse arquivo é gravado com sucesso.

## Escolha do modelo

Antes de adotar um modelo, você pode gerar uma avaliação cega:

```bash
lingua evaluate "/caminho/para/My Clippings.txt" --sample 12
```

Preencha todas as colunas `Translation Score` e `Teaching Score` com notas de 1 a 5. Em seguida:

```bash
lingua select-model "evaluations/relatorio.tsv"
```

O vencedor é definido pela maior média; em caso de empate, ganha o candidato de menor custo reportado. O modelo escolhido é salvo em `.lingua/config.toml`. A opção `model` também aceita um preset do workspace, como `@preset/lingua-translation`.

## Anki e AwesomeTTS

Antes da primeira importação, crie o tipo de nota descrito em [anki/NOTE_TYPE.md](anki/NOTE_TYPE.md). Depois importe o TSV e gere os áudios em lote usando:

- campo de origem: `English`;
- campo de destino: `Audio`;
- voz: inglês americano (`en-US`).

O primeiro campo, `CardID`, é estável. Ao reimportar uma nota já existente, o Anki pode atualizá-la em vez de criar uma duplicata.

## Comandos úteis

```text
lingua init                       Inicializa configuração e banco
lingua doctor [CLIPPINGS]         Diagnostica arquivo, configuração e API
lingua books CLIPPINGS            Lista livros e destaques novos
lingua prepare CLIPPINGS          Traduz e cria rascunho
lingua export DRAFT               Cria TSV final do Anki
lingua evaluate CLIPPINGS         Compara modelos às cegas
lingua select-model REPORT        Salva o modelo vencedor
```

Use `--workspace` em qualquer comando para guardar a configuração em outro diretório.

## Releases para Windows e Linux

Ao enviar uma tag no formato `vX.Y.Z`, o GitHub Actions testa o projeto, gera executáveis nativos para Linux AMD64 e Windows AMD64 e publica ambos na página **Releases**. A tag deve ter a mesma versão de `pyproject.toml`; por exemplo, a versão `0.1.0` exige a tag `v0.1.0`.

```bash
git tag v0.1.0
git push origin v0.1.0
```

Depois, baixe o arquivo pela página de Releases do repositório ou com a GitHub CLI:

```bash
gh release download v0.1.0 --pattern 'lingua-*'
```

No Linux, torne o binário executável se necessário e execute-o:

```bash
chmod +x lingua-linux-amd64
./lingua-linux-amd64 --help
```

No Windows, execute `lingua-windows-amd64.exe` pelo PowerShell ou Explorador de Arquivos.
