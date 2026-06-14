from os import PathLike
from pathlib import Path

import cv2
import ffmpeg
from rdflib import RDF, XSD

from tamper.core.assets import VideoAsset
from tamper.vocabularies import TAMPER

from tamper.core import ImageAsset, Operation, MappedProperty


class Crop(Operation):
    __rdf_type__ = TAMPER.Crop

    x: MappedProperty[int] = MappedProperty(TAMPER.cropX, datatype=XSD.integer)
    y: MappedProperty[int] = MappedProperty(TAMPER.cropY, datatype=XSD.integer)
    width: MappedProperty[int] = MappedProperty(TAMPER.cropWidth, datatype=XSD.integer)
    height: MappedProperty[int] = MappedProperty(
        TAMPER.cropHeight, datatype=XSD.integer
    )

    def _mutate_image(
        self, img_asset: ImageAsset, out_dir: PathLike[str] | None = None
    ):
        img = cv2.imread(img_asset.file_path)
        if img is None:
            raise RuntimeError(f"Could not read image: {img_asset.file_path}")

        h, w = img.shape[:2]
        if self.x + self.width > w or self.y + self.height > h:
            raise ValueError(
                f"Crop region (x={self.x}, y={self.y}, width={self.width}, height={self.height}) "
                f"exceeds image bounds ({w}x{h})"
            )

        cropped = img[self.y : self.y + self.height, self.x : self.x + self.width]
        ext = Path(img_asset.file_path).suffix or ".png"
        ok, buf = cv2.imencode(ext, cropped)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(dir=out_dir, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())

    def _mutate_video(
        self, video_asset: VideoAsset, out_dir: PathLike[str] | None = None
    ):
        inp = ffmpeg.input(str(video_asset.file_path))
        streams = [inp.video.crop(self.x, self.y, self.width, self.height)]
        if video_asset.has_audio():
            streams.append(inp.audio)

        suffix = Path(video_asset.file_path).suffix
        try:
            with self._generates_file(dir=out_dir, suffix=suffix) as output_asset_file:
                (
                    ffmpeg.output(*streams, str(output_asset_file)).run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")
        asset_uri = used[0]

        if (asset_uri, RDF.type, TAMPER.ImageAsset) in self.graph:
            return self._mutate_image(ImageAsset(self.graph, asset_uri), out_dir)
        if (asset_uri, RDF.type, TAMPER.VideoAsset) in self.graph:
            return self._mutate_video(VideoAsset(self.graph, asset_uri), out_dir)

        raise ValueError(f"Asset {used[0]} is not a video or image")
