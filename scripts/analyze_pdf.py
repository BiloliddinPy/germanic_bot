from pypdf import PdfReader
import glob
import os

# Find PDF files in data directory
pdf_files = glob.glob("data/*.pdf")
print(f"Found {len(pdf_files)} PDF file(s):")
for f in pdf_files:
    print(f"  - {f}")

if not pdf_files:
    print("No PDF files found in data directory!")
    exit(1)

# Use the largest PDF (likely the dictionary)
pdf_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
PDF_PATH = pdf_files[0]
print(f"\nUsing: {PDF_PATH}")

try:
    reader = PdfReader(PDF_PATH)
    print(f"Number of pages: {len(reader.pages)}")
    
    # Extract text from the first 2 pages to understand structure
    for i in range(min(3, len(reader.pages))):
        page = reader.pages[i]
        text = page.extract_text()
        print(f"\n--- Page {i+1} ---\n")
        print(text[:1500]) # Print first 1500 chars

except Exception as e:
    print(f"Error reading PDF: {e}")
