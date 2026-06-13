from os import PathLike
from pathlib import Path

import ffmpeg
from rdflib import XSD

from tamper.core import MappedProperty, Operation
from tamper.core.assets import StreamContainer
from tamper.vocabularies import TAMPER


# Maps encoder name to the container format suffix it produces.
_AUDIO_ENCODER_TO_SUFFIX = {
    "libmp3lame": ".mp3",
    "libopus": ".opus",
    "libvorbis": ".ogg",
    "aac": ".aac",
    "flac": ".flac",
    "pcm_s16le": ".wav",
    "pcm_s24le": ".wav",
}

_VIDEO_ENCODER_TO_SUFFIX = {
    "libx264": ".mp4",
    "libx265": ".mp4",
    "libvpx": ".webm",
    "libvpx-vp9": ".webm",
    "libaom-av1": ".webm",
    "libsvtav1": ".webm",
    "prores": ".mov",
    "mpeg2video": ".mpg",
}


class Transcode(Operation):
    __rdf_type__ = TAMPER.Transcode

    audio_encoder: MappedProperty[str | None] = MappedProperty(
        TAMPER.audioEncoder, XSD.string
    )
    video_encoder: MappedProperty[str | None] = MappedProperty(
        TAMPER.videoEncoder, XSD.string
    )
    crf: MappedProperty[int | None] = MappedProperty(TAMPER.crf, XSD.integer)
    target_bitrate: MappedProperty[int | None] = MappedProperty(
        TAMPER.targetBitRate, XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one audio or video asset")

        if not self.audio_encoder and not self.video_encoder:
            raise ValueError(
                "Transcode requires at least one of audioEncoder or videoEncoder"
            )

        asset = StreamContainer(self.graph, used[0])
        output_kwargs = {}
        has_audio = asset.has_audio()
        if has_audio:
            if self.audio_encoder:
                output_kwargs["acodec"] = self.audio_encoder
                if self.target_bitrate:
                    output_kwargs["audio_bitrate"] = self.target_bitrate
            else:
                output_kwargs["acodec"] = "copy"
        elif self.audio_encoder:
            raise ValueError(
                f"Asset {asset.identifier} has no audio stream to transcode"
            )

        has_video = asset.has_video()
        if has_video:
            if self.video_encoder:
                output_kwargs["vcodec"] = self.video_encoder
                if self.crf is not None:
                    output_kwargs["crf"] = self.crf
            else:
                output_kwargs["vcodec"] = "copy"
        elif self.video_encoder:
            raise ValueError(
                f"Asset {asset.identifier} has no video stream to transcode"
            )

        # keep the source container unless we are producing a single-stream output.
        suffix = Path(asset.file_path).suffix
        if has_video and self.video_encoder:
            suffix = _VIDEO_ENCODER_TO_SUFFIX.get(self.video_encoder, suffix)
        elif not has_video and has_audio and self.audio_encoder:
            suffix = _AUDIO_ENCODER_TO_SUFFIX.get(self.audio_encoder, suffix)

        try:
            with self._generates_file(dir=out_dir, suffix=suffix) as output_asset_file:
                (
                    ffmpeg.input(str(asset.file_path))
                    .output(str(output_asset_file), **output_kwargs)
                    .run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e
