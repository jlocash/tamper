# tamper

Tamper is a framework for expressing the relationships between multimedia files.


## The Data Model

The underlying data model is an RDF knowledge graph. Tamper is at its core an ontology that can be used to express the relationships between multimedia asset files.


Image example:
```turtle
@prefix tamper: <https://example.org/tamper/core#> .

<asset://aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e> a tamper:ImageAsset ;
    tamper:checksum "sha256:aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e" ;
    tamper:height 566 ;
    tamper:mediaType "image/png" ;
    tamper:pixelFormat "PNG" ;
    tamper:width 850 .
```


Audio example:
```turtle
@prefix tamper: <https://example.org/tamper/core#> .

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

Video example:
```turtle
@prefix tamper: <https://example.org/tamper/core#> .

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

## MCP Server

### Install dependencies
```shell
# Initialize the environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync
uv pip install -e .
```

### Run directly

```shell
# Define the file where our RDF dataset will live
export TAMPER_HOME=$HOME/.tamper

# Run the MCP server
fastmcp run tamper/app/mcp/server.py --project .   
```

### Install to Claude Code
```shell
fastmcp install claude-code tamper/app/mcp/server.py \
  --project $(pwd) \
  --env TAMPER_HOME=$HOME/.tamper
```
