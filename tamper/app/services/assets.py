from rdflib import RDF, URIRef

from tamper.app.kg import KnowledgeGraph
from tamper.core.assets import AudioAsset, ImageAsset, MediaAsset, VideoAsset
from tamper.vocabularies import TAMPER


class AssetNotFoundError(Exception):
    def __init__(self, asset_uri: URIRef):
        super().__init__(f"Asset {asset_uri.n3()} not found")


ASSET_TYPES = (
    TAMPER.MediaAsset,
    TAMPER.ImageAsset,
    TAMPER.VideoAsset,
    TAMPER.AudioAsset,
)


def asset_exists(kg: KnowledgeGraph, asset_uri: URIRef) -> bool:
    asset_types = " ".join(t.n3() for t in ASSET_TYPES)
    result = kg.query(f"""
    PREFIX tamper: <{TAMPER}>
    ASK {{
        {asset_uri.n3()} a ?assetType .
        VALUES ?assetType {{{asset_types}}}
    }}
    """)
    return result.askAnswer


def get_asset(kg: KnowledgeGraph, asset_uri: URIRef) -> MediaAsset:
    asset_types = " ".join(t.n3() for t in ASSET_TYPES)
    result = kg.query(f"""
    PREFIX tamper: <{TAMPER}>

    CONSTRUCT {{
        {asset_uri.n3()} a ?assetType ;
            tamper:mediaType ?mediaType ;
            tamper:checksum ?checksum ;
            tamper:width ?width ;
            tamper:height ?height ;
            tamper:pixelFormat ?pixelFormat ;
            tamper:containerFormat ?containerFormat ;
            tamper:hasStream ?stream .

        ?stream a ?streamType ;
            tamper:streamIndex ?streamIndex ;
            tamper:codec ?streamCodec ;
            tamper:bitRate ?streamBitRate ;
            tamper:language ?streamLanguage ;
            tamper:sampleRate ?streamSampleRate ;
            tamper:channels ?streamChannels ;
            tamper:bitDepth ?streamBitDepth ;
            tamper:width ?streamWidth ;
            tamper:height ?streamHeight ;
            tamper:pixelFormat ?streamPixelFormat ;
            tamper:frameRate ?streamFrameRate .
    }} WHERE {{
        {asset_uri.n3()} a ?assetType ;
            tamper:mediaType ?mediaType ;
            tamper:checksum ?checksum .
            
        # if the asset is an image
        OPTIONAL {{ {asset_uri.n3()} tamper:width ?width . }}
        OPTIONAL {{ {asset_uri.n3()} tamper:height ?height . }}
        OPTIONAL {{ {asset_uri.n3()} tamper:pixelFormat ?pixelFormat . }}
            
        # If the asset is audio or video
        OPTIONAL {{
            {asset_uri.n3()} tamper:containerFormat ?containerFormat ;
                tamper:hasStream ?stream .

            ?stream a ?streamType ;
                tamper:streamIndex ?streamIndex .

            OPTIONAL {{ ?stream tamper:codec ?streamCodec . }}
            OPTIONAL {{ ?stream tamper:bitRate ?streamBitRate . }}
            OPTIONAL {{ ?stream tamper:language ?streamLanguage . }}
            OPTIONAL {{ ?stream tamper:sampleRate ?streamSampleRate . }}
            OPTIONAL {{ ?stream tamper:channels ?streamChannels . }}
            OPTIONAL {{ ?stream tamper:bitDepth ?streamBitDepth . }}
            OPTIONAL {{ ?stream tamper:width ?streamWidth . }}
            OPTIONAL {{ ?stream tamper:height ?streamHeight . }}
            OPTIONAL {{ ?stream tamper:pixelFormat ?streamPixelFormat . }}
            OPTIONAL {{ ?stream tamper:frameRate ?streamFrameRate . }}
        }}

        VALUES ?assetType {{ {asset_types} }}
    }}
    """)
    graph = result.graph
    if len(graph) == 0:
        raise AssetNotFoundError(asset_uri)

    if (asset_uri, RDF.type, TAMPER.ImageAsset) in graph:
        return ImageAsset(graph, asset_uri)
    if (asset_uri, RDF.type, TAMPER.AudioAsset) in graph:
        return AudioAsset(graph, asset_uri)
    if (asset_uri, RDF.type, TAMPER.VideoAsset) in graph:
        return VideoAsset(graph, asset_uri)
    return MediaAsset(graph, asset_uri)
