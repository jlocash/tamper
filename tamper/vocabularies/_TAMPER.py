from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import URIRef


class TAMPER(DefinedNamespace):
    """
    DESCRIPTION_EDIT_ME_!

    Generated from: SOURCE_RDF_FILE_EDIT_ME_!
    Date: 2026-06-14 02:07:58.350639
    """

    _NS = Namespace("https://example.org/tamper/core#")

    AddGaussianNoise: URIRef  # Adds gaussian noise to an image.
    AudioAsset: URIRef  # A digital audio file containing one or more audio streams.
    AudioStream: URIRef  # A stream containing audio sample data.
    Compress: URIRef  # Applies compression to an image using a format and quality level
    Crop: URIRef  # Extracts a rectangular region from a media asset, given a top-left origin and a width and height.
    GaussianBlur: URIRef  # Convolves an image with a Gaussian kernel of a given size and standard deviation.
    ImageAsset: URIRef  # A digital image file.
    MediaAsset: URIRef  # A digital media file such as an image, audio, or video.
    MedianFilter: URIRef  # Applies a median filter over a square neighbourhood, commonly used to suppress noise residuals.
    Operation: URIRef  # An operation is a process that results in the creation of a new media asset.
    Resample: URIRef  # Resamples the audio stream of an asset to a target sample rate.
    Resize: URIRef  # Resamples an image to a target width and height using a specified interpolation method.
    Stream: URIRef  # A component stream within a media container.
    StreamContainer: URIRef  # A media asset that contains one or more streams (e.g., video or audio files).
    SubtitleStream: URIRef  # A stream containing subtitle or caption data.
    Transcode: URIRef  # Re-encodes a video or audio stream using the specified encoder(s) and quality (CRF). Streams are copied by default if an encoder is not given.
    VideoAsset: (
        URIRef  # A digital video file containing video and potentially audio streams.
    )
    VideoStream: URIRef  # A stream containing video frame data.
    audioEncoder: URIRef  # The name of the audio encoder used for transcoding (e.g., 'libmp3lame', 'aac', 'libopus').
    bitDepth: URIRef  # The number of bits per pixel channel.
    bitRate: URIRef  # The bit rate of the stream in bits per second.
    bitsPerSample: URIRef  # The number of bits per audio sample.
    blurSigma: URIRef  # The Gaussian kernel standard deviation. A value of 0 lets the implementation derive it from the kernel size.
    channels: URIRef  # The number of audio channels.
    checksum: URIRef  # The checksum of the media file, formatted as "algorithm:checksum" (e.g "sha256:5e70b96ad27dc8581424be7069ee9de8da9388b716e6fe213d88385f19baf80a").
    codec: URIRef  # The codec used to encode the stream (e.g., 'h264', 'aac', 'mp3').
    colorSpace: (
        URIRef  # The color space of the visual data (e.g., 'sRGB', 'bt709', 'bt2020').
    )
    containerFormat: (
        URIRef  # The container format name (e.g., 'MPEG-4', 'Matroska', 'FLAC').
    )
    crf: URIRef  # Constant Rate Factor — a perceptual-quality target for the encoder. Lower values mean higher quality and larger file size; 0 is lossless on x264.
    cropHeight: URIRef  # The height in pixels of the crop region.
    cropWidth: URIRef  # The width in pixels of the crop region.
    cropX: URIRef  # The x coordinate, in pixels, of the top-left corner of the crop region.
    cropY: URIRef  # The y coordinate, in pixels, of the top-left corner of the crop region.
    duration: URIRef  # The temporal duration of the media.
    filePath: URIRef  # The relative path to the media file.
    fileSize: URIRef  # The size of the media file in bytes.
    format: URIRef  # compression format (e.g 'webp', 'jpeg')
    frameRate: URIRef  # The frame rate in frames per second.
    gaussianMean: URIRef  #
    gaussianSeed: URIRef  # The seed for the random number generator used to draw the noise, recorded so the operation is exactly reproducible.
    gaussianStd: URIRef  #
    hasStream: URIRef  # Relates a stream container to its constituent streams.
    height: URIRef  # The height in pixels.
    interpolation: URIRef  # The interpolation method used when resampling (e.g., 'nearest', 'linear', 'cubic', 'area', 'lanczos4').
    kernelSize: URIRef  # The side length, in pixels, of the square convolution kernel. Must be a positive odd integer.
    language: URIRef  # The ISO 639 language code for the stream content.
    mediaType: (
        URIRef  # The MIME type of the media asset (e.g., 'image/jpeg', 'video/mp4').
    )
    pixelFormat: URIRef  # The pixel format (e.g., 'yuv420p', 'rgb24').
    qualityFactor: URIRef  # Image compression quality factor (0 - 100)
    sampleRate: URIRef  # The audio sample rate in Hertz.
    streamIndex: URIRef  # The zero-based index of the stream within its container.
    targetBitRate: URIRef  # The target bit rate in bits per second for an audio transcode operation.
    targetHeight: URIRef  # The target height in pixels for a resize operation.
    targetSampleRate: (
        URIRef  # The target sample rate in Hertz for an audio resample operation.
    )
    targetWidth: URIRef  # The target width in pixels for a resize operation.
    videoEncoder: URIRef  # The name of the video encoder used for transcoding (e.g., 'libx264', 'libx265', 'libvpx-vp9').
    width: URIRef  # The width in pixels.
