from pathlib import Path

from rdflib import Graph, Node, RDF, XSD, Literal

from tamper.vocabularies import TAMPER
from .operation import Operation
import ffmpeg


class ResampleAudio(Operation):
    def __init__(self, target_sample_rate: int):
        super().__init__()
        if target_sample_rate <= 0:
            raise ValueError(
                f"Target sample rate must be positive, got {target_sample_rate}"
            )
        self.target_sample_rate = target_sample_rate

    def transform(self, input_asset_file: Path, output_asset_file: Path):
        probe_result = ffmpeg.probe(str(input_asset_file))
        streams = probe_result["streams"]

        output_kwargs = {"format": probe_result["format"]["format_name"].split(",")[0]}
        for s in streams:
            if s["codec_type"] == "video":
                output_kwargs["vcodec"] = "copy"
            elif s["codec_type"] == "audio":
                output_kwargs["acodec"] = s["codec_name"]
                output_kwargs["ar"] = str(self.target_sample_rate)

        try:
            (
                ffmpeg.input(str(input_asset_file))
                .output(str(output_asset_file), **output_kwargs)
                .run(capture_stdout=False, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.ResampleAudio))
        g.add(
            (
                self.subject,
                TAMPER.targetSampleRate,
                Literal(self.target_sample_rate, datatype=XSD.positiveInteger),
            )
        )
        return g

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        target_sample_rate = graph.value(subject, TAMPER.targetSampleRate)
        if target_sample_rate is None:
            raise ValueError(
                f"Graph is missing property {TAMPER.targetSampleRate} for subject {subject}"
            )
        return cls(int(target_sample_rate))


class TranscodeAudio(Operation):
    def __init__(self, audio_encoder: str, target_bitrate: int):
        super().__init__()
        if not audio_encoder:
            raise ValueError("audio_encoder must be a non-empty string")
        if target_bitrate <= 0:
            raise ValueError(f"target_bitrate must be positive, got {target_bitrate}")
        self.audio_encoder = audio_encoder
        self.target_bitrate = target_bitrate

    def transform(self, input_asset_file: Path, output_asset_file: Path):
        probe_result = ffmpeg.probe(str(input_asset_file))
        streams = probe_result["streams"]
        output_kwargs = {"format": probe_result["format"]["format_name"].split(",")[0]}
        for s in streams:
            if s["codec_type"] == "video":
                output_kwargs["vcodec"] = "copy"
                break
        output_kwargs["acodec"] = self.audio_encoder
        output_kwargs["audio_bitrate"] = self.target_bitrate

        try:
            (
                ffmpeg.input(str(input_asset_file))
                .output(str(output_asset_file), **output_kwargs)
                .run(capture_stdout=False, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.TranscodeAudio))
        g.add(
            (
                self.subject,
                TAMPER.targetBitRate,
                Literal(self.target_bitrate, datatype=XSD.positiveInteger),
            )
        )
        g.add((self.subject, TAMPER.audioEncoder, Literal(self.audio_encoder)))
        return g

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        target_bitrate = graph.value(subject, TAMPER.targetBitRate)
        if target_bitrate is None:
            raise ValueError(
                f"Graph is missing property {TAMPER.targetBitRate} for subject {subject}"
            )
        audio_encoder = graph.value(subject, TAMPER.audioEncoder)
        if audio_encoder is None:
            raise ValueError(
                f"Graph is missing property {TAMPER.audioEncoder} for subject {subject}"
            )
        return cls(str(audio_encoder), int(target_bitrate))
