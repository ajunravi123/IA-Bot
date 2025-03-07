import json
import numpy as np
from langchain.embeddings import HuggingFaceEmbeddings

# Load the embedding model
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-base-en")

def load_company_data(json_file):
    """Load company names and symbols from a JSON file."""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def cosine_similarity(query_embedding, name_embeddings):
    """Compute cosine similarity between query and stored embeddings."""
    query_norm = np.linalg.norm(query_embedding)
    name_norms = np.linalg.norm(name_embeddings, axis=1)
    dot_products = np.dot(name_embeddings, query_embedding)
    similarities = dot_products / (name_norms * query_norm)
    return similarities

def get_top_matches(query, json_file, top_n=5):
    """Find the most matched company names using AI-based semantic similarity."""
    company_data = load_company_data(json_file)
    
    company_names = list(company_data.keys())  # Extract company names
    symbols = list(company_data.values())      # Extract symbols
    
    # Compute embeddings for all company names
    name_embeddings = np.array(embedding_model.embed_documents(company_names))
    
    # Compute embedding for query
    query_embedding = np.array(embedding_model.embed_query(query))
    
    # Compute cosine similarity
    similarities = cosine_similarity(query_embedding, name_embeddings)
    
    # Get top N matches
    top_indices = np.argsort(similarities)[::-1][:top_n]
    
    # Return matched company names with symbols
    results = [{"name": company_names[i], "symbol": symbols[i], "score": similarities[i]} for i in top_indices]
    
    return results

# Example Usage:
json_file = "companies.json"  # Your JSON file path
query = "Microsoft Corporation"
matches = get_top_matches(query, json_file)

# Display results
for match in matches:
    print(f"{match['name']} ({match['symbol']}) - Similarity Score: {match['score']:.4f}")
