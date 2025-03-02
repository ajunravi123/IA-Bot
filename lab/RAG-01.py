import os
import faiss
import numpy as np
from pathlib import Path
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader, PyPDFLoader, CSVLoader
import glob
import re

# Define input directory and output paths
input_dir = Path("./data")
output_dir = Path("./vindex")  # Store index and clean file in same directory
output_dir.mkdir(parents=True, exist_ok=True)

# Define output file paths (generic names)
index_file = output_dir / "combined_index.index"
splitted_para_file = output_dir / "combined_clean.txt"

print("Starting...")

# Helper function to clean text
def clean_text(text: str) -> str:
    """Normalize whitespace and paragraph breaks."""
    text = re.sub(r'\s+', ' ', text).strip()
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return '\n\n'.join(paragraphs)

# Helper function to load a document based on extension
def load_document(file_path: Path):
    """Load a document and return its text content."""
    extension = file_path.suffix.lower()
    try:
        if extension == '.txt':
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            return clean_text(docs[0].page_content)
        elif extension == '.pdf':
            loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            return clean_text(" ".join([doc.page_content for doc in docs]))
        elif extension == '.csv':
            loader = CSVLoader(str(file_path))
            docs = loader.load()
            return clean_text(" ".join([doc.page_content for doc in docs]))
        else:
            print(f"Skipping unsupported file: {file_path} (Supported: .txt, .pdf, .csv)")
            return None
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

# Find all supported files in the input directory
print(f"Scanning {input_dir.resolve()} for files...")
supported_patterns = [
    str(input_dir / "**/*.txt"),
    str(input_dir / "**/*.pdf"),
    str(input_dir / "**/*.csv")
]
all_files = []
for pattern in supported_patterns:
    all_files.extend(glob.glob(pattern, recursive=True))

if not all_files:
    raise FileNotFoundError(f"No supported files (.txt, .pdf, .csv) found in {input_dir.resolve()}")

# Load and process all documents
documents = []
for file_path in all_files:
    file_path = Path(file_path)
    print(f"Processing {file_path}...")
    text = load_document(file_path)
    if text:
        documents.append(text)

if not documents:
    raise ValueError("No valid content extracted from files.")

# Split text into chunks
print("Splitting files...")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""],
    keep_separator=True
)
all_chunks = []
for doc in documents:
    chunks = text_splitter.split_text(doc)
    all_chunks.extend(chunks)

if not all_chunks:
    raise ValueError("No chunks generated from the documents.")
print(f"Generated {len(all_chunks)} chunks")

# Embed chunks
print("Embedding...")
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")
try:
    document_embeddings = embedding_model.embed_documents(all_chunks)
except Exception as e:
    raise RuntimeError(f"Failed to generate embeddings: {e}")

# Convert embeddings to NumPy array and verify dimensions
document_embeddings = np.array(document_embeddings, dtype=np.float32)
embedding_dim = document_embeddings.shape[1]
expected_dim = 768  # BAAI/bge-base-en should output 768
if embedding_dim != expected_dim:
    raise ValueError(f"Embedding dimension mismatch: expected {expected_dim}, got {embedding_dim}")
print(f"Embedded {len(all_chunks)} chunks with dimension {embedding_dim}")

# Create FAISS Index
print("Saving index...")
index = faiss.IndexFlatL2(embedding_dim)
index.add(document_embeddings)

# Save FAISS index
faiss.write_index(index, str(index_file))
print(f"Index file generated: {index_file.resolve()} with {index.ntotal} vectors")

# Save split text
print("Generating split document...")
with splitted_para_file.open("w", encoding="utf-8") as f:
    for chunk in all_chunks:
        cleaned_chunk = chunk.strip()
        if cleaned_chunk:
            f.write(cleaned_chunk + "\n")
print(f"Split document saved: {splitted_para_file.resolve()}")

print("Task completed successfully")