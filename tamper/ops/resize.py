from pathlib import Path

import cv2
from rdflib import XSD

from tamper.vocabularies import TAMPER

from tamper.core import AssetWorkspace, ImageAsset, Operation, MappedProperty


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

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])
        img_file = workspace.resolve(img_asset)

        img = cv2.imread(str(img_file))
        resized = cv2.resize(
            img,
            (self.width, self.height),
            interpolation=_INTERPOLATIONS[self.interpolation],
        )
        ext = img_file.suffix or ".png"
        ok, buf = cv2.imencode(ext, resized)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(workspace, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())
