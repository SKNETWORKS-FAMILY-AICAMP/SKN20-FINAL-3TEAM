"""ChromaDB 저장 내용 확인"""
import json
from rag_system.vector_store import VectorStore

# VectorStore 초기화
vector_store = VectorStore("rag_data")

# topology_analyses 컬렉션의 모든 데이터 가져오기
results = vector_store.topology_collection.get(
    include=['documents', 'metadatas', 'embeddings']
)

output_data = []

for i, doc_id in enumerate(results['ids']):
    embedding = results['embeddings'][i]
    data = {
        "document_id": doc_id,
        "metadata": results['metadatas'][i],
        "document": results['documents'][i],
        "embedding": {
            "dimension": len(embedding),
            "first_10_values": embedding[:10].tolist() if hasattr(embedding, 'tolist') else list(embedding[:10])
        }
    }
    output_data.append(data)

# JSON 파일로 저장
with open("chromadb_content.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"ChromaDB content saved to chromadb_content.json")
print(f"Total documents: {len(output_data)}")
