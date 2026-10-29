# Tipo de nota `Lingua ChatGPT`

Crie no Anki um tipo de nota chamado `Lingua ChatGPT` com somente estes campos, nesta ordem:

1. `English`
2. `Portuguese`

## Frente

```html
<div class="sentence">{{English}}</div>
```

## Verso

```html
{{FrontSide}}
<hr id="answer">
<div class="translation">{{Portuguese}}</div>
```

## Estilo

```css
.card {
  background: #f7f3ea;
  color: #26231f;
  font-family: Georgia, serif;
  font-size: 20px;
  line-height: 1.5;
  margin: 0 auto;
  max-width: 760px;
  padding: 24px;
  text-align: left;
}

.sentence { font-size: 1.25em; }
.translation { font-size: 1.1em; }
```

## Importação

1. Salve a resposta crua da skill como um arquivo `.tsv`.
2. No Anki, selecione o separador **Tabulação**.
3. Associe a primeira coluna a `English` e a segunda a `Portuguese`.
4. Ative a interpretação de HTML para que `<br>` separe a tradução de uma nota opcional.

O arquivo não tem cabeçalho nem diretivas de importação. Não adicione colunas extras.
