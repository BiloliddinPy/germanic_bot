import sys
import os

# Add parent directory to path to import database.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import add_word, create_table

# Sample A1 Data (Expanded)
A1_WORDS = [
    ("A1", "der Morgen", "tong", "noun", "die Mörgen", "Guten Morgen!", "Xayrli tong!", "time"),
    ("A1", "der Abend", "oqshom", "noun", "die Abende", "Guten Abend!", "Xayrli kech!", "time"),
    ("A1", "der Apfel", "olma", "noun", "die Äpfel", "Der Apfel ist rot.", "Olma qizil.", "food"),
    ("A1", "das Buch", "kitob", "noun", "die Bücher", "Ich lese ein Buch.", "Men kitob o'qiyapman.", "education"),
    ("A1", "gehen", "bormoq", "verb", "", "Ich gehe zur Schule.", "Men maktabga ketyapman.", "action"),
    ("A1", "das Haus", "uy", "noun", "die Häuser", "Das Haus ist groß.", "Uy katta.", "family"),
    ("A1", "die Mutter", "ona", "noun", "die Mütter", "Meine Mutter ist nett.", "Mening onam mehribon.", "family"),
    ("A1", "der Vater", "ota", "noun", "die Väter", "Mein Vater arbeitet.", "Mening otam ishlaydi.", "family"),
    ("A1", "essen", "yemoq", "verb", "", "Wir essen Pizza.", "Biz pitsa yeyapmiz.", "action"),
    ("A1", "trinken", "ichmoq", "verb", "", "Er trinkt Wasser.", "U suv ichyapti.", "action"),
    ("A1", "sehen", "ko'rmoq", "verb", "", "Ich sehe dich.", "Men seni ko'ryapman.", "action"),
    ("A1", "hören", "eshitmoq", "verb", "", "Hörst du das?", "Buni eshityapsanmi?", "action"),
    ("A1", "schlafen", "uxlamoq", "verb", "", "Das Baby schläft.", "Chaqaloq uxlayapti.", "action"),
    ("A1", "lernen", "o'rganmoq", "verb", "", "Wir lernen Deutsch.", "Biz nemis tilini o'rganyapmiz.", "education"),
    ("A1", "schreiben", "yozmoq", "verb", "", "Ich schreibe eine E-Mail.", "Men elektron xat yozyapman.", "action"),
    ("A1", "sprechen", "gapirmoq", "verb", "", "Sprichst du Deutsch?", "Nemsicha gaplashasanmi?", "action"),
    ("A1", "kommen", "kelmoq", "verb", "", "Woher kommst du?", "Qayerdan kelding?", "action"),
    ("A1", "machen", "qilmoq", "verb", "", "Was machst du?", "Nima qilyapsan?", "action"),
    ("A1", "arbeiten", "ishlamoq", "verb", "", "Er arbeitet viel.", "U ko'p ishlaydi.", "action"),
    ("A1", "spielen", "o'ynamoq", "verb", "", "Die Kinder spielen.", "Bolalar o'ynamoqda.", "action"),
    ("A1", "kaufen", "sotib olmoq", "verb", "", "Ich kaufe Brot.", "Men non sotib olayapman.", "action"),
    ("A1", "wohnen", "yashamoq", "verb", "", "Ich wohne in Berlin.", "Men Berlinda yashayman.", "action"),
    ("A1", "heißen", "atalmoq (ism)", "verb", "", "Ich heiße Anna.", "Mening ismim Anna.", "action"),
    ("A1", "sein", "bo'lmoq", "verb", "", "Ich bin müde.", "Men charchadim.", "state"),
    ("A1", "haben", "bor bo'lmoq", "verb", "", "Ich habe Zeit.", "Mening vaqtim bor.", "state"),
    ("A1", "gut", "yaxshi", "adj", "", "Das ist gut.", "Bu yaxshi.", "common"),
    ("A1", "schlecht", "yomon", "adj", "", "Das Wetter ist schlecht.", "Ob-havo yomon.", "common"),
    ("A1", "groß", "katta", "adj", "", "Berlin ist groß.", "Berlin katta.", "common"),
    ("A1", "klein", "kichik", "adj", "", "Die Maus ist klein.", "Sichqoncha kichkina.", "common"),
    ("A1", "schön", "chiroyli", "adj", "", "Du bist schön.", "Sen chiroylisan.", "common"),
    ("A1", "neu", "yangi", "adj", "", "Das Auto ist neu.", "Mashina yangi.", "common"),
    ("A1", "alt", "eski/qari", "adj", "", "Er ist alt.", "U qari.", "common"),
    ("A1", "der Tisch", "stol", "noun", "die Tische", "Der Tisch ist braun.", "Stol jigarrang.", "furniture"),
    ("A1", "der Stuhl", "stul", "noun", "die Stühle", "Der Stuhl ist bequem.", "Stul qulay.", "furniture"),
    ("A1", "das Fenster", "deraza", "noun", "die Fenster", "Das Fenster ist offen.", "Deraza ochiq.", "furniture"),
    ("A1", "die Tür", "eshik", "noun", "die Türen", "Mach die Tür zu.", "Eshikni yop.", "furniture"),
    ("A1", "die Schule", "maktab", "noun", "die Schulen", "Die Schule beginnt um 8.", "Maktab 8 da boshlanadi.", "education"),
    ("A1", "der Schüler", "o'quvchi", "noun", "die Schüler", "Der Schüler lernt.", "O'quvchi o'rganyapti.", "education"),
    ("A1", "die Lehrerin", "o'qituvchi (ayol)", "noun", "die Lehrerinnen", "Die Lehrerin spricht.", "O'qituvchi gapiryapti.", "education"),
    ("A1", "der Lehrer", "o'qituvchi (erkak)", "noun", "die Lehrer", "Der Lehrer ist streng.", "O'qituvchi qattiqqo'l.", "education"),
    ("A1", "das Wasser", "suv", "noun", "", "Ich trinke Wasser.", "Men suv ichyapman.", "food"),
    ("A1", "das Brot", "non", "noun", "die Brote", "Das Brot ist frisch.", "Non yangi.", "food"),
    ("A1", "der Kaffee", "qahva", "noun", "", "Ich mag Kaffee.", "Men qahvani yoqtiraman.", "food"),
    ("A1", "der Tee", "choy", "noun", "", "Möchtest du Tee?", "Choy xohlaysanmi?", "food"),
    ("A1", "ja", "ha", "other", "", "Ja, bitte.", "Ha, iltimos.", "common"),
    ("A1", "nein", "yo'q", "other", "", "Nein, danke.", "Yo'q, rahmat.", "common"),
    ("A1", "danke", "rahmat", "other", "", "Danke schön!", "Katta rahmat!", "common"),
    ("A1", "bitte", "iltimos/marhamat", "other", "", "Bitte sehr.", "Arzimaydi.", "common"),
    ("A1", "hallo", "salom", "other", "", "Hallo, wie geht's?", "Salom, qalay?", "greeting"),
    ("A1", "tschüss", "xayr", "other", "", "Tschüss, bis morgen!", "Xayr, ertagacha!", "greeting"),
    ("A1", "der Montag", "dushanba", "noun", "", "Am Montag arbeite ich.", "Dushanbada ishlayman.", "time"),
    ("A1", "heute", "bugun", "adv", "", "Heute ist Samstag.", "Bugun shanba.", "time"),
    ("A1", "morgen", "ertaga", "adv", "", "Morgen habe ich frei.", "Ertaga bo'shman.", "time")
]

