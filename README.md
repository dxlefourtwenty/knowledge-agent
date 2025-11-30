# StudAI


## What is StudAI?

StudAI is a pdf-based summarizer that will break down topics for the user and offer them a step-by-step guide on how to study this topic effectively.
This project was made for CS4680 for the AI-Agent Project


## Requirements

Make sure the following are installed:  

Frontend:
  Node.js
  npm  

Backend:
  Python 3.9+
  pip


1. Clone the repo


2. cd backend/

3. create a virtual environment
    (powershell)
      - python -m venv .venv
      - .venv\Scripts\Activate

   (macOS/Linux/WSL)
      - source .venv/bin/activate

4. install dependencies
    - pip install -r requirements.txt


5. Set Up OpenAI API key
    - create a .env file in backend/
    - put 'OPENAI_API_KEY=[your-key-here]'

6. Run the FastAPI server
    - uvicorn main:app --reload
    - backend will run at http://127.0.0.1:8000


7. cd ../frontend

8. npm install

9. npm run dev

10. the frontend will start at: http://localhost:5173



