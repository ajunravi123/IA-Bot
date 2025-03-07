import faiss
import numpy as np
import os
from pathlib import Path
from langchain.embeddings import HuggingFaceEmbeddings
from crewai import Agent
from config import llm_client, ticker_json
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import json

load_dotenv()


JSON_FILE = "companies.json"  # Update with your actual JSON file
EMBEDDINGS_FILE = "company_embeddings.npy"
NAMES_FILE = "company_names.json"


def load_embeddings():
    """Load precomputed embeddings and company names."""
    print("Loading precomputed embeddings...")
    name_embeddings = np.load(EMBEDDINGS_FILE)

    with open(NAMES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return name_embeddings, data["names"], data["symbols"]


if not os.path.exists(EMBEDDINGS_FILE) or not os.path.exists(NAMES_FILE):
    print("EMBEDDINGS FILE file is missing.")
else:
    name_embeddings, company_names, symbols = load_embeddings()
    print("Ticker EMBEDDINGS loaded.")


# Load cached embeddings

class RetrievalAgent:
    def __init__(self, index_path="./vindex/combined_index.index", chunks_path="./vindex/combined_chunks_with_metadata.jsonl"):
        """Initialize the retrieval agent with FAISS index and document chunks with metadata."""
        self.embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
        self.index_path = Path(index_path)
        self.chunks_path = Path(chunks_path)

        # Ensure FAISS index exists
        if not self.index_path.exists():
            raise FileNotFoundError(f"FAISS index file not found: {self.index_path.resolve()}")

        # Load FAISS index
        self.index = faiss.read_index(str(self.index_path))
        print(f"Loaded FAISS index from: {self.index_path.resolve()} with {self.index.ntotal} vectors")

        # Ensure the chunks file exists
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found: {self.chunks_path.resolve()}")

        # Load document chunks with metadata
        self.all_docs = []
        with self.chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                chunk_data = json.loads(line.strip())
                self.all_docs.append({
                    "content": chunk_data["content"],
                    "metadata": chunk_data["metadata"]
                })
        print(f"Loaded {len(self.all_docs)} chunks with metadata from {self.chunks_path.resolve()}")

        # Validate consistency
        if self.index.ntotal != len(self.all_docs):
            raise ValueError(f"Mismatch: Index has {self.index.ntotal} vectors, but {len(self.all_docs)} chunks found.")

        # Define the crewai Agent
        self.agent = Agent(
            role="Document Retrieval Specialist",
            goal="Retrieve relevant paragraphs from indexed documents to answer user questions",
            backstory="I am an expert in searching and retrieving information from a vast repository of documents.",
            verbose=True,
            llm=llm_client
        )

    def retrieve_context(self, query, top_k=3):
        """Retrieve top-k relevant chunks with content and metadata for a given query."""
        query_embedding = self.embedding_model.embed_query(query)
        query_embedding = np.array([query_embedding], dtype=np.float32)

        D, I = self.index.search(query_embedding, top_k)
        distances = D[0]
        indices = I[0]

        relevant_contexts = []
        for i, (idx, dist) in enumerate(zip(indices, distances)):
            if idx < len(self.all_docs):
                chunk = self.all_docs[idx]
                relevant_contexts.append({
                    "rank": i + 1,
                    "distance": float(dist),
                    "index": int(idx),
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]  # Include metadata with URL
                })
                print(f"Rank {i+1}: Distance={dist:.4f}, Index={idx}, URL={chunk['metadata']['url']}, Chunk='{chunk['content'][:100]}...'")
            else:
                print(f"Warning: Invalid index {idx} retrieved (out of bounds)")
        
        return relevant_contexts

    def get_matched_paragraphs(self, query):
        """Retrieve matched paragraphs for a query."""
        contexts = self.retrieve_context(query)
        if not contexts:
            return "No relevant paragraphs found."
        return "\n\n".join([ctx["content"] for ctx in contexts])

    def create_task(self, query):
        """Create a task for the crewai Agent."""
        return {
            "description": f"Retrieve relevant paragraphs from the document index for the question: '{query}'",
            "expected_output": "A string containing relevant paragraphs separated by double newlines",
            "agent": self.agent,
            "callback": lambda result: self.get_matched_paragraphs(query)
        }
    


    def get_top_ticker_matches(self, query, top_n=3):
        """Find the most matched company names using AI-based semantic similarity."""
        
        # Compute embedding for the query
        query_embedding = np.array(self.embedding_model.embed_query(query)).reshape(1, -1)

        # Compute cosine similarity using optimized sklearn function
        similarities = cosine_similarity(query_embedding, name_embeddings)[0]

        # Get top N matches
        top_indices = np.argsort(similarities)[::-1][:top_n]

        # Return matched company names with symbols
        results = [{"name": company_names[i], "symbol": symbols[i], "score": similarities[i]} for i in top_indices]
        
        return results

# Singleton instance
retrieval_agent_instance = RetrievalAgent()