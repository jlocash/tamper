import mimetypes
import os
from os import PathLike
from pathlib import Path
from uuid import uuid7

from tamper.storage import AssetStorage

from .assets import MediaAsset


def hex_digest(asset: MediaAsset) -> str:
    """The bare sha256 hex digest of an asset, without the algorithm prefix"""
    checksum = asset.checksum
    if checksum is None:
        raise ValueError(f"Asset {asset.identifier} has no checksum")
    return checksum.removeprefix("sha256:")


class AssetWorkspace:
    """
    A local scratch directory backed by Tamper's asset storage.

    Assets live in object storage under their content-addressed key, but
    operations need local copies for execution. The workspace fetches an
    asset's file on first use and caches them by checksum, and publishes
    newly generated files back to storage. Cached files are named
    ``<checksum><ext>``, where the extension is derived from the media type.
    """

    def __init__(self, asset_storage: AssetStorage, work_dir: PathLike[str]):
        self.asset_storage = asset_storage
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, asset: MediaAsset) -> Path:
        suffix = mimetypes.guess_extension(asset.media_type or "") or ""
        return self.work_dir / f"{hex_digest(asset)}{suffix}"

    def resolve(self, asset: MediaAsset) -> Path:
        """
        The local path to an asset file, downloading them from asset storage
        on first use.

        :raises FileNotFoundError: if the asset has no file in asset storage
        """
        path = self.cache_path(asset)
        if path.exists():
            return path

        digest = hex_digest(asset)
        if not self.asset_storage.asset_file_exists(digest):
            raise FileNotFoundError(
                f"Asset {asset.identifier} has no file in asset storage"
            )

        # download to a unique name and rename, so steps resolving the same
        # asset concurrently can never observe a half-written file
        partial = path.with_name(f"{path.name}.{uuid7()}.part")
        try:
            self.asset_storage.download_asset_file(digest, str(partial))
            os.replace(partial, path)
        finally:
            partial.unlink(missing_ok=True)

        return path

    def publish(self, asset: MediaAsset, local_path: PathLike[str]) -> Path:
        """
        Uploads a newly generated asset's file under its content-addressed key
        and moves it into the cache.

        :return: the cached path of the published file
        """
        digest = hex_digest(asset)
        if not self.asset_storage.asset_file_exists(digest):
            self.asset_storage.upload_asset_file(digest, str(local_path))

        path = self.cache_path(asset)
        os.replace(local_path, path)
        return path
