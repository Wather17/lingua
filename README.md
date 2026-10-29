# Lingua

O Lingua mantém o contrato simples entre frases estudadas, uma skill do ChatGPT e o Anki.

O fluxo não usa API de tradução nem depende de modelos pagos separadamente:

1. Escreva as frases em um JSON com `text` e `source`.
2. Envie o JSON para a skill descrita em [docs/chatgpt-skill.md](docs/chatgpt-skill.md).
3. Salve a resposta TSV exatamente como foi retornada, sem cabeçalho ou bloco Markdown.
4. Importe o arquivo diretamente no Anki usando o tipo de nota descrito em [anki/NOTE_TYPE.md](anki/NOTE_TYPE.md).

## Entrada

O arquivo deve conter somente `entries`. Cada entrada precisa de `text` e `source`, ambos como textos não vazios e de uma única linha:

```json
{
  "entries": [
    {
      "text": "I couldnt quite put my finger on what was wrong.",
      "source": "The Pragmatic Programmer — capítulo 1"
    },
    {
      "text": "That was unexpected.",
      "source": "anotações de leitura"
    }
  ]
}
```

O `source` fornece contexto para a skill. Ele não aparece no cartão.

## Saída

A skill devolve somente duas colunas separadas por tabulação:

```text
English<TAB>Portuguese
```

A primeira coluna preserva exatamente o texto enviado. A segunda contém a tradução em pt-BR e pode conter uma nota curta após `<br>`. O cartão não possui campos adicionais.

## Validação local

Valide o exemplo de entrada e o exemplo de saída com:

```bash
python3 -m json.tool entries.example.json
awk -F '\t' 'NF != 2 || $1 == "" || $2 == "" { bad=1 } END { exit (NR == 0 || bad) }' docs/example-output.tsv
```

O repositório não remove nem gerencia arquivos pessoais como `entries.json`, `drafts/` ou `exports/`.
