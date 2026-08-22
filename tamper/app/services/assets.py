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
    ASK {{
        {asset_uri.n3()} a ?assetType .
        VALUES ?assetType {{{asset_types}}}
    }}
    """)
    return result.askAnswer


def get_asset(kg: KnowledgeGraph, asset_uri: URIRef) -> MediaAsset:
    asset_types = " ".join(t.n3() for t in ASSET_TYPES)
    result = kg.query(f"""
    CONSTRUCT {{
        {asset_uri.n3()} a ?assetType ;
            {TAMPER.mediaType.n3()} ?mediaType ;
            {TAMPER.checksum.n3()} ?checksum ;
            {TAMPER.width.n3()} ?width ;
            {TAMPER.height.n3()} ?height ;
            {TAMPER.pixelFormat.n3()} ?pixelFormat ;
            {TAMPER.containerFormat.n3()} ?containerFormat ;
            {TAMPER.hasStream.n3()} ?stream .

        ?stream a ?streamType ;
            {TAMPER.streamIndex.n3()} ?streamIndex ;
            {TAMPER.codec.n3()} ?streamCodec ;
            {TAMPER.bitRate.n3()} ?streamBitRate ;
            {TAMPER.language.n3()} ?streamLanguage ;
            {TAMPER.sampleRate.n3()} ?streamSampleRate ;
            {TAMPER.channels.n3()} ?streamChannels ;
            {TAMPER.bitDepth.n3()} ?streamBitDepth ;
            {TAMPER.width.n3()} ?streamWidth ;
            {TAMPER.height.n3()} ?streamHeight ;
            {TAMPER.pixelFormat.n3()} ?streamPixelFormat ;
            {TAMPER.frameRate.n3()} ?streamFrameRate .
    }} WHERE {{
        {asset_uri.n3()} a ?assetType ;
            {TAMPER.mediaType.n3()} ?mediaType ;
            {TAMPER.checksum.n3()} ?checksum .
            
        # if the asset is an image
        OPTIONAL {{ {asset_uri.n3()} {TAMPER.width.n3()} ?width . }}
        OPTIONAL {{ {asset_uri.n3()} {TAMPER.height.n3()} ?height . }}
        OPTIONAL {{ {asset_uri.n3()} {TAMPER.pixelFormat.n3()} ?pixelFormat . }}
            
        # If the asset is audio or video
        OPTIONAL {{
            {asset_uri.n3()} {TAMPER.containerFormat.n3()} ?containerFormat ;
                {TAMPER.hasStream.n3()} ?stream .

            ?stream a ?streamType ;
                {TAMPER.streamIndex.n3()} ?streamIndex .

            OPTIONAL {{ ?stream {TAMPER.codec.n3()} ?streamCodec . }}
            OPTIONAL {{ ?stream {TAMPER.bitRate.n3()} ?streamBitRate . }}
            OPTIONAL {{ ?stream {TAMPER.language.n3()} ?streamLanguage . }}
            OPTIONAL {{ ?stream {TAMPER.sampleRate.n3()} ?streamSampleRate . }}
            OPTIONAL {{ ?stream {TAMPER.channels.n3()} ?streamChannels . }}
            OPTIONAL {{ ?stream {TAMPER.bitDepth.n3()} ?streamBitDepth . }}
            OPTIONAL {{ ?stream {TAMPER.width.n3()} ?streamWidth . }}
            OPTIONAL {{ ?stream {TAMPER.height.n3()} ?streamHeight . }}
            OPTIONAL {{ ?stream {TAMPER.pixelFormat.n3()} ?streamPixelFormat . }}
            OPTIONAL {{ ?stream {TAMPER.frameRate.n3()} ?streamFrameRate . }}
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
