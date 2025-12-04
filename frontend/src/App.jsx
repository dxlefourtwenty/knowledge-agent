import './App.css'
import { useState } from 'react'
import axios from "axios";

function App() {
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const [isFileUploaded, setIsFileUploaded] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [loadingAnswer, setLoadingAnswer] = useState(false);

  const [context, setContext] = useState("");

  const [pdfList, setPdfList] = useState([]);

  const [lastDownloaded, setLastDownloaded] = useState(null);

  const upload = async () => {
    if (!file) return;

    setUploading(true);

    const form = new FormData();
    form.append("file", file);

    try {
      await axios.post("http://localhost:8000/upload", form);

      const listRes = await axios.get("http://localhost:8000/pdfs");
      setPdfList(listRes.data.pdfs);
  
      setIsFileUploaded(true);

    } catch (err) {
      console.error(err);
      alert("File upload failed.");

    } finally {
      setUploading(false);
    }
  };

  const ask = async () => {
    setLoadingAnswer(true);

    try {
      const res = await axios.post(
        "http://localhost:8000/ask",
        { prompt: question },
        { responseType: "blob" }
      );

      // Extract filename from headers
      const cd = res.headers["content-disposition"];
      let filename = "studai_answer.pdf";
      if (cd) {
        const match = cd.match(/filename="?(.+)"?/);
        if (match) filename = match[1];
      }

      // Convert blob → downloadable link
      const pdfBlob = new Blob([res.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(pdfBlob);

      // Auto-download the file
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();

      // Save download info so user can re-download
      setLastDownloaded({ url, filename });

      // Clear UI-based text
      setAnswer("");
      setContext({});

    } catch (err) {
      console.error(err);
      alert("Failed to generate PDF.");
    } finally {
      setLoadingAnswer(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center gap-10 pt-10">
      <div className="text-6xl font-bold text-white">Stud AI</div>

      <div className="text-white text-lg flex flex-col gap-5 text-center">
        <div className="font-medium flex flex-col items-center justify-center">
          <div>Welcome to StudAI!</div>
          <div>Your #1 study buddy!</div>
        </div>
        <div>
          Simply upload one or a couple PDF files below, then our service will interpret the topic, summarize and break it down it for you.
          <div>
            Stud AI will also provide study suggestions tailored to the topic at hand if prompted.
          </div>
          <div className="mt-3">
            Add any additional questions you might have as well and it will be sure to answer it.
          </div>
          <div>
            Make sure to scroll down and see the 'sources used' section!
          </div>
          <div className="mt-3">
            The agent will download the file automatically for you to browse and study.
          </div>
        </div>
      </div>

      <div className="flex justify-center items-center gap-10">
        <div className="flex justify-center items-center gap-2">
          <label className="inline-flex items-center justify-center px-2 py-1 
            rounded-md border border-slate-500 gap-2
            hover:bg-gray-800">
            <input 
              type="file" 
              onChange={(e) => {
                setFile(e.target.files[0]);
                setIsFileUploaded(false);
              }} 
              className="sr-only"
            />
            <div className="text-white text-xl">Choose File</div>
          </label>

          {/**Filename */}
          {file && (
            <div className="text-white text-lg">
              {file.name}
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-2">
          <button 
            onClick={upload}
            disabled={uploading}
            className="text-gray-900 text-xl cursor-pointer border-slate-500 border-2 px-2 
              hover:outline-2 hover:outline-white font-bold hover:scale-105 transition-transform rounded-md bg-blue-400"
          >
            {uploading ? "Uploading..." : "Upload PDF"}
          </button>
          {isFileUploaded && (
            <div className="text-white text-lg">
              ✓
            </div>
          )}
        </div>
      </div>

      <div>
        {pdfList.length > 0 && (
          <div className="text-white border border-slate-700 rounded-lg p-3 bg-gray-900/40 w-[300px]">
            <div className="text-lg font-bold text-blue-300 mb-2">Uploaded PDFs</div>
            <ul className="list-disc pl-5 text-sm">
              {pdfList.map((pdf, idx) => (
                <li key={idx}>{pdf}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-5 items-center justify-center">
        <textarea 
          placeholder="Additional questions..."
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value)

            e.target.style.height = "auto";
            e.target.style.height = e.target.scrollHeight + "px";
          }}
          className="min-h-50 w-[500px] border border-slate-500 rounded-md text-white text-xl px-2 py-1 hover:bg-gray-800"
        />
        <div className="flex justify-center items-center gap-2">
          <button 
            onClick={ask}
            className={`text-gray-800 text-xl border-slate-500 border-2 px-5
              font-bold transition-transform rounded-md bg-blue-400
              ${loadingAnswer ? "opacity-50 cursor-not-allowed": "cursor-pointer hover:outline-2 hover:outline-white hover:scale-105"}`}
          >
            {loadingAnswer ? "Generating..." : "Generate"}
          </button>
          {loadingAnswer && <div className="text-white">⏳</div>}
        </div>
      </div>

      {lastDownloaded && (
        <div className="text-green-400 mt-3 text-center">
          <div className="font-bold text-xl">✔ PDF Generated!</div>

          <button
            onClick={() => {
              const a = document.createElement("a");
              a.href = lastDownloaded.url;
              a.download = lastDownloaded.filename;
              a.click();
            }}
            className="mt-2 px-4 py-2 bg-blue-400 hover:outline-white hover:outline-2 hover:scale-105
              transition-transform cursor-pointer text-gray-800 rounded-md font-bold border-slate-500 border-2"
          >
            Download Again
          </button>

          <div className="text-sm text-gray-400 mt-1">
            ({lastDownloaded.filename})
          </div>
        </div>
      )}

      <div className="text-white font-medium flex flex-col justify-center items-center">
        {context && Object.keys(context).length > 0 && (
          <div className="text-white max-w-[70%] mt-5">
            <div className="text-2xl font-bold text-blue-300 mb-3">
              Sources Used
            </div>

            {Object.entries(context).map(([filename, pages]) => (
              <div key={filename} className="mb-4 border border-slate-700 rounded-lg p-3 bg-gray-900/40">

                {/* FILENAME */}
                <div className="text-xl font-semibold text-blue-200 mb-2">
                  📘 {filename}
                </div>

                {/* PAGES */}
                {Object.entries(pages)
                  .sort((a, b) => Number(a[0]) - Number(b[0]))
                  .map(([pageNum, text]) => (
                    <details 
                      key={pageNum} 
                      className="mb-2 cursor-pointer bg-gray-800 p-2 rounded-md"
                    >
                      <summary className="text-white font-medium">
                        Page {pageNum}
                      </summary>

                      <pre className="bg-gray-900/50 whitespace-pre-wrap mt-2 p-3 text-sm rounded-md border border-slate-600">
                        {text}
                      </pre>
                    </details>
                ))}

              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

}

export default App;
