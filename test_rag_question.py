# test_rag_question.py
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch
import os

def load_vector_store(persist_path="./faiss_index.faiss"):
    """Load the FAISS vector store from disk."""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(persist_path):
        raise FileNotFoundError(f"FAISS index not found at {persist_path}. Run update_vector_db.py first.")
    vector_store = FAISS.load_local(persist_path, embeddings, allow_dangerous_deserialization=True)
    return vector_store

def setup_text_generator():
    """Set up a raw HuggingFace text generation pipeline."""
    model_name = "distilgpt2"  # Lightweight model for testing; replace as needed
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    # Create a text generation pipeline
    generator = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=100,
        device=0 if torch.cuda.is_available() else -1  # Use GPU if available
    )
    return generator

def custom_rag_query(vector_store, generator, question, top_k=3):
    """Custom RAG pipeline: retrieve documents and generate an answer."""
    # Retrieve relevant documents
    retrieved_docs = vector_store.similarity_search(question, k=top_k)
    
    if not retrieved_docs:
        return "No relevant documents found.", []

    # Combine retrieved content into a context
    context = "\n".join([doc.page_content for doc in retrieved_docs])
    print(f"\nRetrieved Context:\n{context[:500]}...")  # Preview context (limited to 500 chars)

    # Craft a simple prompt for the generator
    prompt = f"Question: {question}\nContext: {context}\nAnswer: "
    
    # Generate the answer
    generated = generator(prompt, max_new_tokens=100, do_sample=True, temperature=0.7)
    answer = generated[0]["generated_text"].replace(prompt, "").strip()  # Extract the answer part
    
    return answer, retrieved_docs

def test_rag_question(question, persist_path="./faiss_index.faiss"):
    """Test the custom RAG system by asking a question and retrieving an answer."""
    # Load the vector store
    vector_store = load_vector_store(persist_path)
    
    # Set up the text generator
    generator = setup_text_generator()
    
    # Run the custom RAG query
    answer, source_docs = custom_rag_query(vector_store, generator, question)
    
    # Print the results
    print(f"\nQuestion: {question}")
    print(f"Answer: {answer}")
    print("\nRetrieved Source Documents:")
    for i, doc in enumerate(source_docs, 1):
        print(f"{i}. {doc.page_content[:200]}... (from {doc.metadata.get('source', 'unknown')})")

if __name__ == "__main__":
    # Example question (customize based on your documents)
    test_question = "How does AI improve healthcare?"
    
    # Ensure the FAISS index exists
    if not os.path.exists("./faiss_index.faiss"):
        print("FAISS index not found. Please run update_vector_db.py first.")
    else:
        test_rag_question(test_question)