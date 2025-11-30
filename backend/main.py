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

    # Save file
    path = f"./uploads/{file.filename}"
    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)

    print(f"Saved to: {path}, size={len(contents)} bytes")

    # Extract text
    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        print(f"Extracted text length: {len(text)}")
    except Exception as e:
        print("PDF ERROR:", e)
        raise HTTPException(400, "Invalid PDF")

    # Embed
    try:
        emb = embed_text(text)
        print(f"Embedding length: {len(emb)}")
    except Exception as e:
        print("EMBEDDING ERROR:", e)
        raise HTTPException(500, "Embedding failed")

    # Save to Chroma
    try:
        collection.add(
            ids=[file.filename],
            documents=[text],
            embeddings=[emb]
        )
        print("Successfully added to vectorstore")
    except Exception as e:
        print("CHROMA ERROR:", e)
        raise HTTPException(500, "Vectorstore failed")

    return {"status": "ok"}

# Ask a question → retrieve context → LLM answer
@app.post("/ask")
async def ask_question(body: AskBody):
    prompt = body.prompt

    if not prompt or prompt.strip() == "":
        results = collection.query(query_embeddings =[embed_text("summary")], n_results = 5)
        context = "\n\n".join(results["documents"][0])
        
        completion = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a very knowledgeable assistant in any field. Fine-tune your answer to explain to somebody who is not an expert in this field. Add any additional explanation for clarity. At the end, add some study suggestions and outline each step clearly."},
                {"role": "user", "content": f"Context:\n{context}\n"}
            ]
        )
        
        answer = completion.choices[0].message.content
        return {"answer": answer, "context": results["documents"][0]}
    else:
        query_embedding = embed_text(prompt)
        results = collection.query(query_embeddings=[query_embedding], n_results=5)
        context = "\n\n".join(results["documents"][0])

        completion = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a very knowledgeable assistant in any field. Only answer using the provided context. Fine-tune your answer to explain to somebody who is not an expert in this field. Add any additional explanation for clarity. At the end add some study stuggestions and outline each step clearly."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {prompt}"}
            ]
        )

        answer = completion.choices[0].message.content
        return {"answer": answer, "context": results["documents"][0]}
        
