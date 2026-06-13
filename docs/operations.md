# Operations

See also: [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/)

Operations are processes that result in the creation of new media assets. They are
executed as steps in an [operation plan](../README.md#operation-plans). This
document provides a reference of each operation Tamper supports, its parameters,
their value ranges, and a Turtle example.

Operation types are prefixed by the `tamper:` namespace. If a statement in the graph
asserts that a subject is of type `tamper:<operation type>` (e.g `tamper:Compress`),
then that is a statement of fact. The graph is saying that the operation _actually happened_.
Operations represent provenance activities, not specifications for future execution.

Here, a JPEG compression at quality 90:

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:Compress ;
    tamper:format "jpeg" ;
    tamper:qualityFactor 90 .
```

This reads: _"A JPEG compression operation occurred, with a quality factor of 90"_

To instruct Tamper to actually run a new operation, an `plan:OperationParameters` may
be defined as part of a `plan:Step` in an operation plan:

```turtle
@prefix plan:   <https://example.org/tamper/plan#> .
@prefix tamper: <https://example.org/tamper/core#> .

[] a plan:Step ;
    plan:operationType tamper:Compress ;
    plan:parameters [
        tamper:format "jpeg" ;
        tamper:qualityFactor 90 ;
    ] .
```

Every parameter marked **required** must be present, or the step fails when it
runs.

## Image operations

### Compress — `tamper:Compress`

Re-encodes the image as JPEG at a given quality.

| Parameter      | Property               | Type    | Constraint             | Required |
| -------------- | ---------------------- | ------- | ---------------------- | -------- |
| format         | `tamper:format`        | string  | one of `jpeg`, `webp`) | yes      |
| quality factor | `tamper:qualityFactor` | integer | `0`–`100`              | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:Compress ;
    tamper:format "jpeg" ;
    tamper:qualityFactor 90 .
```

### Resize — `tamper:Resize`

Resizes the image to exact pixel dimensions.

| Parameter     | Property               | Type             | Constraint                                              | Required |
| ------------- | ---------------------- | ---------------- | ------------------------------------------------------- | -------- |
| width         | `tamper:targetWidth`   | positive integer | `> 0`                                                   | yes      |
| height        | `tamper:targetHeight`  | positive integer | `> 0`                                                   | yes      |
| interpolation | `tamper:interpolation` | string           | one of `nearest`, `linear`, `cubic`, `area`, `lanczos4` | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:Resize ;
    tamper:targetWidth 640 ;
    tamper:targetHeight 480 ;
    tamper:interpolation "linear" .
```

### MedianFilter — `tamper:MedianFilter`

Applies a median blur over a square neighbourhood.

| Parameter   | Property            | Type             | Constraint  | Required |
| ----------- | ------------------- | ---------------- | ----------- | -------- |
| kernel size | `tamper:kernelSize` | positive integer | odd, `>= 3` | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:MedianFilter ;
    tamper:kernelSize 3 .
```

### GaussianBlur — `tamper:GaussianBlur`

Applies a Gaussian blur over a square kernel.

| Parameter   | Property            | Type             | Constraint                                           | Required |
| ----------- | ------------------- | ---------------- | ---------------------------------------------------- | -------- |
| kernel size | `tamper:kernelSize` | positive integer | odd, `>= 1`                                          | yes      |
| sigma       | `tamper:blurSigma`  | float            | — (`0.0` lets OpenCV derive it from the kernel size) | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:GaussianBlur ;
    tamper:kernelSize 5 ;
    tamper:blurSigma 0.0 .
```

### AddGaussianNoise — `tamper:AddGaussianNoise`

Adds per-pixel Gaussian noise (values are clipped to `0`–`255`).

| Parameter          | Property              | Type  | Constraint | Required |
| ------------------ | --------------------- | ----- | ---------- | -------- |
| mean               | `tamper:gaussianMean` | float | —          | yes      |
| standard deviation | `tamper:gaussianStd`  | float | `>= 0`     | yes      |
| seed               | `tamper:gaussianSeed` | int   | `>= 0`     | no       |

The noise is drawn from a seeded random number generator, so a given seed
always produces identical output. If `tamper:gaussianSeed` is omitted, a seed
is generated automatically and recorded into the result graph, keeping the run
reproducible and self-documenting.

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:AddGaussianNoise ;
    tamper:gaussianMean 0.0 ;
    tamper:gaussianStd 12.0 .
```

### CropImage — `tamper:CropImage`

Extracts a rectangular region from the image, given a top-left origin
(`cropX`, `cropY`) and a size (`cropWidth`, `cropHeight`). The crop region must
lie within the image bounds, or the step fails when it runs.

| Parameter | Property            | Type                 | Constraint | Required |
| --------- | ------------------- | -------------------- | ---------- | -------- |
| x         | `tamper:cropX`      | non-negative integer | `>= 0`     | yes      |
| y         | `tamper:cropY`      | non-negative integer | `>= 0`     | yes      |
| width     | `tamper:cropWidth`  | positive integer     | `> 0`      | yes      |
| height    | `tamper:cropHeight` | positive integer     | `> 0`      | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:CropImage ;
    tamper:cropX 100 ;
    tamper:cropY 50 ;
    tamper:cropWidth 640 ;
    tamper:cropHeight 480 .
```

## Audio and video operations

These operations act on audio or video assets (stream containers).

### Transcode — `tamper:Transcode`

Re-encodes the audio stream, the video stream, or both, of an audio or video
asset with ffmpeg. By default, the streams are copied unless an encoder is given, and the source container format is preserved (unless the output
is audio-only). At least one of `tamper:audioEncoder` or `tamper:videoEncoder`
must be given.

| Parameter       | Property               | Type                 | Constraint                                                       | Required |
| --------------- | ---------------------- | -------------------- | --------------------------------------------------------------- | -------- |
| video encoder   | `tamper:videoEncoder`  | string               | an ffmpeg encoder, e.g. `libx264`                               | one of † |
| CRF             | `tamper:crf`           | non-negative integer | `>= 0`; only meaningful alongside a video encoder               | no       |
| audio encoder   | `tamper:audioEncoder`  | string               | an ffmpeg encoder, e.g. `libmp3lame`                            | one of † |
| target bit rate | `tamper:targetBitRate` | positive integer     | bits per second, `> 0`; only meaningful alongside an audio encoder | no       |

† At least one of `tamper:videoEncoder` or `tamper:audioEncoder` is required.
Supplying `tamper:crf` without a video encoder, or `tamper:targetBitRate`
without an audio encoder, is rejected.

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

# Re-encode the video stream to H.264; copy the audio stream through unchanged.
[] a tamper:Transcode ;
    tamper:videoEncoder "libx264" ;
    tamper:crf 23 .

# Re-encode the audio stream to MP3; copy any video stream through unchanged.
[] a tamper:Transcode ;
    tamper:audioEncoder "libmp3lame" ;
    tamper:targetBitRate 64000 .

# Re-encode both streams.
[] a tamper:Transcode ;
    tamper:videoEncoder "libx264" ;
    tamper:crf 23 ;
    tamper:audioEncoder "aac" ;
    tamper:targetBitRate 128000 .
```

### ResampleAudio — `tamper:ResampleAudio`

Resamples the audio stream to a target sample rate with ffmpeg. The audio
codec and container format are preserved.

| Parameter          | Property                  | Type             | Constraint      | Required |
| ------------------ | ------------------------- | ---------------- | --------------- | -------- |
| target sample rate | `tamper:targetSampleRate` | positive integer | in Hertz, `> 0` | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:ResampleAudio ;
    tamper:targetSampleRate 8000 .
```
