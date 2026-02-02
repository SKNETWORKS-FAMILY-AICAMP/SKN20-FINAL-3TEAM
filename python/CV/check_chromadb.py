"""ChromaDB 저장 내용 확인"""
import json
from rag_system.vector_store import VectorStore

# VectorStore 초기화
vector_store = VectorStore("rag_data")

# topology_analyses 컬렉션의 모든 데이터 가져오기
topology_results = vector_store.topology_collection.get(
    include=['documents', 'metadatas', 'embeddings']
)
evaluation_results = vector_store.evaluation_collection.get(
    include=['documents', 'metadatas', 'embeddings']
)

topology_results_output_data = []
evaluation_results_output_data = []

for i, doc_id in enumerate(topology_results['ids']):
    embedding = topology_results['embeddings'][i]
    data = {
        "document_id": doc_id,
        "metadata": topology_results['metadatas'][i],
        "document": topology_results['documents'][i],
        "embedding": {
            "dimension": len(embedding),
            "first_10_values": embedding[:10].tolist() if hasattr(embedding, 'tolist') else list(embedding[:10])
        }
    }
    topology_results_output_data.append(data)

for i, doc_id in enumerate(evaluation_results['ids']):
    embedding = evaluation_results['embeddings'][i]
    data = {
        "document_id": doc_id,
        "metadata": evaluation_results['metadatas'][i],
        "document": evaluation_results['documents'][i],
        "embedding": {
            "dimension": len(embedding),
            "first_10_values": embedding[:10].tolist() if hasattr(embedding, 'tolist') else list(embedding[:10])
        }
    }
    evaluation_results_output_data.append(data)

# JSON 파일로 저장
with open("chromadb_topology_content.json", "w", encoding="utf-8") as f:
    json.dump(topology_results_output_data, f, ensure_ascii=False, indent=2)
print(f"ChromaDB content saved to chromadb_topology_content.json")
print(f"Total documents: {len(topology_results_output_data)}")

with open("chromadb_evaluation_content.json", "w", encoding="utf-8") as f:
    json.dump(evaluation_results_output_data, f, ensure_ascii=False, indent=2)
print(f"ChromaDB evaluation content saved to chromadb_evaluation_content.json")
print(f"Total evaluation documents: {len(evaluation_results_output_data)}")
