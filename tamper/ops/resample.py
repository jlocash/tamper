from rdflib import XSD

from tamper.core.assets import AudioStream, StreamContainer, VideoStream
from tamper.vocabularies import TAMPER
from tamper.core import AssetWorkspace, Operation, MappedProperty
import ffmpeg


# ffprobe reports the codec (e.g. "mp3"), but re-encoding needs an encoder name,
# which differs for codecs whose default encoder is an external library.
_CODEC_TO_ENCODER = {
    "mp3": "libmp3lame",
    "opus": "libopus",
    "vorbis": "libvorbis",
}


class Resample(Operation):
    __rdf_type__ = TAMPER.Resample

    target_sample_rate: MappedProperty[int] = MappedProperty(
        TAMPER.targetSampleRate, XSD.integer
    )

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one audio asset")

        asset = StreamContainer(self.graph, used[0])

        output_kwargs = {}
        has_audio = False
        for s in asset.streams:
            if isinstance(s, VideoStream):
                output_kwargs["vcodec"] = "copy"
            elif isinstance(s, AudioStream):
                has_audio = True
                output_kwargs["acodec"] = _CODEC_TO_ENCODER.get(s.codec, s.codec)
                output_kwargs["ar"] = self.target_sample_rate
        if not has_audio:
            raise ValueError(
                f"Asset {asset.identifier} has no audio stream to resample"
            )

        asset_file = workspace.resolve(asset)
        try:
            with self._generates_file(
                workspace, suffix=asset_file.suffix
            ) as output_asset_file:
                (
                    ffmpeg.input(str(asset_file))
                    .output(str(output_asset_file), **output_kwargs)
                    .run(
                        capture_stdout=False, capture_stderr=True, overwrite_output=True
                    )
                )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e
