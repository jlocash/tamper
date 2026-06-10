from os import PathLike
from pathlib import Path

from rdflib import XSD

from tamper.core.assets import AudioAsset, AudioStream, VideoStream
from tamper.vocabularies import TAMPER
from tamper.core import Operation, MappedProperty
import ffmpeg


# ffprobe reports the codec (e.g. "mp3"), but re-encoding needs an encoder name,
# which differs for codecs whose default encoder is an external library.
_CODEC_TO_ENCODER = {
    "mp3": "libmp3lame",
    "opus": "libopus",
    "vorbis": "libvorbis",
}

# Maps encoder name to the container format suffix it produces.
_ENCODER_TO_SUFFIX = {
    "libmp3lame": ".mp3",
    "libopus": ".opus",
    "libvorbis": ".ogg",
    "aac": ".aac",
    "flac": ".flac",
    "pcm_s16le": ".wav",
    "pcm_s24le": ".wav",
}


class ResampleAudio(Operation):
    __rdf_type__ = TAMPER.ResampleAudio

    target_sample_rate: MappedProperty[int] = MappedProperty(
        TAMPER.targetSampleRate, XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one audio asset")

        audio_asset = AudioAsset(self.graph, used[0])

        output_kwargs = {}
        has_audio = False
        for s in audio_asset.streams:
            if isinstance(s, VideoStream):
                output_kwargs["vcodec"] = "copy"
            elif isinstance(s, AudioStream):
                has_audio = True
                output_kwargs["acodec"] = _CODEC_TO_ENCODER.get(s.codec, s.codec)
                output_kwargs["ar"] = self.target_sample_rate
        if not has_audio:
            raise ValueError("Input asset has no audio stream to resample")

        suffix = Path(audio_asset.file_path).suffix
        try:
            with self._generates_file(dir=out_dir, suffix=suffix) as output_asset_file:
                (
                    ffmpeg.input(str(audio_asset.file_path))
                    .output(str(output_asset_file), **output_kwargs)
                    .run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e


class TranscodeAudio(Operation):
    __rdf_type__ = TAMPER.TranscodeAudio

    audio_encoder: MappedProperty[str] = MappedProperty(TAMPER.audioEncoder, XSD.string)
    target_bitrate: MappedProperty[int] = MappedProperty(
        TAMPER.targetBitRate, XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one audio asset")

        audio_asset = AudioAsset(self.graph, used[0])

        output_kwargs = {
            "acodec": self.audio_encoder,
            "audio_bitrate": self.target_bitrate,
        }
        for s in audio_asset.streams:
            if isinstance(s, VideoStream):
                output_kwargs["vcodec"] = "copy"

        suffix = _ENCODER_TO_SUFFIX.get(
            self.audio_encoder, Path(audio_asset.file_path).suffix
        )
        try:
            with self._generates_file(dir=out_dir, suffix=suffix) as output_asset_file:
                (
                    ffmpeg.input(str(audio_asset.file_path))
                    .output(str(output_asset_file), **output_kwargs)
                    .run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e
