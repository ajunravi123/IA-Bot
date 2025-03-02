# update_vector_db.py (with incremental updates)
from langchain.document_loaders import TextLoader, PyPDFLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
import os
import glob

def update_vector_db(documents_dir="documents", persist_path="./faiss_index.faiss"):
    """Incrementally update the FAISS vector database with documents from the specified directory."""
    # Helper function to load a document based on its extension
    def load_document(file_path):
        extension = file_path.lower()
        if extension.endswith('.pdf'):
            return PyPDFLoader(file_path).load()
        elif extension.endswith('.txt'):
            return TextLoader(file_path).load()
        elif extension.endswith('.csv'):
            return CSVLoader(file_path).load()
        else:
            print(f"Skipping unsupported file: {file_path} (Only PDF, TXT, and CSV are supported)")
            return None

    # Load embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Check if an existing FAISS index exists
    if os.path.exists(persist_path):
        print(f"Loading existing FAISS index from {persist_path}")
        vector_store = FAISS.load_local(persist_path, embeddings, allow_dangerous_deserialization=True)
    else:
        print(f"No existing FAISS index found at {persist_path}. Creating a new one.")
        vector_store = None

    # Use glob to recursively find all files in the directory
    supported_patterns = [
        os.path.join(documents_dir, "**/*.pdf"),
        os.path.join(documents_dir, "**/*.txt"),
        os.path.join(documents_dir, "**/*.csv")
    ]
    raw_documents = []
    for pattern in supported_patterns:
        for file_path in glob.glob(pattern, recursive=True):
            docs = load_document(file_path)
            if docs is not None:
                raw_documents.extend(docs if isinstance(docs, list) else [docs])

    if not raw_documents:
        print("No supported documents (PDF, TXT, CSV) found in the directory.")
        if vector_store is None:
            print("No existing index and no new documents to process. Exiting.")
            return
        else:
            print("No new documents to add. Saving existing index unchanged.")
            vector_store.save_local(persist_path)
            return

    # Process raw documents into Document objects
    documents = []
    for doc in raw_documents:
        if isinstance(doc, Document):
            documents.append(doc)
        elif isinstance(doc, list) and all(isinstance(d, Document) for d in doc):
            documents.extend(doc)
        else:
            print(f"Skipping invalid document format: {doc}")
            continue

    if not documents:
        print("No valid Document objects found after processing.")
        if vector_store is None:
            print("No existing index and no valid documents to process. Exiting.")
            return
        else:
            print("No new valid documents to add. Saving existing index unchanged.")
            vector_store.save_local(persist_path)
            return

    # Debug: Verify processed documents
    print(f"Processed documents: {len(documents)}")
    for doc in documents[:5]:
        print(f"Processed document type: {type(doc)}, Content preview: {getattr(doc, 'page_content', 'No content')[:100]}...")

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    # If no existing vector store, create a new one; otherwise, update the existing one
    if vector_store is None:
        vector_store = FAISS.from_documents(chunks, embeddings)
        print("Created new FAISS index.")
    else:
        vector_store.add_documents(chunks)
        print(f"Added {len(chunks)} new chunks to existing FAISS index.")

    # Persist the updated FAISS index to disk
    vector_store.save_local(persist_path)
    print(f"FAISS vector database updated and saved to {persist_path} using HuggingFaceEmbeddings")

if __name__ == "__main__":
    # Ensure the documents directory exists
    if not os.path.exists("documents"):
        os.makedirs("documents")
        print("Created 'documents' directory. Please add PDF, TXT, or CSV files and run again.")
    else:
        update_vector_db()