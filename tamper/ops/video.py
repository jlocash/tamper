from os import PathLike

import ffmpeg
from rdflib import RDF, Literal, XSD, Node
from rdflib.graph import Graph

from .operation import Operation
from tamper.vocabularies import TAMPER


class TranscodeVideo(Operation):
    def __init__(self, video_encoder: str, crf: int):
        super().__init__()
        if not video_encoder:
            raise ValueError("video_encoder must be a non-empty string")
        if not 0 <= crf <= 63:
            raise ValueError(f"crf must be between 0 and 63, got {crf}")
        self.video_encoder = video_encoder
        self.crf = crf

    def graph(self) -> Graph:
        g = Graph()
        g.add((self.subject, RDF.type, TAMPER.TranscodeVideo))
        g.add((self.subject, TAMPER.videoEncoder, Literal(self.video_encoder)))
        g.add((self.subject, TAMPER.crf, Literal(self.crf, datatype=XSD.nonNegativeInteger)))
        return g

    def transform(self, input_video_file: PathLike[str], output_video_file: PathLike[str]):
        probe_result = ffmpeg.probe(str(input_video_file))
        streams = probe_result["streams"]

        codec_types = {s["codec_type"] for s in streams}

        output_kwargs = {"format": probe_result["format"]["format_name"].split(",")[0]}
        if "video" in codec_types:
            output_kwargs["vcodec"] = self.video_encoder
            output_kwargs["crf"] = str(self.crf)
        if "audio" in codec_types:
            output_kwargs["acodec"] = "copy"

        try:
            (
                ffmpeg
                .input(str(input_video_file))
                .output(str(output_video_file), **output_kwargs)
                .run(capture_stderr=True, overwrite_output=True)
            )
        except ffmpeg.Error as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            raise RuntimeError(f"ffmpeg failed: {stderr}") from e

    @classmethod
    def copy_from_graph(cls, graph: Graph, subject: Node):
        video_encoder = graph.value(subject, TAMPER.videoEncoder)
        if video_encoder is None:
            raise ValueError("No video encoder found")
        crf = graph.value(subject, TAMPER.crf)
        if crf is None:
            raise ValueError("No CRF found")
        return cls(str(video_encoder), int(crf))
