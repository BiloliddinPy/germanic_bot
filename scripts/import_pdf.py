from pypdf import PdfReader
import glob
import os
import sys
import re

# Add parent directory to path to import database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import add_word, create_table

# Find the largest PDF (17k dictionary)
pdf_files = glob.glob("data/*.pdf")
pdf_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
PDF_PATH = pdf_files[0]

print(f"Reading: {PDF_PATH}")

def extract_level_from_text(text):
    """Extract level (A1, A2, B1, B2, C1) from text."""
    match = re.search(r'\b(A[12]|B[12]|C1)\b', text)
    return match.group(1) if match else "A1"  # Default to A1 if not found

def parse_dictionary_line(line):
    """Parse a line like 'der Buchstabe - harf' into components."""
    # Pattern: German_word - uzbek_translation
    match = re.match(r'^(.+?)\s*-\s*(.+)$', line.strip())
    if match:
        de = match.group(1).strip()
        uz = match.group(2).strip()
        
        # Detect part of speech from articles
        pos = None
        if de.startswith('der '):
            pos = 'noun (m)'
        elif de.startswith('die '):
            pos = 'noun (f)'
        elif de.startswith('das '):
            pos = 'noun (n)'
        
        return {
            'de': de,
            'uz': uz,
            'pos': pos
        }
    return None

def import_from_pdf():
    create_table()
    
    try:
        reader = PdfReader(PDF_PATH)
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        
        current_level = "A1"
        word_count = 0
        
        for page_num in range(total_pages):
            page = reader.pages[page_num]
            text = page.extract_text()
            
            # Update level if found on this page
            detected_level = extract_level_from_text(text[:200])  # Check first 200 chars
            if detected_level:
                current_level = detected_level
            
            # Split into lines and process
            lines = text.split('\n')
            for line in lines:
                # Skip empty lines, page numbers, headers
                if not line.strip() or line.strip().isdigit():
                    continue
                if len(line.strip()) < 3:
                    continue
                    
                # Skip common header/footer patterns
                if any(x in line for x in ['@Nemis', 'Dilmurod', 'Lektion', 'MOTIVE', '---']):
                    continue
                
                # Try to parse as dictionary entry
                entry = parse_dictionary_line(line)
                if entry and entry['de'] and entry['uz']:
                    # Skip if German or Uzbek part is too long (likely not a word pair)
                    if len(entry['de']) > 80 or len(entry['uz']) > 80:
                        continue
                    
                    try:
                        add_word(
                            level=current_level,
                            de=entry['de'],
                            uz=entry['uz'],
                            pos=entry['pos'],
                            plural=None,
                            example_de=None,
                            example_uz=None,
                            category=None
                        )
                        word_count += 1
                        
                        if word_count % 100 == 0:
                            print(f"Imported {word_count} words... (Currently on level: {current_level})")
                    except Exception as e:
                        # Skip duplicates or errors
                        pass
            
            if (page_num + 1) % 20 == 0:
                print(f"Processed {page_num + 1}/{total_pages} pages")
        
        print(f"\n✅ Import complete! Total words imported: {word_count}")
        
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import_from_pdf()
