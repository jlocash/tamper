import cv2

from rdflib import XSD
from pathlib import Path

from tamper.core import AssetWorkspace, Operation, MappedProperty, ImageAsset
from tamper.vocabularies import TAMPER


_FORMAT_TO_CV2 = {
    "webp": cv2.IMWRITE_WEBP_QUALITY,
    "jpeg": cv2.IMWRITE_JPEG_QUALITY,
}


class Compress(Operation):
    __rdf_type__ = TAMPER.Compress
    format: MappedProperty[str] = MappedProperty(TAMPER.format, datatype=XSD.string)
    quality_factor: MappedProperty[int] = MappedProperty(
        TAMPER.qualityFactor, datatype=XSD.integer
    )

    def mutate(self, workspace: AssetWorkspace):
        used = self.get_used()
        if len(used) != 1:
            raise ValueError("Operation requires exactly one image asset")

        img_asset = ImageAsset(self.graph, used[0])

        img_format = _FORMAT_TO_CV2.get(self.format)
        if img_format is None:
            raise ValueError(f"Unexpected image format '{self.format}'")
        ext = "." + self.format

        img = cv2.imread(str(workspace.resolve(img_asset)))
        ok, buf = cv2.imencode(ext, img, [img_format, self.quality_factor])
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        with self._generates_file(workspace, suffix=".jpg") as f:
            Path(f).write_bytes(buf.tobytes())
