import os
import ollama
import faiss
import numpy as np
from pathlib import Path
from langchain.embeddings import HuggingFaceEmbeddings

# Define directory and file paths (aligned with create_index.py)
data_dir = Path("./vindex")
index_file = data_dir / "combined_index.index"
splitted_para_file = data_dir / "combined_clean.txt"

# Load embedding model (consistent with index creation)
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
embedding_dim = 768  # BAAI/bge-base-en has 768 dimensions

# Ensure FAISS index exists
if not index_file.exists():
    raise FileNotFoundError(f"FAISS index file not found: {index_file.resolve()}")

# Load FAISS index
index = faiss.read_index(str(index_file))
print(f"Loaded FAISS index from: {index_file.resolve()} with {index.ntotal} vectors")

# Ensure the split paragraph file exists
if not splitted_para_file.exists():
    raise FileNotFoundError(f"Split document file not found: {splitted_para_file.resolve()}")

# Load all document chunks for reference
with splitted_para_file.open("r", encoding="utf-8") as f:
    all_docs = [line.strip() for line in f.readlines() if line.strip()]
print(f"Loaded {len(all_docs)} chunks from {splitted_para_file.resolve()}")

def retrieve_relevant_context(query, top_k=3):
    """Retrieve top-k relevant chunks from FAISS using L2 distance."""
    # Generate query embedding (unnormalized, matching index)
    query_embedding = embedding_model.embed_query(query)  # Single query embedding
    query_embedding = np.array([query_embedding], dtype=np.float32)

    # Search in FAISS index (L2 distance)
    D, I = index.search(query_embedding, top_k)
    distances = D[0]  # L2 distances
    indices = I[0]    # Indices of retrieved chunks

    # Retrieve top relevant chunks
    relevant_contexts = []
    for i, (idx, dist) in enumerate(zip(indices, distances)):
        if idx < len(all_docs):
            chunk = all_docs[idx]
            relevant_contexts.append(chunk)
            # Debugging: Print each retrieved chunk with its distance
            print(f"Rank {i+1}: Distance={dist:.4f}, Index={idx}, Chunk='{chunk[:100]}...'")
        else:
            print(f"Invalid index {idx} retrieved (out of bounds for {len(all_docs)} chunks)")

    return relevant_contexts

def ask_deepseek(query):
    """Fetch an answer using DeepSeek with retrieved context."""
    relevant_context = retrieve_relevant_context(query, top_k=3)
    
    if not relevant_context:
        return "I don't have enough information to answer that."

    # Combine context into a single string
    context_str = "\n".join(relevant_context)
    print(f"\nRetrieved Context:\n{context_str}")

    # Optional: Use ollama for generation (uncomment if desired)
    # prompt = (
    #     "Answer the question based only on the following documentation content:\n"
    #     f"{context_str}\n\nQuestion: {query}"
    # )
    # response = ollama.chat(model="deepseek-r1:1.5b", messages=[{"role": "user", "content": prompt}])
    # return response.get("message", {}).get("content", "No response from DeepSeek.")

    # For now, return raw context
    return context_str

# Example usage
while True:
    user_input = input("Ask a question (type 'bye' to exit): ")
    if user_input.lower() == "bye":
        break
    out_val = ask_deepseek(user_input)
    print("\nAjun's Bot:")
    print(out_val)