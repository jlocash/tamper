from pathlib import Path

import cv2
from rdflib import XSD

from tamper.vocabularies import TAMPER

from tamper.core import AssetWorkspace, ImageAsset, Operation, MappedProperty


class MedianFilter(Operation):
    __rdf_type__ = TAMPER.MedianFilter

    kernel_size: MappedProperty[int] = MappedProperty(TAMPER.kernelSize, XSD.integer)

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])
        img_file = workspace.resolve(img_asset)

        img = cv2.imread(str(img_file))
        filtered = cv2.medianBlur(img, self.kernel_size)
        ext = img_file.suffix or ".png"
        ok, buf = cv2.imencode(ext, filtered)
        if not ok:
            raise RuntimeError(f"Encoding to {ext} failed")

        with self._generates_file(workspace, suffix=ext) as f:
            Path(f).write_bytes(buf.tobytes())
