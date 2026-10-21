# Fluxo de releases

Este documento descreve o fluxo atual para publicar o Lingua como pacote Python, disponibilizar os binários nativos e instalar o comando `lingua` com `uv`.

## Visão geral

O projeto usa dois canais de distribuição:

| Canal | Disparo | Conteúdo |
| --- | --- | --- |
| TestPyPI | Manual, pelo workflow `TestPyPI` | Pacote Python para validação antes da publicação real |
| PyPI e GitHub Releases | Tag Git `vX.Y.Z` | Pacote Python, binário Linux AMD64, binário Windows AMD64 e notas da release |

O nome do pacote distribuído é `lingua-kindle`. O comando instalado pelo pacote é `lingua`.

O fluxo de produção está em [`.github/workflows/release.yml`](../.github/workflows/release.yml). O fluxo de teste está em [`.github/workflows/testpypi.yml`](../.github/workflows/testpypi.yml).

## Pré-requisitos

- Python 3.12 ou mais recente;
- `uv` instalado;
- acesso de administrador ao repositório GitHub;
- conta no [PyPI](https://pypi.org/) e no [TestPyPI](https://test.pypi.org/);
- Trusted Publishers configurados no PyPI, no TestPyPI e nos ambientes correspondentes do GitHub.

O projeto não usa token permanente do PyPI. A publicação usa Trusted Publishing com OIDC e a action oficial `pypa/gh-action-pypi-publish`.

## Configuração única de publicação

### Ambientes do GitHub

Em **Settings → Environments**, crie estes ambientes:

- `testpypi`;
- `pypi`.

Não é necessário adicionar secrets nesses ambientes. Os nomes precisam ser exatamente iguais aos usados nos workflows.

### Publisher do TestPyPI

Na conta do [TestPyPI](https://test.pypi.org/), configure um Trusted Publisher para:

- owner: usuário ou organização dona do repositório;
- repository: `lingua`;
- workflow filename: `.github/workflows/testpypi.yml`;
- environment name: `testpypi`.

### Publisher do PyPI

Na conta do [PyPI](https://pypi.org/), configure outro Trusted Publisher para:

- owner: usuário ou organização dona do repositório;
- repository: `lingua`;
- workflow filename: `.github/workflows/release.yml`;
- environment name: `pypi`.

Para um projeto que ainda não existe no índice, use a opção de publisher pendente durante a configuração inicial. O nome `lingua-kindle` precisa ser preservado em `pyproject.toml`.

Consulte também a [documentação oficial do Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Versionamento

A versão é alterada manualmente em `pyproject.toml` e deve ser sincronizada no `uv.lock`:

```bash
uv lock
uv lock --check
```

A tag precisa corresponder exatamente à versão do projeto:

```text
pyproject.toml: version = "0.2.0"
tag Git:          v0.2.0
```

O workflow falha antes de publicar se a tag não for igual a `v<versão do pyproject.toml>`.

## Release recomendada

### 1. Atualizar a versão

Edite a versão em `pyproject.toml`, regenere o lockfile e revise as mudanças:

```bash
uv lock
uv lock --check
git diff --check
```

### 2. Validar localmente

Execute os testes e gere os artefatos publicáveis:

```bash
uv run pytest
uv build --no-sources
```

Os artefatos Python aparecem em `dist/` como wheel e source distribution.

### 3. Enviar a versão para o GitHub

Primeiro envie o commit da versão para a branch principal:

```bash
git push origin main
```

### 4. Validar no TestPyPI

Na aba **Actions** do GitHub:

1. abra o workflow **TestPyPI**;
2. selecione **Run workflow**;
3. informe opcionalmente uma branch, tag ou commit no campo `ref`;
4. aguarde a publicação e as verificações.

Esse workflow executa os testes, constrói o pacote, publica no TestPyPI e testa uma instalação isolada com:

```bash
uv tool install --force \
  --default-index https://test.pypi.org/simple \
  --index https://pypi.org/simple \
  lingua-kindle
lingua --help
lingua doctor entries.example.json --no-check-api
```

O workflow usa TestPyPI como índice principal e PyPI como índice adicional para resolver as dependências do Lingua.

### 5. Criar a release de produção

Depois que o TestPyPI passar, crie e envie a tag correspondente:

```bash
git tag v0.2.0
git push origin v0.2.0
```

O workflow de produção executa estas etapas:

1. valida a tag contra `pyproject.toml` e `uv.lock`;
2. executa os testes;
3. constrói wheel e source distribution;
4. publica ambos no PyPI via Trusted Publishing;
5. constrói os binários Linux AMD64 e Windows AMD64;
6. cria a GitHub Release com os artefatos Python e nativos;
7. gera as notas da release automaticamente.

A GitHub Release só é criada depois que a publicação no PyPI termina com sucesso.

## Artefatos esperados

Para a versão `0.2.0`, a GitHub Release deve conter:

- `lingua_kindle-0.2.0-py3-none-any.whl`;
- `lingua_kindle-0.2.0.tar.gz`;
- `lingua-linux-amd64`;
- `lingua-windows-amd64.exe`.

Usuários Python instalam ou atualizam o pacote com:

```bash
uv tool install lingua-kindle
uv tool upgrade lingua-kindle
```

Os binários nativos são baixados diretamente da GitHub Release.

## Diagnóstico rápido

### A validação da tag falhou

Confira se a versão e a tag são idênticas:

```bash
sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml
git tag --list 'v*'
```

Uma versão publicada não deve ser reutilizada. Para corrigir, incremente a versão e crie uma nova tag.

### A publicação retorna erro de Trusted Publisher

Confira, nos dois índices, todos estes valores:

- owner do GitHub;
- nome do repositório;
- caminho exato do workflow;
- nome do ambiente (`pypi` ou `testpypi`).

Também confirme que o workflow possui `id-token: write`. Essa permissão já está definida no nível do job nos workflows do projeto.

### O TestPyPI publica, mas a instalação falha

Verifique se o pacote foi publicado no TestPyPI e se a instalação usa os dois índices. As dependências do Lingua são resolvidas no PyPI público quando não estão disponíveis no TestPyPI.

### A GitHub Release não foi criada

A criação da GitHub Release depende da publicação no PyPI. Consulte primeiro o job **Publish Python distributions to PyPI**; corrigir esse job e reenviar a mesma tag pode exigir uma nova versão caso o pacote já tenha sido aceito pelo PyPI.

## Referências do fluxo

- [Workflow de CI](../.github/workflows/ci.yml)
- [Workflow de TestPyPI](../.github/workflows/testpypi.yml)
- [Workflow de produção](../.github/workflows/release.yml)
- [Metadados do pacote](../pyproject.toml)
- [Documentação de ferramentas do uv](https://docs.astral.sh/uv/concepts/tools/)


