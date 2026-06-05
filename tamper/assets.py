import hashlib
import shutil
from os import PathLike
from pathlib import Path

import ffmpeg
from magic import Magic
from rdflib import Graph, URIRef, XSD, Node, RDF, Literal
from rdflib.extras.describer import Describer
from rdflib.resource import Resource
from tamper.vocabularies import TAMPER
from PIL import Image as PILImage


def _unwrap_literal(resource: Resource, predicate: Node):
    value = resource.value(predicate)
    if isinstance(value, Literal):
        return value.toPython()
    elif value is not None:
        raise ValueError(
            f"Expected value of subject {resource} and predicate {predicate.n3()} to be Literal, got: {type(value)}"
        )


def _unwrap_expect_literal(resource: Resource, predicate: Node):
    value = resource.value(predicate)
    if value is None:
        raise ValueError(
            f"Missing expected value for subject {resource} and predicate {predicate.n3()}"
        )
    if not isinstance(value, Literal):
        raise ValueError(
            f"Expected value of subject {resource} and predicate {predicate.n3()} to be Literal, got: {type(value)}"
        )
    return value.toPython()


class MediaAsset(Resource):
    @property
    def media_type(self) -> str:
        return _unwrap_expect_literal(self, TAMPER.mediaType)

    @property
    def checksum(self) -> str:
        return _unwrap_expect_literal(self, TAMPER.checksum)

    @property
    def file_path(self) -> Path | None:
        val = self.graph.value(self.identifier, TAMPER.filePath)
        if val is not None:
            return Path(str(val))
        return None

    def move_file(self, new_path: PathLike[str]):
        new_path = Path(new_path)
        current_path = self.file_path
        if current_path is None:
            raise ValueError("Asset does not have a local file path")
        if not current_path.exists():
            raise ValueError(f"Asset file {current_path} does not exist")
        if current_path == new_path:
            return
        shutil.move(current_path, new_path)
        self.set(TAMPER.filePath, Literal(str(new_path.absolute())))


class ImageAsset(MediaAsset):
    @property
    def width(self) -> int:
        return _unwrap_expect_literal(self, TAMPER.width)

    @property
    def height(self) -> int:
        return _unwrap_expect_literal(self, TAMPER.height)

    @property
    def pixel_format(self) -> str:
        return _unwrap_expect_literal(self, TAMPER.pixelFormat)


class Stream(Resource):
    @property
    def stream_index(self) -> int:
        return _unwrap_expect_literal(self, TAMPER.streamIndex)

    @property
    def codec(self) -> str | None:
        return _unwrap_literal(self, TAMPER.codec)

    @property
    def bit_rate(self) -> int | None:
        return _unwrap_literal(self, TAMPER.bitRate)

    @property
    def language(self) -> str | None:
        return _unwrap_literal(self, TAMPER.language)


class AudioStream(Stream):
    @property
    def sample_rate(self) -> int | None:
        return _unwrap_literal(self, TAMPER.sampleRate)

    @property
    def channels(self) -> int | None:
        return _unwrap_literal(self, TAMPER.channels)

    @property
    def bit_depth(self) -> int | None:
        return _unwrap_literal(self, TAMPER.bitDepth)


class VideoStream(Stream):
    @property
    def width(self) -> int | None:
        return _unwrap_literal(self, TAMPER.width)

    @property
    def height(self) -> int | None:
        return _unwrap_literal(self, TAMPER.height)

    @property
    def pixel_format(self) -> str | None:
        return _unwrap_literal(self, TAMPER.pixelFormat)

    @property
    def bit_depth(self) -> int | None:
        return _unwrap_literal(self, TAMPER.bitDepth)

    @property
    def frame_rate(self) -> float | None:
        return _unwrap_literal(self, TAMPER.frameRate)


