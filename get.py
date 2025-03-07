import json
import numpy as np
from langchain.embeddings import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import os

# Load the embedding model once
print("Loading model...")
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")

# File paths for caching
JSON_FILE = "companies.json"  # Update with your actual JSON file
EMBEDDINGS_FILE = "company_embeddings.npy"
NAMES_FILE = "company_names.json"

def load_company_data():
    """Load company names and symbols from the JSON file."""
    print("Loading company data...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_and_save_embeddings():
    """Generate and save embeddings for all company names to avoid recomputation."""
    company_data = load_company_data()
    
    company_names = list(company_data.keys())
    symbols = list(company_data.values())

    print("Generating embeddings (This runs only once)...")
    name_embeddings = np.array(embedding_model.embed_documents(company_names))

    # Save embeddings and company names
    np.save(EMBEDDINGS_FILE, name_embeddings)
    with open(NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump({"names": company_names, "symbols": symbols}, f)

    print("Embeddings saved!")

def load_embeddings():
    """Load precomputed embeddings and company names."""
    print("Loading precomputed embeddings...")
    name_embeddings = np.load(EMBEDDINGS_FILE)

    with open(NAMES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return name_embeddings, data["names"], data["symbols"]

# Precompute and store embeddings if not already done
if not os.path.exists(EMBEDDINGS_FILE) or not os.path.exists(NAMES_FILE):
    generate_and_save_embeddings()

# Load cached embeddings
name_embeddings, company_names, symbols = load_embeddings()

def get_top_matches(query, top_n=5):
    """Find the most matched company names using AI-based semantic similarity."""
    
    # Compute embedding for the query
    query_embedding = np.array(embedding_model.embed_query(query)).reshape(1, -1)

    # Compute cosine similarity using optimized sklearn function
    similarities = cosine_similarity(query_embedding, name_embeddings)[0]

    # Get top N matches
    top_indices = np.argsort(similarities)[::-1][:top_n]

    # Return matched company names with symbols
    results = [{"name": company_names[i], "symbol": symbols[i], "score": similarities[i]} for i in top_indices]
    
    return results

# Example Usage:
query = "Microsoft Corporation"
matches = get_top_matches(query)

print("Results:")
for match in matches:
    print(f"{match['name']} ({match['symbol']}) - Similarity Score: {match['score']:.4f}")

print("Done")
