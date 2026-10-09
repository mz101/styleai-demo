# OutfitSnap - Gen-4 Outfit Mapper

Eine KI-gestützte Fashion-Anwendung, die es Benutzern ermöglicht, Outfits zu erstellen, indem sie Bilder von Personen, Oberteilen und Unterteilen kombiniert. Nutzt Replicate's Gen-4 AI-Modell zur Bildgenerierung.

> **Demo-Repository:** Dieser Code dient Demonstrationszwecken. Alle Zugangsdaten werden über Umgebungsvariablen gesetzt (siehe `env.example`) – im Repository sind keine Schlüssel oder Passwörter enthalten.

## Features

- **3-Schritt Upload-Prozess**: Person → Oberteil → Unterteil
- **AI-Outfit-Generierung**: Erstellt 3 Varianten mit verschiedenen Seeds
- **Vorgefertigte Avatare**: 12 weibliche + 12 männliche Personen
- **Online-Produktsuche**: Amazon PA-API Integration
- **Video-Generierung**: Erstellt Videos aus generierten Outfits
- **Responsive Design**: Modern iOS-inspiriertes Interface

## Technologie-Stack

- **Backend**: Flask (Python)
- **AI**: Replicate Gen-4 & Gen-4-Turbo
- **Frontend**: Vanilla JavaScript, CSS
- **APIs**: Amazon Product Advertising API
- **Deployment**: Railway

## Setup für lokale Entwicklung

1. **Repository klonen**:
```bash
git clone <repository-url>
cd app-paw
```

2. **Virtuelle Umgebung erstellen**:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows
```

3. **Dependencies installieren**:
```bash
pip install -r requirements.txt
```

4. **Umgebungsvariablen konfigurieren**:
```bash
cp env.example .env
# Bearbeiten Sie .env mit Ihren API-Schlüsseln
```

5. **Anwendung starten**:
```bash
python app.py
```

## Deployment auf Railway

### Voraussetzungen
- Railway Account
- Git Repository
- API-Schlüssel für Replicate und Amazon

### Deployment-Schritte

1. **Railway CLI installieren**:
```bash
npm install -g @railway/cli
```

2. **Bei Railway anmelden**:
```bash
railway login
```

3. **Neues Railway-Projekt erstellen**:
```bash
railway new
```

4. **Umgebungsvariablen setzen**:
```bash
railway variables set REPLICATE_API_TOKEN=your_token_here
railway variables set AMAZON_ACCESS_KEY=your_access_key_here
railway variables set AMAZON_SECRET_KEY=your_secret_key_here
railway variables set AMAZON_PARTNER_TAG=your_partner_tag_here
railway variables set FLASK_ENV=production
railway variables set SECRET_KEY=<langer_zufallswert>
railway variables set AUTH_PASSWORD=<sicheres_passwort>
```

5. **Code deployen**:
```bash
git add .
git commit -m "Initial deployment"
railway up
```

## Erforderliche API-Schlüssel

### Replicate API Token
1. Gehen Sie zu [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
2. Erstellen Sie einen neuen Token
3. Setzen Sie `REPLICATE_API_TOKEN` in den Umgebungsvariablen

### Amazon Product Advertising API
1. Gehen Sie zu [webservices.amazon.com/paapi5](https://webservices.amazon.com/paapi5/documentation/)
2. Registrieren Sie sich für die PA-API
3. Erhalten Sie Access Key, Secret Key und Partner Tag
4. Setzen Sie die entsprechenden Umgebungsvariablen

## Projektstruktur

```
app-paw/
├── app.py                 # Flask-Hauptanwendung
├── requirements.txt       # Python-Dependencies
├── Procfile              # Railway-Startbefehl
├── railway.json          # Railway-Konfiguration
├── templates/            # HTML-Templates
│   ├── index.html        # Hauptseite
│   └── result.html       # Ergebnisseite
├── static/               # Statische Dateien
│   ├── styles.css        # Haupt-Styling
│   ├── search.js         # Frontend-Logik
│   ├── persons/          # Avatar-Bilder
│   └── uploads/          # Benutzer-Uploads
└── README.md             # Diese Datei
```

## Sicherheitshinweise

- Alle API-Schlüssel werden über Umgebungsvariablen verwaltet
- Keine sensiblen Daten im Quellcode
- CORS-sichere Amazon-API-Integration über Server-Proxy

## Single Sign-On (SSO) – Service A → Service B

- **Ziel**: Nutzer, die auf Service A eingeloggt sind, werden auf Service B ohne erneute Passworteingabe angemeldet.
- **Endpoint**: `GET /sso-login?sso=<token>&next=<path>`
- **Token**: base64url(`username|exp|signature`)
  - `signature = hex(HMAC_SHA256(key=SSO_SHARED_SECRET, data="username|exp"))`
  - `exp`: Unix-Timestamp (Sekunden, UTC), kurze TTL empfohlen (≤120s)
- **Validierung**:
  - base64url-decoden, `|`-splitten, HMAC in konstanter Zeit prüfen, `now <= exp` prüfen
  - bei Erfolg: signiertes Cookie `auth_session` setzen; Redirect auf `next` (nur wenn `next.startswith('/')`), sonst `/`
  - bei Fehler: Redirect zu `SSO_FALLBACK_URL` oder `/login`
- **Auth-Cookie**: `auth_session`
  - Wert: base64url(`username|issued_at|max_age|sig`)
  - `sig = hex(HMAC_SHA256(SESSION_SECRET, f"{username}|{issued_at}|{max_age}"))`
  - Flags: `HttpOnly`, `SameSite=Lax`, `Secure` (in Prod), `Max-Age=7d`
- **Umgebungsvariablen**:
  - `SSO_SHARED_SECRET` (Pflicht)
  - `SESSION_SECRET` (Pflicht)
  - `COOKIE_SECURE` (Prod=1)
  - `SSO_FALLBACK_URL` (optional; sonst `/login`)

## Support

Bei Problemen oder Fragen erstellen Sie bitte ein Issue im Repository.
