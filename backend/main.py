from fastapi import FastAPI, UploadFile, Form
from pypdf import PdfReader
from embeddings import embed_text
from vectorstore import collection
from openai import OpenAI
import os
from fastapi import HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

client = OpenAI()
uploaded_pdfs = set()

def search_vectorstore(query: str):
    """Search the stored PDFs using vector embeddings."""
    query_embedding = embed_text(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results = 5
    )
    return "\n\n".join(results["documents"][0])

app = FastAPI()

class AskBody(BaseModel):
    prompt: Optional[str] = None
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # IMPORTANT: allow OPTIONS, POST, GET, etc.
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)

# Upload PDF → chunk → embed → store in Chroma
@app.post("/upload")
async def upload_pdf(file: UploadFile):
    print(f"Received file: {file.filename}")

    # Save the PDF locally
    path = f"./uploads/{file.filename}"
    uploaded_pdfs.add(file.filename)
    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)

    print(f"Saved file to {path} ({len(contents)} bytes)")

    #
    # ====== EXTRACT TEXT USING PYMUPDF ======
    #
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
    except Exception as e:
        print("ERROR opening PDF with PyMuPDF:", e)
        raise HTTPException(400, "Invalid or corrupted PDF")

    chunks = []  # will store: (id, text, filename, page)

    try:
        for page_index, page in enumerate(doc):
            page_text = page.get_text("text")  # MUCH better extraction

            if page_text and page_text.strip():
                chunk_id = f"{file.filename}_page_{page_index}"
                chunks.append((chunk_id, page_text, file.filename, page_index))

        print(f"Extracted {len(chunks)} text chunks from {file.filename}")

    except Exception as e:
        print("ERROR extracting text:", e)
        raise HTTPException(500, "Failed to extract text from PDF")

    #
    # ====== STORE IN CHROMA WITH METADATA ======
    #
    try:
        for chunk_id, chunk_text, fname, page_num in chunks:
            emb = embed_text(chunk_text)

            collection.add(
                ids=[chunk_id],
                documents=[chunk_text],
                embeddings=[emb],
                metadatas=[{
                    "filename": fname,
                    "page": page_num
                }]
            )

        print(f"Stored {len(chunks)} chunks into Chroma")

    except Exception as e:
        print("CHROMA ERROR:", e)
        raise HTTPException(500, "Failed to save PDF chunks to vectorstore")

    return {
        "status": "ok",
        "filename": file.filename,
        "chunks_added": len(chunks)
    }



tools = [
    {
        "type": "function",
        "function": {
            "name": "search_vectorstore",
            "description": "Search the uploaded PDF content using semantic vector search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User question to search in the PDF"}
                },
                "required": ["query"]
            }
        }
    }
]

@app.post("/ask")
async def ask_question(body: AskBody):
    user_prompt = body.prompt

    if not user_prompt or user_prompt.strip() == "":
        raise HTTPException(400, "Prompt cannot be empty.")

    #
    # ==== FIRST CALL: force tool use ====
    #
    first = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI agent. You MUST always call the tool "
                    "`search_vectorstore` before answering. "
                    "Do not answer directly."
                )
            },
            {"role": "user", "content": user_prompt}
        ],
        tools=tools
    )

    assistant_msg = first.choices[0].message
    tool_calls = assistant_msg.tool_calls

    if tool_calls and len(tool_calls) > 0:
        tool_call = tool_calls[0]
        name = tool_call.function.name
        raw_args = tool_call.function.arguments

        try:
            args = eval(raw_args) if isinstance(raw_args, str) else raw_args
        except:
            args = {}

        query = args.get("query", user_prompt)

        #
        # ==== RETRIEVE MANY RESULTS (multi-PDF support) ====
        #
        query_embedding = embed_text(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=30  # ensures mixing chunks from multiple PDFs
        )

        #
        # ==== GROUP RESULTS BY FILENAME ====
        #
        grouped = {}

        documents = results["documents"]
        metadatas = results.get("metadatas", [])

        for row_docs, row_meta in zip(documents, metadatas):
            for doc, meta in zip(row_docs, row_meta):
                
                # Handle missing metadata safely
                if isinstance(meta, dict):
                    filename = meta.get("filename", "Unknown_File")
                    page = meta.get("page", 0)
                else:
                    filename = "Unknown_File"
                    page = 0

                if filename not in grouped:
                    grouped[filename] = {}

                grouped[filename][page] = doc


        #
        # ==== BUILD CLEAN GROUPED CONTEXT ====
        #
        formatted_context = ""

        for filename, pages in grouped.items():
            formatted_context += f"\n\n=== {filename} ===\n"
            for page_num in sorted(pages.keys()):
                formatted_context += f"\n[Page {page_num}]\n{pages[page_num]}\n"

        #
        # ==== SEND TO MODEL ====
        #
        tool_msg = {
            "role": "tool",
            "content": formatted_context
        }
        if hasattr(tool_call, "id"):
            tool_msg["tool_call_id"] = tool_call.id

        final = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Use ONLY the provided PDF context to answer. "
                        "The context is grouped by file and page."
                    )
                },
                {"role": "user", "content": user_prompt},
                assistant_msg,
                tool_msg
            ]
        )

        return {
            "answer": final.choices[0].message.content,
            "context": formatted_context,   # GROUPED CONTEXT
            "grouped": grouped             # Optional: structured form
        }

    # fallback
    return {
        "answer": assistant_msg.content,
        "context": None
    }


@app.get("/pdfs")
async def list_pdfs():
    return {"pdfs": list(uploaded_pdfs)}




        
