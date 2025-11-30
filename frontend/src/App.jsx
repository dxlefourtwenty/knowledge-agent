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

  const upload = async () => {
    if (!file) return;

    setUploading(true);

    const form = new FormData();
    form.append("file", file);

    try {
      await axios.post("http://localhost:8000/upload", form);
  
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
      const res = await axios.post("http://localhost:8000/ask", {
        prompt: question
      });
  
      setAnswer(res.data.answer);

    } catch (err) {
      console.error(err);
      alert("Failed to add additional questions.")

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
          Simply upload a PDF file below, then our service will interpret the topic, summarize and break it down it for you.
          <div>
            Stud AI will also provide study suggestions tailored to the topic at hand.
          </div>
          <div className="mt-3">
            Add any additional questions you might have as well and it will be sure to answer it as well.
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


      <div className="flex flex-col gap-5 items-center justify-center">
        <input 
          placeholder="Additional questions..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="border border-slate-500 rounded-md text-white text-xl px-2 py-1 hover:bg-gray-800"
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

      <div className="text-white font-medium flex flex-col justify-center items-center">
        <div className="text-xl">Answer Below:</div> 
        {answer && (
          <div className="prose prose-invert max-w-[60%]">
            <pre className="bg-gray-900/40 whitespace-pre-wrap px-15 py-4 border border-slate-600 mt-2 leading-relaxed rounded-xl">
              {answer}
            </pre>
          </div>
        )}
      </div>
    </div>
  );

}

export default App;
