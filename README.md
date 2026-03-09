# 🏠 OLX.ba Apartment Watcher

Automatski prati oglase za iznajmljivanje stanova na OLX.ba i šalje notifikacije čim se pojavi novi oglas — svako **5 minuta**, potpuno besplatno.

Podržava **Email** i/ili **Telegram** notifikacije — koristi ono što ti odgovara.

## Kako radi

1. **GitHub Actions** pokreće Python skriptu svakih 5 minuta
2. Skripta otvara tvoju OLX.ba pretragu (sa svim filterima)
3. Izvlači ID-eve svih oglasa sa stranice
4. Poredi sa prethodnim rezultatima (sačuvanim u `seen_ids.json`)
5. Za svaki **novi** oglas → šalje email i/ili Telegram poruku sa linkom

## Preduvjeti

- GitHub račun (besplatan)
- Email adresa (za email notifikacije) ILI Telegram (za Telegram notifikacije)
- ~15 minuta za setup

---

## Korak po korak setup

### 1. Odaberi način notifikacije

Možeš koristiti **Email**, **Telegram**, ili **oboje**.

---

### Opcija A: Email notifikacije (preporučeno — najjednostavnije)

#### Gmail setup

1. Otvori [myaccount.google.com/security](https://myaccount.google.com/security)
2. Uključi **2-Step Verification** (ako nisi već)
3. Idi na [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Kreiraj novu App Password:
   - Ime: `OLX Watcher`
   - Klikni **Create**
5. Kopiraj 16-znakovni password (npr. `abcd efgh ijkl mnop`) — **sačuvaj ga!**

Ti ćeš trebati ove podatke za Secrets (korak 4):

| Secret | Vrijednost |
|--------|-----------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `tvoj.email@gmail.com` |
| `SMTP_PASS` | App Password iz koraka 5 (bez razmaka) |
| `EMAIL_TO` | Email na koji želiš primati obavijesti |

#### Outlook/Hotmail setup

| Secret | Vrijednost |
|--------|-----------|
| `SMTP_HOST` | `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `tvoj.email@outlook.com` |
| `SMTP_PASS` | Tvoja lozinka (ili App Password ako imaš 2FA) |
| `EMAIL_TO` | Email na koji želiš primati obavijesti |

#### Yahoo setup

| Secret | Vrijednost |
|--------|-----------|
| `SMTP_HOST` | `smtp.mail.yahoo.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | `tvoj.email@yahoo.com` |
| `SMTP_PASS` | App Password (kreiraj na Yahoo Account Security) |
| `EMAIL_TO` | Email na koji želiš primati obavijesti |

---

### Opcija B: Telegram notifikacije

1. Otvori Telegram i pronađi **@BotFather**
2. Pošalji mu `/newbot`
3. Odaberi ime (npr. "OLX Watcher") i username (npr. `olx_zenica_watcher_bot`)
4. BotFather ti daje **API token** — sačuvaj ga! Izgleda ovako:
   ```
   7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

#### Dobij svoj Telegram Chat ID

1. Pošalji bilo kakvu poruku svom novom botu (npr. "hello")
2. Otvori u browseru:
   ```
   https://api.telegram.org/bot<TVOJ_TOKEN>/getUpdates
   ```
   (zamijeni `<TVOJ_TOKEN>` sa stvarnim tokenom iz koraka 1)
3. U JSON odgovoru pronađi `"chat": { "id": 123456789 }` — to je tvoj **Chat ID**

### 2. Kreiraj GitHub repozitorij

1. Idi na [github.com/new](https://github.com/new)
2. Ime: `olx-watcher` (ili šta god hoćeš)
3. Označi **Private** (privatni repo — neće trošiti tvoje GitHub Actions minute)
   
   > ⚠️ **Napomena o minutama**: Privatni repos imaju **2000 minuta/mjesec** besplatno. Svaki run traje ~1-2 min, pa ~8600 runova/mjesec = ~170-340 sati. To je blizu limita. Ako želiš biti siguran, koristi **Public** repo (neograničene minute) — nema nikakvih sigurnosnih problema jer su tokeni u Secrets.

4. Klikni **Create repository**

### 3. Uploadaj fajlove

Uploadaj sve fajlove iz ovog foldera u repo. Najlakše putem terminala:

```bash
# Kloniraj repo
git clone https://github.com/TVOJ_USERNAME/olx-watcher.git
cd olx-watcher

# Kopiraj fajlove (ili downloadaj ZIP koji sam ti dao)
# Struktura treba biti:
# olx-watcher/
# ├── .github/
# │   └── workflows/
# │       └── check.yml
# ├── scraper.py
# ├── requirements.txt
# ├── seen_ids.json
# └── README.md

# Pushaj na GitHub
git add .
git commit -m "Initial commit"
git push
```

Ili koristi GitHub web interface — "Add file" > "Upload files".

### 4. Dodaj Secrets u GitHub

1. Idi u svoj repo na GitHubu
2. **Settings** → **Secrets and variables** → **Actions**
3. Klikni **New repository secret** i dodaj secrets za tvoj odabrani kanal:

**Za Email (Opcija A) — dodaj ovih 5:**

| Ime | Vrijednost |
|-----|---------|
| `SMTP_HOST` | Npr. `smtp.gmail.com` |
| `SMTP_PORT` | `587` (ili `465` za Yahoo) |
| `SMTP_USER` | Tvoja email adresa |
| `SMTP_PASS` | App Password (NE tvoja obična lozinka!) |
| `EMAIL_TO` | Email na koji želiš primati notifikacije |

**Za Telegram (Opcija B) — dodaj ova 2:**

| Ime | Vrijednost |
|-----|---------|
| `TELEGRAM_BOT_TOKEN` | Token iz BotFathera |
| `TELEGRAM_CHAT_ID` | Chat ID (broj) |

> 💡 Možeš dodati i Email i Telegram — skripta šalje na **sve** konfigurirane kanale.

### 5. (Opcionalno) Prilagodi URL pretrage

Ako želiš pratiti drugačiju pretragu, idi u:
**Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New repository variable**

| Ime | Vrijednost |
|-----|---------|
| `OLX_SEARCH_URL` | Tvoj OLX.ba URL pretrage sa filterima |

Default je već podešen na tvoj URL za iznajmljivanje stanova u Zenici.

### 6. Pokreni prvi put (ručno)

1. Idi na **Actions** tab u svom repu
2. Klikni **OLX.ba Apartment Watcher** u lijevom meniju
3. Klikni **Run workflow** → **Run workflow**
4. Sačekaj ~1-2 min
5. Na Telegramu ćeš dobiti poruku: "✅ OLX Watcher pokrenut!"

Od sad, skripta se automatski pokreće svakih 5 minuta!

---

## Kako izgleda notifikacija

**Email** — dobijete formatiran HTML email sa svim novim oglasima u jednoj poruci:

> **🏠 3 nova oglasa na OLX.ba!**
>
> **Stan za iznajmljivanje, 50m2, centar**
> 💰 350 KM
> 🔗 https://olx.ba/artikal/12345678
>
> **Garsonjera blizu fakulteta**
> 💰 200 KM
> 🔗 https://olx.ba/artikal/12345679

**Telegram** — svaki oglas dolazi kao zasebna poruka:

```
🏠 Novi oglas na OLX.ba!

📌 Stan za iznajmljivanje, 50m2, centar
💰 350 KM
🔗 https://olx.ba/artikal/12345678
```

## Troubleshooting

### "No listings found"
OLX.ba je SPA (Single Page Application) — sadržaj se učitava JavaScriptom. Skripta koristi Playwright (headless browser) za renderovanje. Ako ne radi:
- Provjeri Actions log za detalje greške
- Možda je OLX.ba promijenio strukturu stranice

### GitHub Actions se ne pokreće
- Provjeri da je workflow fajl na pravom putu: `.github/workflows/check.yml`
- Idi na Actions tab i provjeri da workflow nije disabled
- GitHub ponekad ima delay od par minuta za cron schedule

### Ne dobijam Telegram poruke
- Provjeri da si poslao barem jednu poruku botu prije setupa
- Provjeri da su TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID ispravno uneseni u Secrets
- Pogledaj Actions log — ako vidiš "[WARN] Telegram credentials not set", secrets nisu pronađeni

### Previše commitova u repou
Svaki run koji pronađe promjene commituje `seen_ids.json`. Ovo je normalno. Ako te smeta, možeš periodično squashati commitove.

## Prilagodba

### Promijeni interval provjere
U `.github/workflows/check.yml`, izmijeni cron:
```yaml
# Svakih 10 minuta
- cron: '*/10 * * * *'

# Svakih 15 minuta
- cron: '*/15 * * * *'
```

### Prati više pretraga
Dupliciraj workflow ili dodaj više URL-ova u skriptu.

## Alternativna rješenja (ako ne želiš custom kod)

### Distill.io (Browser Extension)
- **Besplatno**: Lokalni monitor (browser mora biti otvoren), interval od 5 sekundi
- **Cloud**: Min. 6h interval na besplatnom planu, 5 min na plaćenom ($15/mj)
- **Problem**: OLX.ba je SPA — cloud monitoring možda neće raditi bez JS renderinga

### Visualping.io
- Slična ograničenja kao Distill.io
- Besplatni plan ima ograničen broj provjera

### changedetection.io (Self-hosted)
- Odlično rješenje ako imaš server
- Podržava Playwright za SPA stranice
- Potpuno besplatno (open source), ali treba hosting

**Moja preporuka**: GitHub Actions rješenje iz ovog repoa je najbolji balans besplatnog hostinga, brzine notifikacija, i jednostavnosti.

---

## Licenca

MIT — koristi kako hoćeš.
