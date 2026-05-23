from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import URIRef


class TAMPER(DefinedNamespace):
    """
    DESCRIPTION_EDIT_ME_!

    Generated from: SOURCE_RDF_FILE_EDIT_ME_!
    Date: 2026-05-21 22:52:15.906073
    """

    _NS = Namespace("https://example.org/tamper/core#")

    AudioAsset: URIRef  # A digital audio file containing one or more audio streams.
    AudioStream: URIRef  # A stream containing audio sample data.
    ImageAsset: URIRef  # A digital image file.
    MediaAsset: URIRef  # A digital media file such as an image, audio, or video.
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
    fileSize: URIRef  # The size of the media file in bytes.
    frameRate: URIRef  # The frame rate in frames per second.
    hasStream: URIRef  # Relates a stream container to its constituent streams.
    height: URIRef  # The height in pixels.
    language: URIRef  # The ISO 639 language code for the stream content.
    mediaType: URIRef  # The MIME type of the media asset (e.g., 'image/jpeg', 'video/mp4').
    pixelFormat: URIRef  # The pixel format of the video stream (e.g., 'yuv420p', 'rgb24').
    sampleRate: URIRef  # The audio sample rate in Hertz.
    streamIndex: URIRef  # The zero-based index of the stream within its container.
    width: URIRef  # The width in pixels.
