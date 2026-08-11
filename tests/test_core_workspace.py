import pytest
from rdflib import Graph

from tamper.core import load_asset_from_file
from tamper.core.workspace import hex_digest

from .conftest import TEST_MEDIA

JPG = TEST_MEDIA / "images" / "file_example_JPG_100kB.jpg"
WAV = TEST_MEDIA / "audio" / "file_example_WAV_1MG.wav"


def describe(src):
    """An asset resource for ``src``, without touching asset storage."""
    return load_asset_from_file(Graph(), src)


class TestCachePath:
    def test_named_by_checksum_and_media_type(self, workspace):
        asset = describe(JPG)
        assert workspace.cache_path(asset).name == f"{hex_digest(asset)}.jpg"

    def test_lives_in_the_work_dir(self, workspace):
        assert workspace.cache_path(describe(JPG)).parent == workspace.work_dir

    def test_unknown_media_type_gets_no_suffix(self, workspace):
        asset = describe(JPG)
        asset.media_type = "application/x-not-a-real-type"
        assert workspace.cache_path(asset).suffix == ""


class TestResolve:
    def test_downloads_asset_on_first_use(self, workspace, load_asset):
        asset = load_asset(Graph(), JPG)

        path = workspace.resolve(asset)

        assert path.exists()
        assert path.read_bytes() == JPG.read_bytes()

    def test_is_cached_after_the_first_download(
        self, workspace, load_asset, object_storage
    ):
        asset = load_asset(Graph(), JPG)
        first = workspace.resolve(asset)

        # drop the object; a cached resolve must not need it
        object_storage.objects.clear()

        assert workspace.resolve(asset) == first

    def test_leaves_no_partial_files_behind(self, workspace, load_asset):
        workspace.resolve(load_asset(Graph(), JPG))
        assert list(workspace.work_dir.glob("*.part")) == []

    def test_missing_asset_raises(self, workspace):
        with pytest.raises(FileNotFoundError):
            workspace.resolve(describe(JPG))

    def test_asset_without_checksum_raises(self, workspace):
        asset = describe(JPG)
        asset.graph.remove((asset.identifier, None, None))
        with pytest.raises(ValueError):
            workspace.resolve(asset)


class TestPublish:
    def test_uploads_under_the_content_addressed_key(
        self, workspace, asset_storage, tmp_path
    ):
        source = tmp_path / "generated.jpg"
        source.write_bytes(JPG.read_bytes())
        asset = describe(source)

        workspace.publish(asset, source)

        assert asset_storage.asset_file_exists(hex_digest(asset))

    def test_moves_the_file_into_the_cache(self, workspace, tmp_path):
        source = tmp_path / "generated.jpg"
        source.write_bytes(JPG.read_bytes())
        asset = describe(source)

        path = workspace.publish(asset, source)

        assert path == workspace.cache_path(asset)
        assert path.read_bytes() == JPG.read_bytes()
        assert not source.exists()

    def test_published_asset_resolves_without_a_download(
        self, workspace, tmp_path, object_storage
    ):
        source = tmp_path / "generated.wav"
        source.write_bytes(WAV.read_bytes())
        asset = describe(source)
        workspace.publish(asset, source)

        object_storage.objects.clear()

        assert workspace.resolve(asset).read_bytes() == WAV.read_bytes()

    def test_republishing_existing_bytes_does_not_reupload(
        self, workspace, asset_storage, tmp_path
    ):
        source = tmp_path / "generated.jpg"
        source.write_bytes(JPG.read_bytes())
        asset = describe(source)
        workspace.publish(asset, source)

        stored = dict(asset_storage.object_storage.objects)

        again = tmp_path / "again.jpg"
        again.write_bytes(JPG.read_bytes())
        workspace.publish(asset, again)

        assert asset_storage.object_storage.objects == stored
