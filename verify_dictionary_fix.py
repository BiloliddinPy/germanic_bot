import sys
import os
import logging

# Add current dir to path
sys.path.append(os.getcwd())

from database import create_table, bootstrap_words_if_empty
from database.repositories.word_repository import get_words_by_level_and_letter, get_total_words_count_by_letter

def test():
    logging.basicConfig(level=logging.INFO)
    print("Testing Dictionary Fix...")
    
    # Ensure tables exist
    create_table()
    
    # Run bootstrap
    count = bootstrap_words_if_empty()
    if count > 0:
        print(f"✅ Bootstrapped {count} words.")
    else:
        print("ℹ️ Bootstrap skipped (data already exists or error).")
        
    # Test filtering for 'A'
    level = 'A1'
    letter = 'A'
    
    total = get_total_words_count_by_letter(level, letter)
    print(f"Total words for '{level}' starting with '{letter}': {total}")
    
    words = get_words_by_level_and_letter(level, letter, limit=10)
    print(f"Found {len(words)} words:")
    for w in words:
        print(f" - {w['de']} ({w['uz']})")
        
    # Specific check for 'der Apfel'
    found_apfel = any(w['de'] == 'der Apfel' for w in words)
    if found_apfel:
        print("✅ 'der Apfel' found correctly under letter 'A'!")
    else:
        print("❌ 'der Apfel' NOT found under letter 'A'.")
        sys.exit(1)

if __name__ == "__main__":
    test()
