from database import get_words_by_level, get_total_words_count

print("--- DEBUGGING DATABASE ---")

levels = ["A1", "A2", "B1"]
for level in levels:
    print(f"\nChecking Level: {level}")
    count = get_total_words_count(level)
    print(f"Total count: {count}")
    
    words = get_words_by_level(level, limit=5)
    print(f"First 5 words: {len(words)}")
    for w in words:
        print(f" - {w['de']} ({w['uz']})")

print("\n--- END DEBUG ---")
