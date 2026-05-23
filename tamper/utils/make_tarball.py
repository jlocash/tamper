import tarfile
from io import BytesIO
from os import PathLike
from pathlib import Path

from rdflib import Dataset, URIRef, Literal

from tamper.namespaces import TAMPER


def get_asset_files(dataset: Dataset):
    asset_query = f"""    
    SELECT DISTINCT ?asset ?assetFile ?checksum WHERE {{
        ?asset {TAMPER.filePath.n3()} ?assetFile .
        ?asset {TAMPER.checksum.n3()} ?checksum .
    }}
    """

    for row in dataset.query(asset_query):
        yield URIRef(row.asset), row.assetFile, str(row.checksum)


def make_tarball(dataset: Dataset, output_file: PathLike[str]):
    cloned = Dataset()
    cloned.bind("tamper", TAMPER)
    cloned += dataset

    with tarfile.open(output_file, "w:gz") as tar:
        for asset, asset_file, checksum in get_asset_files(dataset):
            new_asset_file = "assets/" + checksum.split(":")[-1] + Path(asset_file).suffix
            tar.add(str(asset_file), arcname=new_asset_file)
            for s, p, o, g in list(cloned.quads((asset, TAMPER.filePath, asset_file, None))):
                cloned.remove((s, p, o, g))
                cloned.add((s, p, Literal(new_asset_file), g))

        dataset_trig = cloned.serialize(format="trig")
        dataset_bytes = dataset_trig.encode("utf-8")
        info = tarfile.TarInfo(name="dataset.trig")
        info.size = len(dataset_bytes)
        tar.addfile(info, BytesIO(dataset_bytes))
