# An RDF Primer

Tamper describes files using **RDF** (Resource Description Framework), written in
a text format called **Turtle**. You don't need to know RDF to use Tamper, but
five ideas are enough to read every example in these docs. If you've written JSON
or YAML, the syntax will look familiar.

### 1. Everything is a *triple*: subject → predicate → object

RDF describes the world as simple statements of the form **subject, predicate,
object** — like "this image *has width* 850". Each statement is one fact:

```turtle
<asset://abc123> tamper:width 850 .
```

Read it as: *the thing `asset://abc123`* (subject) *has a width* (predicate) *of
850* (object). The trailing `.` ends the statement.

### 2. The semicolon `;` chains facts about the same subject

A `;` avoids repeating the subject; it introduces more facts about the same
subject:

```turtle
<asset://abc123> tamper:width 850 ;
    tamper:height 566 ;
    tamper:mediaType "image/png" .
```

That's three facts about one image: its width, height, and media type. A `,`
(comma) similarly repeats both the subject *and* predicate, listing several
objects for the same property.

### 3. `a` means "is a" (the type)

`a` is shorthand for "is of type". This line says the subject is an image asset:

```turtle
<asset://abc123> a tamper:ImageAsset .
```

(`a` is just sugar for the predicate `rdf:type`.)

### 4. Prefixes are abbreviations for long names

Every RDF name is really a full URL, which would be unwieldy to repeat. A
`@prefix` line defines a short alias so you can write `tamper:width` instead of
`<https://example.org/tamper/core#width>`:

```turtle
@prefix tamper: <https://example.org/tamper/core#> .
```

Tamper uses three prefixes:

| Prefix | Stands for | Used for |
|--------|-----------|----------|
| `tamper:` | `https://example.org/tamper/core#` | assets, operations, and their properties |
| `plan:` | `https://example.org/tamper/plan#` | operation plans (steps, variables) |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | human-readable labels |

### 5. Square brackets `[]` are an anonymous nested thing

Sometimes you need a sub-object that doesn't need its own name — like a single
audio stream inside a file. `[ ... ]` is a **blank node**: an inline, unnamed
subject. It's the RDF equivalent of an anonymous object literal:

```turtle
<asset://abc123> tamper:hasStream [
    a tamper:AudioStream ;
    tamper:channels 2
] .
```

That reads: *the asset has a stream, which is an audio stream with 2 channels*.

---

That's everything you need to read Tamper's examples. When you're ready to go
deeper, the [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/) and the
[Turtle specification](https://www.w3.org/TR/turtle/) are the authoritative
references.

Next: see [the data model](data-model.md) for how real files are described, or
the [README](../README.md#operation-plans) for how to transform them.
