import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from fastapi import HTTPException
from app.config import get_settings
from app.models import Property, ContentItem

logger = logging.getLogger(__name__)
settings = get_settings()

def get_chroma_client():
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key missing for vector store.")
    
    path = settings.CHROMA_PATH or "./chroma_data"
    os.makedirs(path, exist_ok=True)
    return chromadb.PersistentClient(path=path)

def get_embedding_function():
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key missing for embeddings.")
        
    model = settings.OPENAI_EMBEDDING_MODEL or "text-embedding-3-small"
    return embedding_functions.OpenAIEmbeddingFunction(
        api_key=settings.OPENAI_API_KEY,
        model_name=model
    )

def get_properties_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="properties",
        embedding_function=get_embedding_function()
    )

def get_content_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="content",
        embedding_function=get_embedding_function()
    )

def _build_property_text(prop: Property) -> str:
    parts = []
    if prop.name: parts.append(prop.name)
    if prop.type: parts.append(f"Type: {prop.type}")
    if prop.location: parts.append(f"Location: {prop.location}")
    if prop.description: parts.append(prop.description)
    if prop.amenities:
        if isinstance(prop.amenities, list):
            parts.append("Amenities: " + ", ".join(prop.amenities))
        else:
            parts.append(f"Amenities: {prop.amenities}")
            
    return "\n".join(parts)

def index_property(prop: Property):
    try:
        col = get_properties_collection()
        text = _build_property_text(prop)
        metadata = {
            "property_id": prop.id,
            "type": prop.type or "",
            "location": prop.location or "",
            "url": prop.url or ""
        }
        
        col.upsert(
            documents=[text],
            metadatas=[metadata],
            ids=[str(prop.id)]
        )
        logger.info(f"Indexed property {prop.id} to vector store.")
    except HTTPException as e:
        logger.warning(f"Skipping index for property {prop.id}: {e.detail}")
    except Exception as e:
        logger.error(f"Error indexing property {prop.id}: {e}")

def search_properties(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    col = get_properties_collection()
    results = col.query(
        query_texts=[query],
        n_results=top_k
    )
    
    properties = []
    if not results['ids'] or not results['ids'][0]:
        return properties
        
    for i, p_id in enumerate(results['ids'][0]):
        dist = results['distances'][0][i] if 'distances' in results and results['distances'] else None
        meta = results['metadatas'][0][i] if 'metadatas' in results and results['metadatas'] else {}
        properties.append({
            "id": int(p_id),
            "score": dist,
            "metadata": meta
        })
        
    return properties

def index_content(item: ContentItem):
    try:
        if not item.caption:
            return
            
        col = get_content_collection()
        metadata = {
            "content_id": item.id,
            "property_id": item.property_id or 0,
            "kind": item.kind or "",
            "platform": item.platform or ""
        }
        
        col.upsert(
            documents=[item.caption],
            metadatas=[metadata],
            ids=[str(item.id)]
        )
    except HTTPException as e:
        logger.warning(f"Skipping index for content {item.id}: {e.detail}")
    except Exception as e:
        logger.error(f"Error indexing content {item.id}: {e}")

def find_similar_content(text: str, threshold: float = 0.9) -> List[Dict[str, Any]]:
    col = get_content_collection()
    results = col.query(
        query_texts=[text],
        n_results=5
    )
    
    similar = []
    if not results['ids'] or not results['ids'][0]:
        return similar
        
    for i, c_id in enumerate(results['ids'][0]):
        dist = results['distances'][0][i] if 'distances' in results and results['distances'] else 1.0
        # Chroma defaults to L2 distance. Smaller is better. 
        # Using a loose mapping of L2 to similarity threshold.
        # Typical threshold logic might need tuning based on actual embeddings.
        if dist < (2.0 * (1.0 - threshold)): # Basic heuristic
            similar.append({
                "id": int(c_id),
                "distance": dist,
                "text": results['documents'][0][i] if 'documents' in results and results['documents'] else ""
            })
            
    return similar
