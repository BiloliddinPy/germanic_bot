from database.connection import get_connection

def get_quiz_options(word_id, limit=4):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, de, uz FROM words WHERE id = ?", (word_id,))
    target = cursor.fetchone()
    
    cursor.execute("SELECT id, uz FROM words WHERE id != ? ORDER BY RANDOM() LIMIT ?", (word_id, limit - 1))
    others = cursor.fetchall()
    conn.close()
    
    options = [{'id': r[0], 'text': r[1], 'correct': False} for r in others]
    options.append({'id': target[0], 'text': target[2], 'correct': True})
    import random
    random.shuffle(options)
    return {'word': target[1], 'options': options}

print(get_quiz_options(1))
