from os import PathLike
from pathlib import Path

import cv2
from rdflib import XSD

from tamper.vocabularies import TAMPER

from tamper.core import ImageAsset, Operation, MappedProperty


_INTERPOLATIONS = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "area": cv2.INTER_AREA,
    "lanczos4": cv2.INTER_LANCZOS4,
}


class Resize(Operation):
    __rdf_type__ = TAMPER.Resize

    width: MappedProperty[int] = MappedProperty(TAMPER.targetWidth, XSD.integer)
    height: MappedProperty[int] = MappedProperty(TAMPER.targetHeight, XSD.integer)
    interpolation: MappedProperty[str] = MappedProperty(
        TAMPER.interpolation, XSD.string
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

        img = cv2.imread(img_asset.file_path)
        resized = cv2.resize(
            img,
            (self.width, self.height),
            interpolation=_INTERPOLATIONS[self.interpolation],
        )
        ext = Path(img_asset.file_path).suffix or ".png"
        ok, buf = cv2.imencode(ext, resized)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(dir=out_dir, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())


class MedianFilter(Operation):
    __rdf_type__ = TAMPER.MedianFilter

    kernel_size: MappedProperty[int] = MappedProperty(TAMPER.kernelSize, XSD.integer)

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

        img = cv2.imread(img_asset.file_path)
        filtered = cv2.medianBlur(img, self.kernel_size)
        ext = Path(img_asset.file_path).suffix or ".png"
        ok, buf = cv2.imencode(ext, filtered)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(dir=out_dir, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())


class GaussianBlur(Operation):
    __rdf_type__ = TAMPER.GaussianBlur

    kernel_size: MappedProperty[int] = MappedProperty(TAMPER.kernelSize, XSD.integer)
    sigma: MappedProperty[float] = MappedProperty(TAMPER.blurSigma, XSD.double)

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

        img = cv2.imread(img_asset.file_path)
        blurred = cv2.GaussianBlur(
            img, (self.kernel_size, self.kernel_size), sigmaX=self.sigma
        )
        ext = Path(img_asset.file_path).suffix or ".png"
        ok, buf = cv2.imencode(ext, blurred)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(dir=out_dir, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())
