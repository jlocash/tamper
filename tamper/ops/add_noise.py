from pathlib import Path

import cv2
import numpy as np
from rdflib import XSD

from tamper.vocabularies import TAMPER

from tamper.core import AssetWorkspace, ImageAsset, Operation, MappedProperty


class AddGaussianNoise(Operation):
    __rdf_type__ = TAMPER.AddGaussianNoise

    mean: MappedProperty[float] = MappedProperty(TAMPER.gaussianMean, XSD.double)
    std: MappedProperty[float] = MappedProperty(TAMPER.gaussianStd, XSD.double)
    seed: MappedProperty[int] = MappedProperty(TAMPER.noiseSeed, XSD.integer)

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])
        img_file = workspace.resolve(img_asset)

        img = cv2.imread(str(img_file))
        rng = np.random.default_rng(self.seed)
        noise = rng.normal(self.mean, self.std, img.shape)
        noisy_img = np.clip(img + noise, 0, 255).astype(np.uint8)
        ext = img_file.suffix or ".png"
        ok, buf = cv2.imencode(ext, noisy_img)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(workspace, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())


class AddSaltPepperNoise(Operation):
    __rdf_type__ = TAMPER.AddSaltPepperNoise

    amount: MappedProperty[float] = MappedProperty(TAMPER.saltPepperAmount, XSD.double)
    salt_ratio: MappedProperty[float] = MappedProperty(
        TAMPER.saltPepperRatio, XSD.double
    )
    seed: MappedProperty[int] = MappedProperty(TAMPER.noiseSeed, XSD.integer)

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])
        img_file = workspace.resolve(img_asset)

        img = cv2.imread(str(img_file))
        if img is None:
            raise RuntimeError(f"Could not read image: {img_file}")

        rng = np.random.default_rng(self.seed)
        out = img.copy()
        h, w = img.shape[:2]
        n = int(self.amount * h * w)
        n_salt = int(n * self.salt_ratio)

        flat = rng.choice(h * w, size=n, replace=False)
        ys, xs = np.unravel_index(flat, (h, w))
        out[ys[:n_salt], xs[:n_salt]] = 255
        out[ys[n_salt:], xs[n_salt:]] = 0

        ext = img_file.suffix or ".png"
        ok, buf = cv2.imencode(ext, out)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(workspace, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())
