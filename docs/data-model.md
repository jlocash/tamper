# The Data Model

See also: [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/)

The underlying data model is an RDF knowledge graph. Every file is described as 
an **asset** with a content-addressed identifier
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

The `tamper.core` module provides classes that wrap an `rdflib.Graph` instance and provide 
accessor fields to make interacting with the graph easy.

## Image

```python
from tamper.core import ImageAsset
from rdflib import Graph

ctx = Graph()
img = ImageAsset.from_file(ctx, "/path/to/image.png")

# Each field is mapped to a property in the graph
assert img.media_type == "image/png"
assert img.checksum == "sha256:aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e"
assert img.file_path == "/path/to/image.png"
assert img.width == 850
assert img.height == 566
assert img.pixel_format == "RGB"

ctx.print(format="turtle")
```

```turtle
<asset://aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e> a tamper:ImageAsset ;
    tamper:checksum "sha256:aad96d410d92b5589d41e8462507e3af57682022db3d3711a236c0245fcf296e" ;
    tamper:height 566 ;
    tamper:filePath "/path/to/image.png" ;
    tamper:mediaType "image/png" ;
    tamper:pixelFormat "RGB" ;
    tamper:width 850 .
```

## Audio

Audio assets are stream containers. Metadata is sourced using FFmpeg.

```python
from tamper.core import AudioAsset
from rdflib import Graph

ctx = Graph()
audio_asset = AudioAsset.from_file(ctx, "/path/to/audio.wav")

# Again, fields are mapped to properties in the graph
assert audio_asset.media_type == "audio/mpeg"
assert audio_asset.checksum == "sha256:0362a64f6c0dcb7347b4af8bb22828d765912d58a8becea58ff610460cd8396b"
assert audio_asset.file_path == "/path/to/audio.wav"
assert audio_asset.container_format == "WAV / WAVE (Waveform Audio)"
assert audio_asset.streams[0].stream_index == 0
assert audio_asset.streams[0].codec == "mp3"
assert audio_asset.streams[0].bit_rate == 320000
assert audio_asset.streams[0].bit_depth == 0
assert audio_asset.streams[0].channels == 2
assert audio_asset.streams[0].sample_rate == 44100

ctx.print(format="turtle")
```

```turtle
<asset://0362a64f6c0dcb7347b4af8bb22828d765912d58a8becea58ff610460cd8396b> a tamper:AudioAsset ;
    tamper:checksum "sha256:0362a64f6c0dcb7347b4af8bb22828d765912d58a8becea58ff610460cd8396b" ;
    tamper:mediaType "audio/mpeg" ;
    tamper:filePath "/path/to/audio.wav" ;
    tamper:containerFormat "WAV / WAVE (Waveform Audio)" ;
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
```python
from tamper.core import VideoAsset
from rdflib import Graph

ctx = Graph()

# video_asset is mapped to a `tamper:VideoAsset` in the graph
video_asset = VideoAsset.from_file(ctx, "/path/to/video.mp4")

# We can access its properties like an ordinary Python object
# NOTE: these values are just examples, and will change depending 
# on the media file
assert video_asset.media_type == "video/mp4"
assert video_asset.checksum == "sha256:8ab080c1406dff77f8897955cf977e9ad779e40ab3a07bc2f8694fbd2fc2be21"
assert video_asset.file_path == "/path/to/video.mp4"
assert video_asset.container_format == "QuickTime / MOV"
assert video_asset.streams[0].stream_index == 0
assert video_asset.streams[0].codec == "h264"
assert video_asset.streams[0].width == 1280
assert video_asset.streams[0].height == 720
assert video_asset.streams[0].pixel_format == "yuv420p"
assert video_asset.streams[0].frame_rate == 30.0
assert video_asset.streams[1].stream_index == 1
assert video_asset.streams[1].codec == "aac"
assert video_asset.streams[1].channels == 2
assert video_asset.streams[1].sample_rate == 48000
assert video_asset.streams[1].bit_depth == 0

ctx.print(format="turtle")
```

A video asset carries one stream per track — here a VP8 video stream and a
Vorbis audio stream:

```turtle
<asset://8ab080c1406dff77f8897955cf977e9ad779e40ab3a07bc2f8694fbd2fc2be21> a tamper:VideoAsset ;
    tamper:checksum "sha256:8ab080c1406dff77f8897955cf977e9ad779e40ab3a07bc2f8694fbd2fc2be21" ;
    tamper:containerFormat "QuickTime / MOV" ;
    tamper:filePath "/path/to/video.mp4" ;
    tamper:hasStream [ a tamper:AudioStream ;
            tamper:bitDepth 0 ;
            tamper:bitRate 160000 ;
            tamper:channels 2 ;
            tamper:codec "aac" ;
            tamper:language "und" ;
            tamper:sampleRate 48000 ;
            tamper:streamIndex 1 ],
        [ a tamper:VideoStream ;
            tamper:bitDepth 8 ;
            tamper:bitRate 2453499 ;
            tamper:codec "h264" ;
            tamper:frameRate 3e+01 ;
            tamper:height 720 ;
            tamper:language "und" ;
            tamper:pixelFormat "yuv420p" ;
            tamper:streamIndex 0 ;
            tamper:width 1280 ] .
```
