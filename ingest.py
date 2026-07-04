import os
import fitz  # PyMuPDF
from pptx import Presentation
from sentence_transformers import SentenceTransformer
import chromadb

DATA_FOLDER = "data"
CHROMA_PATH = "chroma_db"

# Load embedding model
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# Setup ChromaDB
client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection("aquanis_docs")

def chunk_text(text, chunk_size=400):
    words = text.split()
    return [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def read_pdf(path):
    doc = fitz.open(path)
    return "\n".join(page.get_text() for page in doc)

def read_pptx(path):
    prs = Presentation(path)
    text = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text.append(shape.text)
    return "\n".join(text)

# Process all files
all_chunks = []
all_ids = []
all_sources = []

for filename in os.listdir(DATA_FOLDER):
    filepath = os.path.join(DATA_FOLDER, filename)
    print(f"Reading: {filename}")

    if filename.endswith(".pdf"):
        text = read_pdf(filepath)
    elif filename.endswith(".pptx"):
        text = read_pptx(filepath)
    else:
        continue

    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        all_chunks.append(chunk)
        all_ids.append(f"{filename}_chunk_{i}")
        all_sources.append(filename)

# Embed and store
print(f"Embedding {len(all_chunks)} chunks...")
embeddings = model.encode(all_chunks).tolist()

collection.add(
    documents=all_chunks,
    embeddings=embeddings,
    ids=all_ids,
    metadatas=[{"source": s} for s in all_sources]
)

print("✅ Done! Aquanis has learned from your documents.") 