class StreamContainer(MediaAsset):
    _streams: list[AudioStream | VideoStream] = None

    @property
    def streams(self) -> list[AudioStream | VideoStream]:
        if self._streams is None:
            streams = []
            for stream in self.objects(TAMPER.hasStream):
                stream_type = self.graph.value(stream.identifier, RDF.type)
                if stream_type == TAMPER.VideoStream:
                    streams.append(VideoStream(self.graph, stream.identifier))
                elif stream_type == TAMPER.AudioStream:
                    streams.append(AudioStream(self.graph, stream.identifier))
            self._streams = sorted(streams, key=lambda s: s.stream_index)
        return self._streams


class VideoAsset(StreamContainer):
    pass


class AudioAsset(StreamContainer):
    pass


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


def _extract_container_metadata(asset: Describer, asset_file: PathLike[str]):
    probe_result = ffmpeg.probe(asset_file)

    for stream in probe_result["streams"]:
        with asset.rel(TAMPER.hasStream):
            asset.value(TAMPER.streamIndex, stream["index"])
            if "codec_name" in stream:
                asset.value(TAMPER.codec, stream["codec_name"])
            if "bit_rate" in stream:
                asset.value(TAMPER.bitRate, int(stream["bit_rate"]))
            if "tags" in stream and "language" in stream["tags"]:
                asset.value(TAMPER.language, stream["tags"]["language"])

            if stream["codec_type"] == "video":
                asset.rdftype(TAMPER.VideoStream)
                if "width" in stream:
                    asset.value(TAMPER.width, int(stream["width"]))
                if "height" in stream:
                    asset.value(TAMPER.height, int(stream["height"]))
                if "pix_fmt" in stream:
                    asset.value(TAMPER.pixelFormat, stream["pix_fmt"])
                if "bits_per_raw_sample" in stream:
                    asset.value(TAMPER.bitDepth, int(stream["bits_per_raw_sample"]))

                frame_rate = _get_frame_rate(stream)
                if frame_rate is not None:
                    asset.value(TAMPER.frameRate, frame_rate, datatype=XSD.float)
                # TODO: color space
                # TODO: bit depth

            elif stream["codec_type"] == "audio":
                asset.rdftype(TAMPER.AudioStream)
                if "sample_rate" in stream:
                    asset.value(TAMPER.sampleRate, int(stream["sample_rate"]))
                if "channels" in stream:
                    asset.value(TAMPER.channels, int(stream["channels"]))
                if "bits_per_sample" in stream:
                    asset.value(TAMPER.bitDepth, int(stream["bits_per_sample"]))


def _extract_image_metadata(asset: Describer, asset_file: PathLike[str]):
    with PILImage.open(asset_file) as img:
        asset.value(TAMPER.width, img.width)
        asset.value(TAMPER.height, img.height)
        asset.value(TAMPER.pixelFormat, img.format)


def load_asset_from_file(g: Graph, asset_file: PathLike[str]) -> MediaAsset:
    mimetype = Magic(mime=True).from_file(asset_file)
    checksum = get_file_sha256(asset_file)

    asset_uri = URIRef(f"asset://{checksum}")
    asset = Describer(g, about=asset_uri)
    asset.value(TAMPER.mediaType, mimetype)
    asset.value(TAMPER.checksum, "sha256:" + checksum)
    asset.value(TAMPER.filePath, str(Path(asset_file).absolute()))

    if mimetype.startswith("image/"):
        asset.rdftype(TAMPER.ImageAsset)
        _extract_image_metadata(asset, asset_file)
        return ImageAsset(g, asset_uri)
    elif mimetype.startswith("audio/"):
        asset.rdftype(TAMPER.AudioAsset)
        _extract_container_metadata(asset, asset_file)
        return AudioAsset(g, asset_uri)
    elif mimetype.startswith("video/"):
        asset.rdftype(TAMPER.VideoAsset)
        _extract_container_metadata(asset, asset_file)
        return VideoAsset(g, asset_uri)

    return asset_uri


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
