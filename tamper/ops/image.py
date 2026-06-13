from os import PathLike
from pathlib import Path

import cv2
import numpy as np
from rdflib import XSD

from tamper.vocabularies import TAMPER

from tamper.core import ImageAsset, Operation, MappedProperty


class CompressJPEG(Operation):
    __rdf_type__ = TAMPER.CompressJPEG

    quality_factor: MappedProperty[int] = MappedProperty(
        TAMPER.qualityFactor, datatype=XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])
        img_asset.graph.print()
        img = cv2.imread(img_asset.file_path)
        ok, buf = cv2.imencode(
            ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.quality_factor]
        )
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        with self._generates_file(dir=out_dir, suffix=".jpg") as f:
            Path(f).write_bytes(buf.tobytes())


class CompressWebP(Operation):
    __rdf_type__ = TAMPER.CompressWebP

    quality_factor: MappedProperty[int] = MappedProperty(
        TAMPER.qualityFactor, datatype=XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")
        img_asset = ImageAsset(self.graph, used[0])

        img = cv2.imread(img_asset.file_path)
        ok, buf = cv2.imencode(
            ".webp", img, [cv2.IMWRITE_WEBP_QUALITY, self.quality_factor]
        )
        if not ok:
            raise RuntimeError("WebP encoding failed")
        with self._generates_file(dir=out_dir, suffix=".webp") as f:
            Path(f).write_bytes(buf.tobytes())


class CropImage(Operation):
    __rdf_type__ = TAMPER.CropImage

    x: MappedProperty[int] = MappedProperty(TAMPER.cropX, datatype=XSD.integer)
    y: MappedProperty[int] = MappedProperty(TAMPER.cropY, datatype=XSD.integer)
    width: MappedProperty[int] = MappedProperty(TAMPER.cropWidth, datatype=XSD.integer)
    height: MappedProperty[int] = MappedProperty(
        TAMPER.cropHeight, datatype=XSD.integer
    )

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

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


class AddGaussianNoise(Operation):
    __rdf_type__ = TAMPER.AddGaussianNoise

    mean: MappedProperty[float] = MappedProperty(TAMPER.gaussianMean, XSD.double)
    std: MappedProperty[float] = MappedProperty(TAMPER.gaussianStd, XSD.double)
    seed: MappedProperty[int] = MappedProperty(TAMPER.gaussianSeed, XSD.integer)

    def mutate(self, out_dir: PathLike[str] | None = None):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

        img = cv2.imread(img_asset.file_path)
        rng = np.random.default_rng(self.seed)
        noise = rng.normal(self.mean, self.std, img.shape)
        noisy_img = np.clip(img + noise, 0, 255).astype(np.uint8)
        ext = Path(img_asset.file_path).suffix or ".png"
        ok, buf = cv2.imencode(ext, noisy_img)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(dir=out_dir, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())
