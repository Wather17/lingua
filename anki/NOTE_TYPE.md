# Tipo de nota `Lingua Kindle`

No Anki Desktop, abra **Ferramentas → Gerenciar tipos de notas**, crie um tipo chamado `Lingua Kindle` e adicione os campos abaixo, exatamente nesta ordem:

1. `CardID`
2. `English`
3. `Portuguese`
4. `Vocabulary`
5. `Grammar`
6. `Source`
7. `Audio`

A oitava coluna do TSV não é um campo da nota: a diretiva `#tags column:8` faz o Anki consumi-la diretamente como tags nativas.

## Frente

```html
<div class="sentence">{{English}}</div>
<div class="audio">{{Audio}}</div>
```

## Verso

```html
{{FrontSide}}
<hr id="answer">
<div class="translation">{{Portuguese}}</div>

{{#Vocabulary}}
<section>
  <h3>Vocabulário</h3>
  <div>{{Vocabulary}}</div>
</section>
{{/Vocabulary}}

{{#Grammar}}
<section>
  <h3>Gramática</h3>
  <div>{{Grammar}}</div>
</section>
{{/Grammar}}

{{#Source}}
<div class="source">{{Source}}</div>
{{/Source}}
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
.audio { margin-top: 12px; }
.translation { font-size: 1.1em; }
section { margin-top: 20px; }
h3 {
  color: #80643f;
  font-family: system-ui, sans-serif;
  font-size: .75em;
  letter-spacing: .08em;
  margin-bottom: 6px;
  text-transform: uppercase;
}
.source {
  color: #777067;
  font-family: system-ui, sans-serif;
  font-size: .68em;
  margin-top: 28px;
}
```

## Importação e áudio

1. Importe o TSV gerado em `exports/`. As diretivas do arquivo selecionam o deck, tipo de nota, separador e coluna de tags.
2. Confirme que cada coluna foi associada ao campo de mesmo nome.
3. No navegador de cartões, selecione as novas notas.
4. No HyperTTS, use `English` como origem, `Audio` como destino e escolha uma voz `en-US`.
5. Gere apenas para campos de áudio vazios, para não substituir arquivos existentes.
