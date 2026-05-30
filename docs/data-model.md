# The Data Model

See also: [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/)

The underlying data model is an RDF knowledge graph. Tamper is at its core an
ontology for expressing the relationships between multimedia asset files.

Every file is described as an **asset** with a content-addressed identifier
(`asset://<sha256>`), its media type, and technical metadata. The identifier is
a hash of the file's contents, so identical files always share the same id.

Audio and video files are **containers**: they hold one or more _streams_ (for
example, a video track plus an audio track). Tamper describes each contained
stream separately via `tamper:hasStream`, using the blank-node (`[ ... ]`) form
to nest a stream inside its asset.

All terms below come from the core vocabulary, abbreviated by the `tamper:`
prefix:

```turtle
@prefix tamper: <https://example.org/tamper/core#> .
```

## Image

```turtle
<asset://aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e> a tamper:ImageAsset ;
    tamper:checksum "sha256:aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e" ;
    tamper:height 566 ;
    tamper:mediaType "image/png" ;
    tamper:pixelFormat "PNG" ;
    tamper:width 850 .
```

## Audio

```turtle
<asset://0362a64f6c0dcb7347b4af8bb22828d765912d58a8becea58ff610460cd8396b> a tamper:AudioAsset ;
    tamper:checksum "sha256:0362a64f6c0dcb7347b4af8bb22828d765912d58a8becea58ff610460cd8396b" ;
    tamper:mediaType "audio/mpeg" ;
    tamper:hasStream [
        a tamper:AudioStream ;
        tamper:bitDepth 0 ;
        tamper:bitRate 320000 ;
        tamper:channels 2 ;
        tamper:codec "mp3" ;
        tamper:sampleRate 44100 ;
        tamper:streamIndex 0 ;
    ] .
```

## Video

A video asset carries one stream per track — here a VP8 video stream and a
Vorbis audio stream:

```turtle
<asset://c1a8ec81bcf8641f4801e59948ef6e55cc4be8e15a909a417ebb40010119e0d3> a tamper:VideoAsset ;
    tamper:checksum "sha256:c1a8ec81bcf8641f4801e59948ef6e55cc4be8e15a909a417ebb40010119e0d3" ;
    tamper:mediaType "video/webm" ;
    tamper:hasStream [
        a tamper:VideoStream ;
        tamper:codec "vp8" ;
        tamper:frameRate 30.0 ;
        tamper:height 720 ;
        tamper:pixelFormat "yuv420p" ;
        tamper:streamIndex 0 ;
        tamper:width 1280 ;
    ], [
        a tamper:AudioStream ;
        tamper:bitDepth 0 ;
        tamper:channels 2 ;
        tamper:codec "vorbis" ;
        tamper:sampleRate 48000 ;
        tamper:streamIndex 1 ;
    ] .
```
