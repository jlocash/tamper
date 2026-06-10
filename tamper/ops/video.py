from os import PathLike
from pathlib import Path

import ffmpeg
from rdflib import XSD

from tamper.core import Operation, MappedProperty, VideoAsset
from tamper.vocabularies import TAMPER

_ENCODER_TO_SUFFIX = {
    "libx264": ".mp4",
    "libx265": ".mp4",
    "libvpx": ".webm",
    "libvpx-vp9": ".webm",
    "libaom-av1": ".webm",
    "libsvtav1": ".webm",
    "prores": ".mov",
    "mpeg2video": ".mpg",
}


class TranscodeVideo(Operation):
    __rdf_type__ = TAMPER.TranscodeVideo

    video_encoder: MappedProperty[str] = MappedProperty(TAMPER.videoEncoder, XSD.string)
    crf: MappedProperty[int] = MappedProperty(TAMPER.crf, XSD.integer)

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one video asset")

        video_asset = VideoAsset(self.graph, used[0])
        if not video_asset.has_video():
            raise ValueError("Input asset has no video stream to transcode")

        output_kwargs = {"vcodec": self.video_encoder, "crf": self.crf}
        if video_asset.has_audio():
            output_kwargs["acodec"] = "copy"

        suffix = _ENCODER_TO_SUFFIX.get(
            self.video_encoder, Path(video_asset.file_path).suffix
        )
        try:
            with self._generates_file(dir=out_dir, suffix=suffix) as output_asset_file:
                (
                    ffmpeg.input(str(video_asset.file_path))
                    .output(str(output_asset_file), **output_kwargs)
                    .run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e
