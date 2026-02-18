# Botni 24/7 Ishlatish Bo'yicha Qo'llanma

Bot har doim ishlab turishi uchun ikkita asosiy yo'l bor:

## 1-usul: O'z kompyuteringizda (Vaqtinchalik)
Agar kompyuteringiz yoniq tursa, bot ishlaydi. Terminalni yopib qo'ysangiz ham ishlashi uchun `nohup` buyrug'idan foydalanish kerak.

**Ishga tushirish:**
```bash
sh run_background.sh
```
Bu buyruq botni "fon rejimida" ishga tushiradi. Terminalni yopsangiz ham bot o'chmaydi.

**To'xtatish:**
Botni o'chirish uchun avval uning ID raqamini (PID) topish va o'chirish kerak:
```bash
pkill -f main.py
```

---

## 2-usul: Serverda (VPS) - Professional Yechim ✅
Bot 24 soat uzluksiz ishlashi uchun uni **Virtual Server (VPS)** ga joylashtirish kerak. Bu yiliga taxminan $50-$60 turadi (masalan: DigitalOcean, Hetzner, Aeza).

**Qadamlar:**
1.  **Server olish**: Ubuntu 22.04 operatsion tizimli server sotib olasiz.
2.  **Fayllarni yuklash**: `germic_bot` papkasini serverga ko'chirasiz.
3.  **Systemd xizmatini yoqish**:
    Serverda bot o'chib qolmasligi uchun `systemd` yaratamiz.

`/etc/systemd/system/germanic.service` fayli:
```ini
[Unit]
Description=Germanic Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=/root/germanic_bot
ExecStart=/usr/bin/python3 /root/germanic_bot/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Keyin serverda:
```bash
sudo systemctl enable germanic
sudo systemctl start germanic
```

Shunda serveringiz o'chib-yonsa ham bot avtomatik ishlayveradi.
