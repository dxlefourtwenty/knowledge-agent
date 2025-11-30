import chromadb

# default persistent storage (~/.chroma)
chroma_client = chromadb.Client()

collection = chroma_client.get_or_create_collection(
    name="notes",
    metadata={"hnsw:space": "cosine"}
)
