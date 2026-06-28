import os
from dotenv import load_dotenv
import json
import PyPDF2
from google import genai  # <-- Updated Library
from google.genai import types # <-- Add this import at the top of your file
from database import SessionLocal, Paper
from prompts import EXTRACTION_PROMPT

# --- Load the hidden .env file ---
load_dotenv()

# Pulls the key secretly from your environment variables
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(pdf_file_object):
    """Reads a PDF file object and extracts its text."""
    pdf_reader = PyPDF2.PdfReader(pdf_file_object)
    text = ""
    num_pages = min(len(pdf_reader.pages), 15)
    for page_num in range(num_pages):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() + "\n"
    return text

def parse_with_llm(raw_text, filename):
    """Sends the raw text to the LLM and returns a structured JSON dictionary."""
    full_prompt = f"{EXTRACTION_PROMPT}\n\nFilename: {filename}\n\nRaw Text:\n{raw_text}"
    
    try:
        # --- UPGRADED: Force strict JSON output ---
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        response_text = response.text.strip()
        
        # Because we forced JSON MIME type, we can usually load it directly
        return json.loads(response_text)
            
    except json.JSONDecodeError as e:
        print(f"\n--- JSON DECODE ERROR ---")
        print(f"Failed to parse the strictly formatted JSON. Details: {e}")
        return None
    except Exception as e:
        print(f"\n--- API OR PARSING ERROR ---")
        print(f"Exception: {e}")
        return None
            
    except Exception as e:
        print(f"\n--- LLM PARSING ERROR ---")
        print(f"Exception: {e}")
        return None

def save_to_database(extracted_json, filename):
    """Takes the clean JSON dictionary and saves it to the SQL database."""
    db = SessionLocal()
    try:
        # --- NEW: THE DUPLICATE CHECKER ---
        # Query the database to see if this filename already exists
        existing_paper = db.query(Paper).filter(Paper.file_reference == filename).first()
        if existing_paper:
            print(f"Skipping insert: {filename} already exists in the database.")
            return False, "This paper is already in your repository."
        
        # --- IF NO DUPLICATE, PROCEED WITH INSERTION ---
        new_paper = Paper(
            title=extracted_json["metadata"].get("title", "Unknown Title"),
            authors=", ".join(extracted_json["metadata"].get("authors", [])),
            year=extracted_json["metadata"].get("year", 0),
            domain=extracted_json["metadata"].get("domain", "Unknown"),
            sample_size=str(extracted_json["methodology"].get("sample_size", "")),
            technique=extracted_json["methodology"].get("estimation_technique", ""),
            variables=json.dumps(extracted_json.get("variables", {})),
            findings=" | ".join(extracted_json.get("key_findings", [])),
            limitations=json.dumps(extracted_json.get("limitations", {})),
            file_reference=filename
        )
        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
        return True, "Successfully processed and saved to database."
        
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
        return False, "Failed to save to database due to an error."
    finally:
        db.close()

def process_uploaded_pdf(pdf_file_object):
    """Master function to tie the whole pipeline together."""
    filename = pdf_file_object.name
    
    raw_text = extract_text_from_pdf(pdf_file_object)
    if not raw_text:
        return False, "Failed to extract text from PDF."
        
    extracted_data = parse_with_llm(raw_text, filename)
    if not extracted_data:
        return False, "Failed to parse data using LLM."
        
    # --- UPDATED: Catch both the success boolean and the specific message ---
    success, message = save_to_database(extracted_data, filename)
    
    return success, message