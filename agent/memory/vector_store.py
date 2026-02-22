import uuid
import chromadb
from chromadb.utils import embedding_functions


class VectorStore:
    def __init__(self, persist_directory="vectors"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        # Using a fast, high-quality local embedding model for code/text semantics
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="devbot_memory", embedding_function=self.ef
        )

    def add(self, text, metadata=None):
        doc_id = str(uuid.uuid4())

        # Chroma requires metadata values to be str, int, float or bool
        safe_meta = {}
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    safe_meta[k] = v
                else:
                    safe_meta[k] = str(v)

        self.collection.add(
            documents=[text], metadatas=[safe_meta] if safe_meta else None, ids=[doc_id]
        )

    def search(self, q, k=3):
        res = self.collection.query(query_texts=[q], n_results=k)
        if res and res["documents"] and res["documents"][0]:
            return res["documents"][0]
        return []
