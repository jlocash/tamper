import hashlib
import shutil
from os import PathLike
from pathlib import Path

import ffmpeg
from magic import Magic
from rdflib import PROV, XSD, BNode, Graph, URIRef, RDF, Literal
from tamper.core._common import MappedProperty
from tamper.vocabularies import TAMPER
from PIL import Image as PILImage
from ._common import Resource


magic = Magic(mime=True)


def get_file_sha256(path: PathLike[str]):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _get_frame_rate(stream_data: dict) -> float | None:
    frame_rate_str = stream_data.get("r_frame_rate")
    if not frame_rate_str or frame_rate_str == "0/0":
        frame_rate_str = stream_data.get("avg_frame_rate")

    if frame_rate_str and frame_rate_str != "0/0":
        try:
            num, den = map(int, frame_rate_str.split("/"))
            if den != 0:
                return num / den
        except ValueError, ZeroDivisionError:
            pass

    return None


def _extract_container_metadata(asset: StreamContainer):
    probe_result = ffmpeg.probe(asset.file_path)

    format_long_name = probe_result.get("format", {}).get("format_long_name")
    if format_long_name is not None:
        asset.container_format = format_long_name

    for stream_data in probe_result["streams"]:
        stream_uri = BNode()
        stream = Stream.new(asset.graph, stream_uri)

        stream.stream_index = stream_data["index"]
        if "codec_name" in stream_data:
            stream.codec = stream_data["codec_name"]
        if "bit_rate" in stream_data:
            stream.bit_rate = int(stream_data["bit_rate"])
        if "tags" in stream_data and "language" in stream_data["tags"]:
            stream.language = stream_data["tags"]["language"]

        if stream_data["codec_type"] == "video":
            stream = VideoStream.new(stream.graph, stream_uri)
            if "width" in stream_data:
                stream.width = int(stream_data["width"])
            if "height" in stream_data:
                stream.height = int(stream_data["height"])
            if "pix_fmt" in stream_data:
                stream.pixel_format = stream_data["pix_fmt"]
            if "bits_per_raw_sample" in stream_data:
                stream.bit_depth = int(stream_data["bits_per_raw_sample"])

            frame_rate = _get_frame_rate(stream_data)
            if frame_rate is not None:
                stream.frame_rate = frame_rate
            # TODO: color space
            # TODO: bit depth

        elif stream_data["codec_type"] == "audio":
            stream = AudioStream.new(stream.graph, stream_uri)
            if "sample_rate" in stream_data:
                stream.sample_rate = int(stream_data["sample_rate"])
            if "channels" in stream_data:
                stream.channels = int(stream_data["channels"])
            if "bits_per_sample" in stream_data:
                stream.bit_depth = int(stream_data["bits_per_sample"])

        asset.add(TAMPER.hasStream, stream)


def _extract_image_metadata(asset: ImageAsset):
    with PILImage.open(asset.file_path) as img:
        asset.width = img.width
        asset.height = img.height
        asset.pixel_format = img.mode


class MediaAsset(Resource):
    __rdf_type__ = TAMPER.MediaAsset
    media_type: MappedProperty[str] = MappedProperty(TAMPER.mediaType, XSD.string)
    checksum: MappedProperty[str] = MappedProperty(TAMPER.checksum, XSD.string)
    file_path: MappedProperty[PathLike[str]] = MappedProperty(
        TAMPER.filePath, XSD.string
    )
    was_generated_by: MappedProperty[URIRef] = MappedProperty(PROV.wasGeneratedBy)

    def move_file(self, new_path: PathLike[str]):
        new_path = Path(new_path)
        current_path = Path(self.file_path)
        if current_path is None:
            raise ValueError("Asset does not have a local file path")
        if not current_path.exists():
            raise ValueError(f"Asset file {current_path} does not exist")
        if current_path == new_path:
            return
        shutil.move(current_path, new_path)
        self.set(TAMPER.filePath, Literal(str(new_path.absolute())))

    @classmethod
    def from_file(cls, graph: Graph, file: PathLike[str]):
        media_type = magic.from_file(file)
        checksum = get_file_sha256(file)
        asset_uri = URIRef(f"asset://{checksum}")
        asset = cls.new(graph, asset_uri)
        asset = MediaAsset.new(graph, asset_uri)
        asset.media_type = media_type
        asset.checksum = "sha256:" + checksum
        asset.file_path = str(Path(file).absolute())
        return asset


