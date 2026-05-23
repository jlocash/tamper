from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import URIRef


class TAMPER(DefinedNamespace):
    """
    DESCRIPTION_EDIT_ME_!

    Generated from: SOURCE_RDF_FILE_EDIT_ME_!
    Date: 2026-05-23 21:36:45.399543
    """

    _NS = Namespace("https://example.org/tamper/core#")

    AddGaussianNoise: URIRef  # Adds gaussian noise to an image.
    AudioAsset: URIRef  # A digital audio file containing one or more audio streams.
    AudioStream: URIRef  # A stream containing audio sample data.
    CompressImage: URIRef  # Applies JPEG compression to an image.
    ImageAsset: URIRef  # A digital image file.
    ImageOperation: URIRef  # An operation that results in the creation of an image.
    MediaAsset: URIRef  # A digital media file such as an image, audio, or video.
    Operation: URIRef  # An operation is a process that results in the creation of a new media asset.
    Stream: URIRef  # A component stream within a media container.
    StreamContainer: URIRef  # A media asset that contains one or more streams (e.g., video or audio files).
    SubtitleStream: URIRef  # A stream containing subtitle or caption data.
    VideoAsset: URIRef  # A digital video file containing video and potentially audio streams.
    VideoStream: URIRef  # A stream containing video frame data.
    bitDepth: URIRef  # The number of bits per pixel channel.
    bitRate: URIRef  # The bit rate of the stream in bits per second.
    bitsPerSample: URIRef  # The number of bits per audio sample.
    channels: URIRef  # The number of audio channels.
    checksum: URIRef  # The checksum of the media file, formatted as "algorithm:checksum" (e.g "sha256:5e70b96ad27dc8581424be7069ee9de8da9388b716e6fe213d88385f19baf80a").
    codec: URIRef  # The codec used to encode the stream (e.g., 'h264', 'aac', 'mp3').
    colorSpace: URIRef  # The color space of the visual data (e.g., 'sRGB', 'bt709', 'bt2020').
    containerFormat: URIRef  # The container format name (e.g., 'MPEG-4', 'Matroska', 'FLAC').
    duration: URIRef  # The temporal duration of the media.
    filePath: URIRef  # The relative path to the media file.
    fileSize: URIRef  # The size of the media file in bytes.
    frameRate: URIRef  # The frame rate in frames per second.
    gaussianMean: URIRef  # 
    gaussianStd: URIRef  # 
    hasStream: URIRef  # Relates a stream container to its constituent streams.
    height: URIRef  # The height in pixels.
    language: URIRef  # The ISO 639 language code for the stream content.
    mediaType: URIRef  # The MIME type of the media asset (e.g., 'image/jpeg', 'video/mp4').
    pixelFormat: URIRef  # The pixel format (e.g., 'yuv420p', 'rgb24').
    qualityFactor: URIRef  # JPEG compression quality factor (0 - 100)
    sampleRate: URIRef  # The audio sample rate in Hertz.
    streamIndex: URIRef  # The zero-based index of the stream within its container.
    width: URIRef  # The width in pixels.
