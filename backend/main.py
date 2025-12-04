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
from fastapi.responses import FileResponse
import uuid
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth

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

# Ensure absolute path for generated PDFs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(BASE_DIR, "generated")
os.makedirs(GENERATED_DIR, exist_ok=True)


@app.post("/ask")
async def ask_question(body: AskBody):
    user_prompt = body.prompt or ""

    if not user_prompt.strip():
        raise HTTPException(400, "Prompt cannot be empty.")

    #
    # ==== FIRST MODEL CALL (FORCE TOOL USE) ====
    #
    first = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an AI agent. You MUST call the tool `search_vectorstore` "
                    "before answering. Do NOT answer directly."
                )
            },
            {"role": "user", "content": user_prompt}
        ],
        tools=tools
    )

    assistant_msg = first.choices[0].message
    tool_calls = assistant_msg.tool_calls

    #
    # ==== ENSURE TOOL CALL ====
    #
    if not tool_calls:
        return {"error": "No tool call occurred."}

    tool_call = tool_calls[0]
    raw_args = tool_call.function.arguments

    try:
        args = eval(raw_args) if isinstance(raw_args, str) else raw_args
    except:
        args = {}

    query = args.get("query", user_prompt)

    #
    # ==== SEMANTIC SEARCH ====
    #
    query_embedding = embed_text(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=30
    )

    #
    # ==== GROUP RESULTS BY PDF + PAGE ====
    #
    grouped = {}
    retrieval_entries = []

    for row_docs, row_meta in zip(results["documents"], results["metadatas"]):
        for doc, meta in zip(row_docs, row_meta):

            if isinstance(meta, dict):
                filename = meta.get("filename", "Unknown_File")
                page = meta.get("page", 0)
            else:
                filename = "Unknown_File"
                page = 0

            # Save for PDF appendix
            retrieval_entries.append({
                "filename": filename,
                "page": page,
                "text": doc[:500]  # limit snippet length
            })

            # Group for context, same as before
            if filename not in grouped:
                grouped[filename] = {}
            grouped[filename][page] = doc

    #
    # ==== BUILD CLEAN CONTEXT ====
    #
    formatted_context = ""
    for filename, pages in grouped.items():
        formatted_context += f"\n\n=== {filename} ===\n"
        for page_num in sorted(pages.keys()):
            formatted_context += f"\n[Page {page_num}]\n{pages[page_num]}\n"

    #
    # ==== FINAL MODEL CALL (WITH CONTEXT) ====
    #
    tool_msg = {"role": "tool", "content": formatted_context}
    if hasattr(tool_call, "id"):
        tool_msg["tool_call_id"] = tool_call.id

    final = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": (
                    "Use ONLY the provided PDF context. "
                    "Do NOT include headings. Begin immediately with the explanation."
                )
            },
            {"role": "user", "content": user_prompt},
            assistant_msg,
            tool_msg
        ]
    )

    answer_text = final.choices[0].message.content

    #
    # ==== GENERATE PDF WITH WRAPPED TEXT ====
    #
    pdf_id = uuid.uuid4().hex
    pdf_path = os.path.join(GENERATED_DIR, f"answer_{pdf_id}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - inch

    # Margins
    left_margin = 1 * inch
    max_width = width - 2 * inch  # left + right margins

    #
    # Helper: Wrapped Text Renderer
    #
    def draw_wrapped(text, y):
        c.setFont("Helvetica", 11)
        for paragraph in text.split("\n"):
            words = paragraph.split()
            line = ""

            for w in words:
                test_line = (line + " " + w).strip()
                if stringWidth(test_line, "Helvetica", 11) <= max_width:
                    line = test_line
                else:
                    c.drawString(left_margin, y, line)
                    y -= 0.2 * inch

                    if y < 1 * inch:
                        c.showPage()
                        c.setFont("Helvetica", 11)
                        y = height - inch

                    line = w

            if line:
                c.drawString(left_margin, y, line)
                y -= 0.2 * inch

            y -= 0.1 * inch  # paragraph spacing

            if y < 1 * inch:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - inch

        return y

    #
    # ==== PDF TITLE ====
    #
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_margin, y, "StudAI Generated Answer")
    y -= 0.5 * inch

    #
    # ==== USER QUESTION (WRAPPED) ====
    #
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, y, "Your Question:")
    y -= 0.35 * inch

    y = draw_wrapped(user_prompt, y)

    #
    # Separator
    #
    c.setFont("Helvetica", 11)
    c.drawString(left_margin, y, "-" * 70)
    y -= 0.35 * inch

    #
    # ==== GENERATED ANSWER (WRAPPED) ====
    #
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left_margin, y, "Generated Explanation:")
    y -= 0.35 * inch

    y = draw_wrapped(answer_text, y)
    
    # ==== APPENDIX: SOURCES USED ====
    c.showPage()  # start a fresh page
    y = height - inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, y, "Appendix: Sources Used")
    y -= 0.5 * inch

    c.setFont("Helvetica", 11)

    for entry in retrieval_entries:
        # Filename + Page Number
        header = f"{entry['filename']} — Page {entry['page']}"
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1 * inch, y, header)
        y -= 0.25 * inch

        # Text Snippet (wrapped)
        snippet = entry["text"].replace("\n", " ")

        # Wrapped text logic
        words = snippet.split()
        line = ""
        while words:
            word = words.pop(0)
            test_line = (line + " " + word).strip()

            if stringWidth(test_line, "Helvetica", 11) <= max_width:
                line = test_line
            else:
                c.setFont("Helvetica", 11)
                c.drawString(1 * inch, y, line)
                y -= 0.2 * inch

                if y < 1 * inch:
                    c.showPage()
                    y = height - inch

                line = word

        # Final leftover text
        if line:
            c.setFont("Helvetica", 11)
            c.drawString(1 * inch, y, line)
            y -= 0.3 * inch

        # Spacing between entries
        y -= 0.2 * inch

        # Page break if necessary
        if y < 1 * inch:
            c.showPage()
            y = height - inch


    c.save()

    #
    # ==== RETURN PDF ====
    #
    return FileResponse(
        pdf_path,
        filename="studai_answer.pdf",
        media_type="application/pdf"
    )


@app.get("/pdfs")
async def list_pdfs():
    return {"pdfs": list(uploaded_pdfs)}




        
