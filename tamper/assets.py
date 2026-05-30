import hashlib
from os import PathLike
from pathlib import Path

import ffmpeg
from magic import Magic
from rdflib import Graph, URIRef, XSD
from rdflib.extras.describer import Describer
from tamper.vocabularies import TAMPER
from PIL import Image as PILImage


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
        except (ValueError, ZeroDivisionError):
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
                    asset.value(TAMPER.frameRate, frame_rate, datatype=XSD.decimal)
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


def build_asset_from_file(g: Graph, asset_file: PathLike[str]) -> URIRef:
    mimetype = Magic(mime=True).from_file(asset_file)
    checksum = get_file_sha256(asset_file)

    asset_uri = URIRef(f"asset://{checksum}")
    asset = Describer(g, about=asset_uri)
    asset.value(TAMPER.mediaType, mimetype)
    asset.value(TAMPER.checksum, "sha256:"+checksum)
    asset.value(TAMPER.filePath, str(Path(asset_file).absolute()))

    if mimetype.startswith("image/"):
        asset.rdftype(TAMPER.ImageAsset)
        _extract_image_metadata(asset, asset_file)
    elif mimetype.startswith("audio/"):
        asset.rdftype(TAMPER.AudioAsset)
        _extract_container_metadata(asset, asset_file)
    elif mimetype.startswith("video/"):
        asset.rdftype(TAMPER.VideoAsset)
        _extract_container_metadata(asset, asset_file)

    return asset_uri
