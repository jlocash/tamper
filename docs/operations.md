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

## Video operations

### TranscodeVideo — `tamper:TranscodeVideo`

Re-encodes the video's stream(s) with ffmpeg. Audio streams are copied
through unchanged; the container format is preserved.

| Parameter     | Property              | Type                 | Constraint                                    | Required |
| ------------- | --------------------- | -------------------- | --------------------------------------------- | -------- |
| video encoder | `tamper:videoEncoder` | string               | non-empty (an ffmpeg encoder, e.g. `libx264`) | yes      |
| CRF           | `tamper:crf`          | non-negative integer | `0`–`63`                                      | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:TranscodeVideo ;
    tamper:videoEncoder "libx264" ;
    tamper:crf 23 .
```

## Audio operations

### TranscodeAudio — `tamper:TranscodeAudio`

Re-encodes the audio stream with ffmpeg using a given encoder and target bit
rate. Any video stream (e.g. cover art) is copied through unchanged; the
container format is preserved.

| Parameter       | Property               | Type             | Constraint                                       | Required |
| --------------- | ---------------------- | ---------------- | ------------------------------------------------ | -------- |
| audio encoder   | `tamper:audioEncoder`  | string           | non-empty (an ffmpeg encoder, e.g. `libmp3lame`) | yes      |
| target bit rate | `tamper:targetBitRate` | positive integer | bits per second, `> 0`                           | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:TranscodeAudio ;
    tamper:audioEncoder "libmp3lame" ;
    tamper:targetBitRate 64000 .
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
