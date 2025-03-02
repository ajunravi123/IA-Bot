# retrieval_agent.py
import faiss
import numpy as np
from pathlib import Path
from langchain.embeddings import HuggingFaceEmbeddings
from crewai import Agent
from config import llm_client
from dotenv import load_dotenv

load_dotenv()

class RetrievalAgent:
    def __init__(self, index_path="./vindex/combined_index.index", chunks_path="./vindex/combined_clean.txt"):
        """Initialize the retrieval agent with FAISS index and document chunks."""
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

        # Load document chunks
        with self.chunks_path.open("r", encoding="utf-8") as f:
            self.all_docs = [line.strip() for line in f.readlines() if line.strip()]
        print(f"Loaded {len(self.all_docs)} chunks from {self.chunks_path.resolve()}")

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
        """Retrieve top-k relevant chunks for a given query."""
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
                    "content": chunk
                })
                print(f"Rank {i+1}: Distance={dist:.4f}, Index={idx}, Chunk='{chunk[:100]}...'")
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

# Singleton instance
retrieval_agent_instance = RetrievalAgent()