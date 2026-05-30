# Operations

See also: [RDF 1.1 Primer](https://www.w3.org/TR/rdf11-primer/)

Operations are the media transformations a [plan](../README.md#operation-plans)
runs at each step — compress, resize, blur, add noise, transcode. Each entry in
this reference shows the operation's parameters, their value ranges, and a Turtle
example.

An operation is written as a _typed node_: the `tamper:` class (after `a`) names
the transformation, and the `tamper:` properties carry its parameters. Here, a
JPEG compression at quality 90:

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:CompressJPEG ;
    tamper:qualityFactor 90 .
```

That's the form used in this reference. **Inside a plan**, though, the operation
is wrapped slightly differently: a step references it through a
`plan:OperationParameters` bundle, which names the operation with
`plan:operationType` (an object property — _not_ `rdf:type`, so no `a`) and then
lists the same parameters:

```turtle
@prefix plan:   <https://example.org/tamper/plan#> .
@prefix tamper: <https://example.org/tamper/core#> .

[] a plan:OperationParameters ;
    plan:operationType tamper:CompressJPEG ;
    tamper:qualityFactor 90 .
```

In short: the parameters are identical either way — only the wrapper changes.
The examples in each section below use the standalone form for brevity.

Every parameter marked **required** must be present, or the step fails when it
runs. Image operations accept any raster format OpenCV can decode; the output
keeps the input file's extension (defaulting to `.png`).

## Image operations

### CompressJPEG — `tamper:CompressJPEG`

Re-encodes the image as JPEG at a given quality.

| Parameter      | Property               | Type    | Constraint | Required |
| -------------- | ---------------------- | ------- | ---------- | -------- |
| quality factor | `tamper:qualityFactor` | integer | `0`–`100`  | yes      |

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:CompressJPEG ;
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

```turtle
@prefix tamper: <https://example.org/tamper/core#> .

[] a tamper:AddGaussianNoise ;
    tamper:gaussianMean 0.0 ;
    tamper:gaussianStd 12.0 .
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
