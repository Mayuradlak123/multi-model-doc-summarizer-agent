import uuid
from typing import List, Dict, Any
from app.config import chroma_client, logger, chroma_breaker, with_breaker

class SimpleEmbeddingFunction:
    """A resilient fallback embedding function that doesn't need external downloads."""
    def __call__(self, input: List[str]) -> List[List[float]]:
        # Generate deterministic mock embedding vectors of size 128
        embeddings = []
        for text in input:
            vector = [0.0] * 128
            # simple hashing/token frequency simulation
            for i, char in enumerate(text[:128]):
                vector[i % 128] += float(ord(char)) / 255.0
            # Normalize vector
            norm = sum(x**2 for x in vector)**0.5
            if norm > 0:
                vector = [x / norm for x in vector]
            embeddings.append(vector)
        return embeddings

def get_embedding_fn():
    try:
        from chromadb.utils import embedding_functions
        # Try to use default sentence transformer (might download a small model on first import)
        logger.info("Initializing SentenceTransformer embedding function...")
        # We specify a small model to load quickly
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning(f"Could not initialize SentenceTransformer ({str(e)}). Using lightweight fallback embedding function.")
        return SimpleEmbeddingFunction()

embedding_fn = get_embedding_fn()

class VectorStoreService:
    def __init__(self):
        self.client = chroma_client
        self.cache_collection = None
        if self.client:
            try:
                self.cache_collection = self.client.get_or_create_collection(
                    name="semantic_cache",
                    embedding_function=embedding_fn
                )
                logger.info("Semantic cache collection 'semantic_cache' initialized in ChromaDB.")
            except Exception as e:
                logger.error(f"Failed to initialize semantic cache collection: {str(e)}")

    @with_breaker(chroma_breaker, lambda *args, **kwargs: None)
    def check_cache(self, text: str, threshold: float = 0.15) -> str | None:
        """Queries the semantic cache for a similar text chunk.
        Returns the cached summary string if found within the distance threshold, else None."""
        if not self.client or not self.cache_collection:
            return None
            
        try:
            results = self.cache_collection.query(
                query_texts=[text],
                n_results=1
            )
            if results and results["documents"] and results["documents"][0]:
                distance = results["distances"][0][0] if results["distances"] else 1.0
                if distance <= threshold:
                    cached_response = results["metadatas"][0][0]["response"]
                    logger.info(f"⚡ Semantic Cache HIT! Cosine/L2 distance: {distance:.4f} (<= {threshold})")
                    return cached_response
                else:
                    logger.info(f"🔍 Semantic Cache MISS. Closest distance: {distance:.4f} (> {threshold})")
        except Exception as e:
            logger.error(f"Error checking semantic cache: {str(e)}")
        return None

    @with_breaker(chroma_breaker, lambda *args, **kwargs: False)
    def update_cache(self, text: str, response: str) -> bool:
        """Saves a text chunk and its corresponding summary to the semantic cache."""
        if not self.client or not self.cache_collection:
            return False
            
        try:
            cache_id = f"cache_{uuid.uuid4().hex[:12]}"
            self.cache_collection.add(
                ids=[cache_id],
                documents=[text],
                metadatas=[{"response": response}]
            )
            logger.info(f"💾 Saved response to semantic cache under ID: {cache_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving to semantic cache: {str(e)}")
            return False

    @with_breaker(chroma_breaker, lambda *args, **kwargs: False)
    def index_document(self, document_id: str, chunks: List[Dict[str, Any]], filename: str) -> bool:
        if not self.client:
            logger.warning("Chroma Client is not active. Skipping indexing.")
            return False
            
        try:
            # Collection names must be 3-63 chars, start/end alphanumeric, contain alphanumeric, dunder, hyphen, dot
            clean_id = document_id.replace("-", "_")
            collection_name = f"doc_{clean_id}"
            logger.info(f"Indexing document {filename} in Chroma collection: {collection_name}")
            
            # Delete if exists to avoid conflicts
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass
                
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=embedding_fn
            )
            
            ids = [f"{document_id}_chunk_{c['chunk_index']}" for c in chunks]
            documents = [c["content"] for c in chunks]
            metadatas = [{
                "document_id": document_id,
                "filename": filename,
                "chunk_index": c["chunk_index"],
                "start_char": c["start_char"],
                "end_char": c["end_char"]
            } for c in chunks]
            
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Successfully indexed {len(chunks)} chunks into collection {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to index document in ChromaDB: {str(e)}")
            return False

    @with_breaker(chroma_breaker, lambda *args, **kwargs: [])
    def query_document(self, document_id: str, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        if not self.client:
            logger.warning("Chroma Client is not active. Returning empty results.")
            return []
            
        try:
            clean_id = document_id.replace("-", "_")
            collection_name = f"doc_{clean_id}"
            
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn
            )
            
            count = collection.count()
            if count == 0:
                return []
                
            results = collection.query(
                query_texts=[query],
                n_results=min(n_results, count)
            )
            
            formatted_results = []
            if results and results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to query Chroma DB for document {document_id}: {str(e)}")
            return []

vector_store_service = VectorStoreService()