class ImageAsset(MediaAsset):
    __rdf_type__ = TAMPER.ImageAsset
    width: MappedProperty[int] = MappedProperty(TAMPER.width, XSD.integer)
    height: MappedProperty[int] = MappedProperty(TAMPER.height, XSD.integer)
    pixel_format: MappedProperty[str] = MappedProperty(TAMPER.pixelFormat, XSD.string)

    @classmethod
    def from_file(cls, graph: Graph, file: PathLike[str]):
        asset = super().from_file(graph, file)
        if not asset.media_type.startswith("image/"):
            raise ValueError(f"Expected iamge file, got {asset.media_type}")
        asset = cls.new(asset.graph, asset.identifier)
        _extract_image_metadata(asset)
        return asset


class Stream(Resource):
    __rdf_type__ = TAMPER.Stream
    stream_index: MappedProperty[int] = MappedProperty(TAMPER.streamIndex, XSD.integer)
    codec: MappedProperty[int] = MappedProperty(TAMPER.codec, XSD.string)
    bit_rate: MappedProperty[int] = MappedProperty(TAMPER.bitRate, XSD.integer)
    language: MappedProperty[str] = MappedProperty(TAMPER.language, XSD.string)


class AudioStream(Stream):
    __rdf_type__ = TAMPER.AudioStream
    sample_rate: MappedProperty[int] = MappedProperty(TAMPER.sampleRate, XSD.integer)
    channels: MappedProperty[int] = MappedProperty(TAMPER.channels, XSD.integer)
    bit_depth: MappedProperty[int] = MappedProperty(TAMPER.bitDepth, XSD.integer)


class VideoStream(Stream):
    __rdf_type__ = TAMPER.VideoStream
    width: MappedProperty[int] = MappedProperty(TAMPER.width, XSD.integer)
    height: MappedProperty[int] = MappedProperty(TAMPER.height, XSD.integer)
    pixel_format: MappedProperty[str] = MappedProperty(TAMPER.pixelFormat, XSD.string)
    bit_depth: MappedProperty[int] = MappedProperty(TAMPER.bitDepth, XSD.integer)
    frame_rate: MappedProperty[float] = MappedProperty(TAMPER.frameRate, XSD.double)


class StreamContainer(MediaAsset):
    __rdf_type__ = TAMPER.StreamContainer
    _streams: list[AudioStream | VideoStream] = None

    container_format: MappedProperty[str] = MappedProperty(
        TAMPER.containerFormat, XSD.string
    )

    @property
    def streams(self) -> list[AudioStream | VideoStream]:
        if self._streams is None:
            streams = []
            for stream in self.objects(TAMPER.hasStream):
                if (stream.identifier, RDF.type, TAMPER.VideoStream) in self.graph:
                    streams.append(VideoStream(self.graph, stream.identifier))
                elif (stream.identifier, RDF.type, TAMPER.AudioStream) in self.graph:
                    streams.append(AudioStream(self.graph, stream.identifier))
            self._streams = sorted(streams, key=lambda s: s.stream_index)
        return self._streams

    def has_video(self) -> bool:
        return any(isinstance(s, VideoStream) for s in self.streams)

    def has_audio(self) -> bool:
        return any(isinstance(s, AudioStream) for s in self.streams)


class VideoAsset(StreamContainer):
    __rdf_type__ = TAMPER.VideoAsset

    @classmethod
    def from_file(cls, graph: Graph, file: PathLike[str]):
        asset = super().from_file(graph, file)
        if not asset.media_type.startswith("video/"):
            raise ValueError(f"Expected video file, got {asset.media_type}")

        asset = cls.new(asset.graph, asset.identifier)
        _extract_container_metadata(asset)
        return asset


class AudioAsset(StreamContainer):
    __rdf_type__ = TAMPER.AudioAsset

    @classmethod
    def from_file(cls, graph: Graph, file: PathLike[str]):
        asset = super().from_file(graph, file)
        if not asset.media_type.startswith("audio/"):
            raise ValueError(f"Expected audio file, got {asset.media_type}")

        asset = cls.new(asset.graph, asset.identifier)
        _extract_container_metadata(asset)
        return asset


def load_asset_from_file(g: Graph, asset_file: PathLike[str]) -> MediaAsset:
    media_type = magic.from_file(asset_file)

    if media_type.startswith("image/"):
        return ImageAsset.from_file(g, asset_file)
    elif media_type.startswith("audio/"):
        return AudioAsset.from_file(g, asset_file)
    elif media_type.startswith("video/"):
        return VideoAsset.from_file(g, asset_file)
    else:
        raise ValueError(f"Unknown media type: {media_type}")


__all__ = [
    "MediaAsset",
    "ImageAsset",
    "StreamContainer",
    "Stream",
    "AudioStream",
    "VideoStream",
    "AudioAsset",
    "VideoAsset",
    "load_asset_from_file",
]