# Sample A2 Data
A2_WORDS = [
    ("A2", "der Urlaub", "ta'til", "noun", "die Urlaube", "Ich brauche Urlaub.", "Menga ta'til kerak.", "travel"),
    ("A2", "reisen", "sayohat qilmoq", "verb", "", "Wir reisen nach Deutschland.", "Biz Germaniyaga sayohat qilyapmiz.", "travel"),
    ("A2", "anrufen", "qo'ng'iroq qilmoq", "verb", "", "Ruf mich an.", "Menga qo'ng'iroq qil.", "communication"),
    ("A2", "einkaufen", "bozorlik qilmoq", "verb", "", "Ich gehe einkaufen.", "Men bozorlik qilishga ketyapman.", "daily_life"),
    ("A2", "der Bahnhof", "vokzal", "noun", "die Bahnhöfe", "Der Zug steht am Bahnhof.", "Poyezd vokzalda turibdi.", "travel"),
    ("A2", "der Arzt", "shifokor", "noun", "die Ärzte", "Ich muss zum Arzt.", "Men shifokorga borishim kerak.", "health"),
    ("A2", "die Gesundheit", "sog'liq", "noun", "", "Gesundheit ist wichtig.", "Sog'liq muhim.", "health"),
    ("A2", "einfach", "oson", "adj", "", "Deutsch ist nicht einfach.", "Nemis tili oson emas.", "common"),
    ("A2", "schwierig", "qiyin", "adj", "", "Die Prüfung war schwierig.", "Imtihon qiyin edi.", "common"),
    ("A2", "vielleicht", "balki", "adv", "", "Vielleicht komme ich später.", "Balki keyinroq kelarman.", "common")
]

def seed():
    print("Seeding database...")
    create_table() 
    
    count_a1 = 0
    for word in A1_WORDS:
        add_word(*word)
        count_a1 += 1
        
    count_a2 = 0
    for word in A2_WORDS:
        add_word(*word)
        count_a2 += 1
        
    print(f"Successfully added/updated {count_a1} A1 words.")
    print(f"Successfully added/updated {count_a2} A2 words.")
    print(f"Total: {count_a1 + count_a2} words.")

if __name__ == "__main__":
    seed()
