import os, uuid, time, requests
import base64, hmac
from typing import Optional
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, session, send_file, after_this_request
)
from werkzeug.utils import secure_filename
from functools import wraps
import replicate
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, DateTime, Text
import shutil
import hashlib
import secrets
import zipfile

from pathlib import Path
from urllib.parse import urlparse, urlunparse
import threading
from boto3.session import Session as Boto3Session
from botocore.config import Config as BotoConfig
BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

# Persistente Speicher-Konfiguration
PERSISTENT_DIR = Path("/app/persistent") if os.path.exists("/app/persistent") else BASE_DIR / "persistent"
UPLOAD_FOLDER = PERSISTENT_DIR / "uploads" / "images"
GENERATED_FOLDER = PERSISTENT_DIR / "uploads" / "generated" 
VIDEO_FOLDER = PERSISTENT_DIR / "uploads" / "videos"
PERSONS_FOLDER = PERSISTENT_DIR / "avatars"
EXPORTS_FOLDER = PERSISTENT_DIR / "exports"
LEGACY_UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"  # Für Kompatibilität

# Erstelle persistente Ordner
for folder in [UPLOAD_FOLDER, GENERATED_FOLDER, VIDEO_FOLDER, PERSONS_FOLDER, EXPORTS_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)

# Migriere bestehende Avatare falls nötig
legacy_persons = BASE_DIR / "static" / "persons"
if legacy_persons.exists() and not (PERSONS_FOLDER / "female").exists():
    print("Migriere Avatar-Bilder zu persistentem Speicher...")
    shutil.copytree(legacy_persons, PERSONS_FOLDER, dirs_exist_ok=True)

replicate_client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))

# DigitalOcean Spaces Konfiguration
SPACES_REGION = os.getenv("SPACES_REGION", "fra1")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_KEY = os.getenv("SPACES_KEY") or os.getenv("DO_SPACES_KEY")
SPACES_SECRET = os.getenv("SPACES_SECRET") or os.getenv("DO_SPACES_SECRET")
SPACES_CDN_DOMAIN = (os.getenv("SPACES_CDN_DOMAIN") or "").strip().rstrip("/")
SPACES_PUBLIC = str(os.getenv("SPACES_PUBLIC", "1")).lower() in ("1", "true", "yes")
try:
    SPACES_MAX_UPLOAD_MB = int(os.getenv("SPACES_MAX_UPLOAD_MB", "8"))
except Exception:
    SPACES_MAX_UPLOAD_MB = 8

_s3_client = None
if SPACES_BUCKET and SPACES_KEY and SPACES_SECRET and SPACES_REGION:
    try:
        _s3_client = Boto3Session().client(
            "s3",
            region_name=SPACES_REGION,
            endpoint_url=f"https://{SPACES_REGION}.digitaloceanspaces.com",
            aws_access_key_id=SPACES_KEY,
            aws_secret_access_key=SPACES_SECRET,
            config=BotoConfig(s3={"addressing_style": "virtual"})
        )
        print("✅ DigitalOcean Spaces konfiguriert")
    except Exception as e:
        print(f"⚠️ Konnte Spaces-Client nicht initialisieren: {e}")
        _s3_client = None

def _spaces_public_url(key: str) -> str:
    key = str(key).lstrip("/")
    if SPACES_CDN_DOMAIN:
        return f"{SPACES_CDN_DOMAIN}/{key}"
    if SPACES_BUCKET and SPACES_REGION:
        return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{key}"
    return None

def _is_spaces_url(u: str) -> bool:
    """Prüft, ob die URL auf DigitalOcean Spaces/CDN zeigt (DO-only Policy für Feeds)."""
    if not u:
        return False
    try:
        us = str(u)
        if SPACES_CDN_DOMAIN and us.startswith(SPACES_CDN_DOMAIN):
            return True
        if SPACES_BUCKET and SPACES_REGION and us.startswith(f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/"):
            return True
    except Exception:
        return False
    return False

def _spaces_upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    if not _s3_client:
        raise RuntimeError("Spaces ist nicht konfiguriert (fehlende Credentials)")
    key = str(key).lstrip("/")
    extra_args = {
        "ContentType": content_type or "application/octet-stream",
        "ACL": "public-read" if SPACES_PUBLIC else "private",
    }
    _s3_client.put_object(Bucket=SPACES_BUCKET, Key=key, Body=data, **extra_args)
    return _spaces_public_url(key)

# Version und Build-Info
APP_VERSION = "1.4.0"  # Vollständige Datenpersistenz und Backup-Integration
BUILD_TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
BUILD_INFO = f"v{APP_VERSION} ({BUILD_TIMESTAMP})"

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp"}

app = Flask(__name__, static_url_path="/static")
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
# Ohne SECRET_KEY wird pro Start ein zufälliger Schlüssel erzeugt (Sessions überleben dann keinen Neustart)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
# Cookie-Sicherheit (in Produktion aktivieren)
is_production = os.getenv('FLASK_DEBUG', 'False').lower() != 'true'
app.config['SESSION_COOKIE_SECURE'] = True if is_production else False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

# ---------- Health Endpoint ---------- #
@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "version": APP_VERSION}), 200

# ---------- SSO / eigene Auth-Cookie-Helfer ---------- #
AUTH_COOKIE_NAME = "auth_session"

def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} not configured")
    return value

def _b64url_decode(data: str) -> str:
    try:
        # fehlendes Padding tolerant ergänzen
        padding = '=' * (-len(data) % 4)
        raw = base64.urlsafe_b64decode((data + padding).encode("utf-8"))
        return raw.decode("utf-8")
    except Exception:
        raise

def _b64url_encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8").rstrip('=')

def _hmac_hex(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_sso_token(token: str) -> Optional[str]:
    """Validiert das SSO-Token: base64url(username|exp|signature).
    Gibt den username zurück oder None bei Ungültigkeit.
    """
    if not token:
        return None
    try:
        decoded = _b64url_decode(token)
        parts = decoded.split("|")
        if len(parts) != 3:
            return None
        username, exp_str, signature = parts
        # Signatur prüfen
        expected = _hmac_hex(_get_required_env("SSO_SHARED_SECRET"), f"{username}|{exp_str}")
        if not hmac.compare_digest(signature, expected):
            return None
        # Ablauf prüfen (Unix-Timestamp in Sekunden, UTC)
        if time.time() > int(exp_str):
            return None
        return username
    except Exception:
        return None

def create_auth_cookie_value(username: str, max_age: int = 7*24*60*60) -> str:
    issued_at = int(time.time())
    payload = f"{username}|{issued_at}|{max_age}"
    sig = _hmac_hex(_get_required_env("SESSION_SECRET"), payload)
    raw = f"{payload}|{sig}"
    # base64url, ohne Padding
    return _b64url_encode(raw)

def verify_auth_cookie(token: Optional[str]) -> Optional[str]:
    """Validiert den Wert des auth_session-Cookies.
    Gibt den username zurück oder None.
    """
    if not token:
        return None
    try:
        decoded = _b64url_decode(token)
        parts = decoded.split("|")
        if len(parts) != 4:
            return None
        username, issued_at_str, max_age_str, sig = parts
        payload = f"{username}|{issued_at_str}|{max_age_str}"
        expected = _hmac_hex(_get_required_env("SESSION_SECRET"), payload)
        if not hmac.compare_digest(sig, expected):
            return None
        # Ablauf prüfen: issued_at + max_age >= now
        issued_at = int(issued_at_str)
        max_age = int(max_age_str)
        if time.time() > issued_at + max_age:
            return None
        return username
    except Exception:
        return None

@app.route("/sso-login", methods=["GET"])
def sso_login():
    sso_token = request.args.get("sso")
    next_path = request.args.get("next", "/") or "/"

    username = verify_sso_token(sso_token)
    if not username:
        fb = os.getenv("SSO_FALLBACK_URL") or "/login"
        return redirect(fb, code=303)

    # Auth-Cookie ausstellen
    cookie_value = create_auth_cookie_value(username)
    # Nur lokale Pfade zulassen ("//host" bzw. "/\\host" wären Weiterleitungen auf fremde Domains)
    is_local = isinstance(next_path, str) and next_path.startswith("/") and not next_path.startswith(("//", "/\\"))
    target = next_path if is_local else "/"

    resp = redirect(target, code=303)
    secure_flag = str(os.getenv("COOKIE_SECURE", "0")).lower() in ("1", "true", "yes")
    resp.set_cookie(
        AUTH_COOKIE_NAME,
        cookie_value,
        max_age=7*24*60*60,
        httponly=True,
        samesite="Lax",
        secure=secure_flag,
        path="/",
    )
    return resp

# Database Konfiguration
database_url = None
# Erzwinge SQLite-Only
persistent_sqlite = "/app/persistent/outfitsnap.db"
if os.path.exists("/app/persistent"):
    database_url = f"sqlite:///{persistent_sqlite}"
else:
    database_url = "sqlite:///outfitsnap.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
print(f"🔗 Database URI: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
# Einfache In‑Memory TTL‑Cache Implementierung
class SimpleTTLCache:
    def __init__(self, max_entries: int = 500, default_ttl_seconds: int = 900):
        self._store = {}
        self._lock = threading.Lock()
        self._max = max_entries
        self._ttl = default_ttl_seconds

    def _now(self):
        return time.time()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if expires_at < self._now():
                # abgelaufen entfernen
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value, ttl_seconds: int = None):
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        with self._lock:
            # einfache Größenbegrenzung mit zufälligem Prune (FIFO-ish)
            if len(self._store) >= self._max:
                # entferne ~10% älteste/erste Einträge (vereinfachter Ansatz)
                for i, k in enumerate(list(self._store.keys())):
                    self._store.pop(k, None)
                    if i >= max(1, self._max // 10):
                        break
            self._store[key] = (value, self._now() + max(1, ttl))

    def clear(self):
        with self._lock:
            self._store.clear()

search_cache = SimpleTTLCache(max_entries=500, default_ttl_seconds=900)  # 15 Minuten


# Sichere Standard-Header setzen
@app.after_request
def set_security_headers(response):
    try:
        # Erzwinge HTTPS (HSTS), nur wenn hinter TLS
        if is_production:
            response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
        # Verhindere MIME-Sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Content Security Policy – explizit Medien/Images/Skripte erlauben
        csp_parts = [
            "upgrade-insecure-requests",
            "default-src 'self' https: data:",
            "script-src 'self' 'unsafe-inline' https:",
            "style-src 'self' 'unsafe-inline' https:",
            "img-src 'self' https: data: blob:",
            "media-src 'self' https: data: blob:",
            "connect-src 'self' https:",
            "font-src 'self' https: data:",
        ]
        csp = "; ".join(csp_parts)
        response.headers['Content-Security-Policy'] = csp
        # Weitere sinnvolle Defaults
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    except Exception:
        pass
    return response

# Reverse-Proxy Header (Railway) respektieren, damit url_for extern HTTPS nutzt
try:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
except Exception:
    pass

# ---------- Database Models ---------- #
class OutfitSession(db.Model):
    __tablename__ = 'outfit_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Eingabe-Bilder (lokale Pfade)
    person_image_path = Column(String(500))
    top_image_path = Column(String(500))
    bottom_image_path = Column(String(500))
    # Amazon-Produkt-Links (optional)
    top_product_url = Column(String(1000))
    bottom_product_url = Column(String(1000))
    
    # Generierte Inhalte
    generated_image_path = Column(String(500))  # Lokaler Pfad
    generated_image_url = Column(String(1000))  # Replicate URL (Backup)
    generated_video_path = Column(String(500))  # Lokaler Pfad
    generated_video_url = Column(String(1000))  # Replicate Video-URL (Backup)
    
    # Karl-Analyse
    karl_analysis = Column(Text)
    
    # Session-Info
    user_session = Column(String(100))  # Flask session ID
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'created_at': self.created_at.isoformat(),
            'person_image_path': self.person_image_path,
            'top_image_path': self.top_image_path,
            'bottom_image_path': self.bottom_image_path,
            'top_product_url': self.top_product_url,
            'bottom_product_url': self.bottom_product_url,
            'generated_image_path': self.generated_image_path,
            'generated_image_url': self.generated_image_url,
            'generated_video_path': self.generated_video_path,
            'generated_video_url': self.generated_video_url,
            'karl_analysis': self.karl_analysis
        }

class UserPreference(db.Model):
    __tablename__ = 'user_preferences'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100))
    preferred_styles = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class SelectedVideo(db.Model):
    __tablename__ = 'selected_videos'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Video-Referenz
    outfit_session_id = Column(String(36))  # Referenz zu OutfitSession
    video_url = Column(String(1000))  # Video-URL (lokal oder remote)
    video_path = Column(String(500))  # Lokaler Pfad falls vorhanden
    is_active = Column(String(10), default='true')  # 'true' oder 'false' als String
    
    # Metadaten
    title = Column(String(200))  # Optional: Titel für Admin-Interface
    notes = Column(Text)  # Optional: Notizen
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'created_at': self.created_at.isoformat(),
            'outfit_session_id': str(self.outfit_session_id) if self.outfit_session_id else None,
            'video_url': self.video_url,
            'video_path': self.video_path,
            'is_active': self.is_active,
            'title': self.title,
            'notes': self.notes
        }

class AppSetting(db.Model):
    __tablename__ = 'app_settings'
    key = Column(String(100), primary_key=True)
    value = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_app_setting(key, default=None):
    try:
        setting = AppSetting.query.filter_by(key=key).first()
        return setting.value if setting and setting.value is not None else default
    except Exception:
        return default

def set_app_setting(key, value):
    setting = AppSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()
    return setting.value

# ---------- Produktbild-/Link-Normalisierung & Matching ---------- #
def _normalize_product_url(u: str):
    """Normiert Produkt-URLs grob: trimmt Whitespace und stellt Schema sicher."""
    if not u:
        return None
    u = u.strip()
    if not u:
        return None
    if not (u.startswith('http://') or u.startswith('https://')):
        u = 'https://' + u
    return u

def _canonicalize_url(u: str) -> str:
    """Kanonisiert eine URL für Matching-Zwecke: https-Schema, kleingeschriebener Host, ohne Query/Fragment."""
    try:
        p = urlparse(u)
        scheme = 'https'
        netloc = (p.netloc or '').lower()
        path = p.path or ''
        return urlunparse((scheme, netloc, path, '', '', ''))
    except Exception:
        return u

def _compute_image_key(path_or_url: str) -> str:
    """Bild-Matching-Schlüssel:
    - Lokale Datei: sha256-Inhaltshash → "hash:<hex>"
    - Remote-URL: kanonisierte URL → "url:<canon>"
    - Fallback: getrimmter String → "str:<value>"
    """
    if not path_or_url:
        return None
    value = str(path_or_url).strip()
    if not value:
        return None

    # URL-basiert
    if value.startswith('http://') or value.startswith('https://'):
        canon = _canonicalize_url(value)
        return f"url:{canon}"

    # Versuche lokale Datei zu hashen
    try:
        p = Path(value)
        if p.exists() and p.is_file():
            h = hashlib.sha256()
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(chunk)
            return f"hash:{h.hexdigest()}"
    except Exception:
        pass

    # Fallback: String-basierter Schlüssel
    return f"str:{value}"

# Auth-Konfiguration
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")  # kein Standard-Passwort: ohne Variable ist der Login deaktiviert

# Auth-Decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1) Bestehende Session-Flag
        if session.get('authenticated'):
            return f(*args, **kwargs)

        # 2) Neues auth_session-Cookie prüfen
        cookie_val = request.cookies.get(AUTH_COOKIE_NAME)
        username = verify_auth_cookie(cookie_val)
        if username:
            # optional: username in session notieren (ohne Flask-Server-Session zu erzwingen)
            session['authenticated'] = True
            session['username'] = username
            return f(*args, **kwargs)

        # 3) Fallback: Login
        return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------- Hilfsfunktionen ---------- #
def _save_file(fieldname):
    """Speichert eine einzelne Datei direkt in Spaces und gibt die öffentliche URL zurück."""
    f = request.files[fieldname]
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Invalid file format for {fieldname}")

    # Größenlimit prüfen (Standard 8MB)
    f.stream.seek(0, os.SEEK_END)
    size_bytes = f.stream.tell()
    f.stream.seek(0)
    if size_bytes > SPACES_MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File too large (>{SPACES_MAX_UPLOAD_MB}MB)")

    # Eindeutiger Dateiname verhindert Kollisionen & Caching
    filename = secure_filename(f"{uuid.uuid4().hex}{ext}")
    key = f"uploads/images/{filename}"

    # Content-Type ableiten
    content_type = f.mimetype or "application/octet-stream"
    data = f.read()
    url = _spaces_upload_bytes(data, key, content_type=content_type)
    return url

def _get_url_or_upload(fieldname):
    """
    Prüft ob eine URL übergeben wurde (person_url, top_url, bottom_url).
    Falls ja, wird diese zurückgegeben.
    Falls nein, wird die hochgeladene Datei gespeichert und deren URL zurückgegeben.
    """
    url_fieldname = f"{fieldname}_url"

    # Prüfe ob eine URL übergeben wurde
    if url_fieldname in request.form and request.form[url_fieldname].strip():
        provided_url = request.form[url_fieldname].strip()

        # Bei vorgefertigten Personen-Bildern: Relativen Pfad zu absoluter URL konvertieren
        if provided_url.startswith('/static/persons/'):
            return url_for("static", filename=provided_url[8:], _external=True)  # Entferne '/static/' Prefix

        # Bei externen URLs direkt zurückgeben
        return provided_url

    # Falls keine URL, dann normale Datei-Upload-Verarbeitung (jetzt: Upload zu Spaces)
    if fieldname not in request.files:
        raise ValueError(f"Neither file nor URL found for {fieldname}")

    return _save_file(fieldname)

def _run_gen4(person_url, top_url, bottom_url, seed=None):
    """A call to Gen-4 and returns the image URL."""
    input_payload = {
        "prompt":      "A realistic photo of @person wearing @top and @bottom",
        "resolution":  "1080p",                   # User-Vorgabe
        "aspect_ratio": "1:1",
        "reference_tags":   ["person", "top", "bottom"],
        "reference_images": [person_url, top_url, bottom_url],
    }
    if seed is not None:
        input_payload["seed"] = seed

    # Synchrone Ausführung – Rückgabe ist direkt der Bild-URL
    output_url = replicate.run("runwayml/gen4-image", input=input_payload)
    return output_url                # URL (string)

def _ensure_persons_folder():
    """Erstellt die Ordnerstruktur für vorgefertigte Personen-Bilder"""
    female_folder = PERSONS_FOLDER / "female"
    male_folder = PERSONS_FOLDER / "male"

    female_folder.mkdir(parents=True, exist_ok=True)
    male_folder.mkdir(parents=True, exist_ok=True)

    return female_folder, male_folder

# ---------- Auth Routes ---------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if (AUTH_PASSWORD and username == AUTH_USERNAME
                and hmac.compare_digest((password or "").encode("utf-8"), AUTH_PASSWORD.encode("utf-8"))):
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid login credentials", version=BUILD_INFO)
    
    return render_template('login.html', version=BUILD_INFO)

@app.route("/logout")
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# ---------- Admin Backend ---------- #
@app.route("/admin")
@require_auth
def admin_dashboard():
    """Admin dashboard with outfit overview and statistics."""
    try:
        # Alle Outfit-Sessions abrufen (neueste zuerst)
        # Robustere Sortierung: Falls created_at NULL ist (ältere Datensätze), trotzdem konsistent sortieren
        from sqlalchemy import func
        sessions = (
            OutfitSession.query
            .order_by(func.coalesce(OutfitSession.created_at, func.now()).desc(), OutfitSession.id.desc())
            .limit(400)
            .all()
        )
        
        # Statistiken berechnen
        total_sessions = OutfitSession.query.count()
        sessions_today = OutfitSession.query.filter(
            OutfitSession.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        sessions_with_karl = OutfitSession.query.filter(
            OutfitSession.karl_analysis.isnot(None)
        ).count()
        
        # Unique User Sessions
        unique_users = db.session.query(OutfitSession.user_session).distinct().count()
        
        stats = {
            'total_sessions': total_sessions,
            'sessions_today': sessions_today,
            'sessions_with_karl': sessions_with_karl,
            'unique_users': unique_users,
            'karl_usage_rate': round((sessions_with_karl / total_sessions * 100) if total_sessions > 0 else 0, 1)
        }
        
        return render_template("admin.html", 
                             sessions=sessions, 
                             stats=stats, 
                             version=BUILD_INFO)
                             
    except Exception as e:
        # Fallback wenn Database nicht verfügbar
        return render_template("admin.html", 
                             sessions=[], 
                             stats={'total_sessions': 0, 'sessions_today': 0, 'sessions_with_karl': 0, 'unique_users': 0, 'karl_usage_rate': 0},
                             error=f"Database not available: {e}",
                             version=BUILD_INFO)

@app.route("/admin/session/<session_id>")
@require_auth
def admin_session_detail(session_id):
    """Detailansicht einer einzelnen Outfit-Session."""
    try:
        # IDs sind Strings (UUID als Text)
        outfit_session = OutfitSession.query.filter_by(id=session_id).first()
        if not outfit_session:
            return "Session not found", 404
            
        return render_template("admin_session.html", 
                             session=outfit_session, 
                             version=BUILD_INFO)
    except Exception as e:
        return f"Error loading session: {e}", 500

@app.route("/admin/session/<session_id>/delete", methods=["POST"])
@require_auth
def admin_delete_session(session_id):
    """Löscht eine Outfit-Session inkl. verknüpfter Einträge (SelectedVideo)."""
    try:
        session_obj = OutfitSession.query.filter_by(id=session_id).first()
        if not session_obj:
            return redirect(url_for('admin_dashboard'))

        # Verknüpfte Videos bereinigen
        SelectedVideo.query.filter_by(outfit_session_id=session_id).delete(synchronize_session=False)

        db.session.delete(session_obj)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        db.session.rollback()
        return f"Error deleting session: {e}", 500

@app.route("/admin/session/<session_id>/update-products", methods=["POST"])
@require_auth
def admin_update_products(session_id):
    """Speichert manuell nachgepflegte Produktlinks."""
    try:
        # IDs sind Strings (UUID als Text)
        outfit_session = OutfitSession.query.filter_by(id=session_id).first()
        if not outfit_session:
            return "Session not found", 404

        top_url = request.form.get('top_product_url') or None
        bottom_url = request.form.get('bottom_product_url') or None

        # Einfache Normalisierung: Schema ergänzen, Whitespace trimmen
        def _normalize(u: str):
            if not u:
                return None
            u = u.strip()
            if not u:
                return None
            if not (u.startswith('http://') or u.startswith('https://')):
                u = 'https://' + u
            return u

        top_url = _normalize(top_url)
        bottom_url = _normalize(bottom_url)

        outfit_session.top_product_url = top_url
        outfit_session.bottom_product_url = bottom_url
        db.session.commit()

        return redirect(url_for('admin_session_detail', session_id=session_id))
    except Exception as e:
        return f"Error updating products: {e}", 500

@app.route("/admin/api/stats")
@require_auth
def admin_api_stats():
    """API-Endpoint für Live-Statistiken (JSON)."""
    try:
        from datetime import timedelta
        
        # Erweiterte Statistiken
        total_sessions = OutfitSession.query.count()
        sessions_today = OutfitSession.query.filter(
            OutfitSession.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        # Sessions der letzten 7 Tage
        last_week = datetime.utcnow() - timedelta(days=7)
        sessions_week = OutfitSession.query.filter(OutfitSession.created_at >= last_week).count()
        
        # Karl-Nutzung
        sessions_with_karl = OutfitSession.query.filter(OutfitSession.karl_analysis.isnot(None)).count()
        
        # Unique Users
        unique_users = db.session.query(OutfitSession.user_session).distinct().count()
        
        return jsonify({
            'total_sessions': total_sessions,
            'sessions_today': sessions_today,
            'sessions_week': sessions_week,
            'sessions_with_karl': sessions_with_karl,
            'unique_users': unique_users,
            'karl_usage_rate': round((sessions_with_karl / total_sessions * 100) if total_sessions > 0 else 0, 1),
            'avg_sessions_per_user': round(total_sessions / unique_users if unique_users > 0 else 0, 1),
            'last_updated': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/admin/tools/backfill-product-links")
@require_auth
def admin_backfill_product_links():
    """Fullt fehlende Produkt-Links durch Bild-Matching auf.
    Regeln:
    - Nur Top/Bottom matchen; Person ignorieren
    - Matching-Schlussel: lokale Datei  sha256, Remote-URL  kanonisierte URL
    - Konflikt: meistgenutzter Link, bei Gleichstand jngster Datensatz
    - dry_run (default=1): nur Vorschau
    """
    try:
        dry_run = request.args.get('dry_run', '1') not in ('0', 'false', 'no')
        limit = int(request.args.get('limit', 2000))

        # 1) Alle Sessions einlesen (bis Limit)
        from sqlalchemy import desc
        sessions = (
            OutfitSession.query
            .order_by(desc(OutfitSession.created_at), desc(OutfitSession.id))
            .limit(limit)
            .all()
        )

        # 2) Index: image_key -> bekannte Produkt-Links (Counter + latest)
        from collections import defaultdict, Counter
        top_map = defaultdict(lambda: { 'counter': Counter(), 'latest': {} })
        bottom_map = defaultdict(lambda: { 'counter': Counter(), 'latest': {} })

        for s in sessions:
            # Top
            k_top = _compute_image_key(s.top_image_path)
            if k_top and s.top_product_url:
                norm = _normalize_product_url(s.top_product_url)
                if norm:
                    top_map[k_top]['counter'][norm] += 1
                    prev = top_map[k_top]['latest'].get(norm)
                    if (not prev) or ((s.created_at or datetime.min) > prev['created_at']):
                        top_map[k_top]['latest'][norm] = { 'created_at': s.created_at or datetime.min }
            # Bottom
            k_bottom = _compute_image_key(s.bottom_image_path)
            if k_bottom and s.bottom_product_url:
                norm = _normalize_product_url(s.bottom_product_url)
                if norm:
                    bottom_map[k_bottom]['counter'][norm] += 1
                    prev = bottom_map[k_bottom]['latest'].get(norm)
                    if (not prev) or ((s.created_at or datetime.min) > prev['created_at']):
                        bottom_map[k_bottom]['latest'][norm] = { 'created_at': s.created_at or datetime.min }

        # 3) Kandidaten mit fehlenden Links bestimmen und bestes Mapping auswhlen
        updates = []
        for s in sessions:
            # Top fehlend
            if not s.top_product_url:
                k_top = _compute_image_key(s.top_image_path)
                if k_top and top_map[k_top]['counter']:
                    cnt = top_map[k_top]['counter']
                    max_count = max(cnt.values())
                    # Kandidaten mit max Count
                    best_candidates = [u for u, c in cnt.items() if c == max_count]
                    if len(best_candidates) == 1:
                        best_top = best_candidates[0]
                    else:
                        # Tie-break: jngster
                        latest_map = top_map[k_top]['latest']
                        best_top = max(best_candidates, key=lambda u: latest_map.get(u, {'created_at': datetime.min})['created_at'])
                    if best_top:
                        updates.append({ 'id': str(s.id), 'field': 'top_product_url', 'value': best_top })
            # Bottom fehlend
            if not s.bottom_product_url:
                k_bottom = _compute_image_key(s.bottom_image_path)
                if k_bottom and bottom_map[k_bottom]['counter']:
                    cnt = bottom_map[k_bottom]['counter']
                    max_count = max(cnt.values())
                    best_candidates = [u for u, c in cnt.items() if c == max_count]
                    if len(best_candidates) == 1:
                        best_bottom = best_candidates[0]
                    else:
                        latest_map = bottom_map[k_bottom]['latest']
                        best_bottom = max(best_candidates, key=lambda u: latest_map.get(u, {'created_at': datetime.min})['created_at'])
                    if best_bottom:
                        updates.append({ 'id': str(s.id), 'field': 'bottom_product_url', 'value': best_bottom })

        applied = 0
        if not dry_run:
            # 4) Persistieren
            id_to_updates = defaultdict(dict)
            for u in updates:
                id_to_updates[u['id']][u['field']] = u['value']

            for s in sessions:
                u = id_to_updates.get(str(s.id))
                if not u:
                    continue
                if 'top_product_url' in u and not s.top_product_url:
                    s.top_product_url = u['top_product_url']
                if 'bottom_product_url' in u and not s.bottom_product_url:
                    s.bottom_product_url = u['bottom_product_url']
                if 'top_product_url' in u or 'bottom_product_url' in u:
                    applied += 1
            if applied:
                db.session.commit()

        return jsonify({
            'dry_run': dry_run,
            'scanned_sessions': len(sessions),
            'candidate_updates': len(updates),
            'applied_updates': applied if not dry_run else 0,
            'sample': updates[:50]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/admin/init-db")
@require_auth
def admin_init_db():
    """Manueller Database-Initialisierungsendpoint für Admin."""
    try:
        with app.app_context():
            db.create_all()
            return jsonify({
                'success': True,
                'message': 'Database-Tabellen erfolgreich erstellt!',
                'tables': [table.name for table in db.metadata.tables.values()]
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Database-Initialisierung fehlgeschlagen: {str(e)}'
        }), 500

@app.route("/admin/debug/<session_id>")
@require_auth
def admin_debug_session(session_id):
    """Debug-Endpoint für Session-Daten."""
    try:
        import uuid as uuid_module
        # IDs sind Strings (UUID als Text)
        outfit_session = OutfitSession.query.filter_by(id=session_id).first()
        if not outfit_session:
            return jsonify({'error': 'Session nicht gefunden'}), 404
            
        return jsonify({
            'session_data': outfit_session.to_dict(),
            'current_flask_session': dict(session),
            'debug_info': {
                'has_generated_image_url': bool(outfit_session.generated_image_url),
                'has_generated_image_path': bool(outfit_session.generated_image_path),
                'has_generated_video_url': bool(outfit_session.generated_video_url),
                'has_generated_video_path': bool(outfit_session.generated_video_path),
                'has_karl_analysis': bool(outfit_session.karl_analysis),
                'karl_analysis_length': len(outfit_session.karl_analysis) if outfit_session.karl_analysis else 0,
                'generated_image_url': outfit_session.generated_image_url,
                'generated_image_path': outfit_session.generated_image_path,
                'generated_video_url': outfit_session.generated_video_url,
                'generated_video_path': outfit_session.generated_video_path
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/admin/test-download")
@require_auth
def admin_test_download():
    """Test-Endpoint um Bild-Download zu testen."""
    test_url = "https://replicate.delivery/xezq/vY8Jgx39uP6FCZWPqBICEEfXx6fKrElojiqnLAZBXuCfKmhqA/tmp4a1ev65b.png"
    
    try:
        print(f"🧪 Teste Bild-Download: {test_url}")
        
        # Test 1: Bild herunterladen
        response = requests.get(test_url, timeout=30)
        print(f"📥 HTTP Status: {response.status_code}")
        print(f"📦 Content-Length: {len(response.content)} bytes")
        print(f"📄 Content-Type: {response.headers.get('content-type', 'unknown')}")
        
        if response.status_code == 200:
            # Test 2: Lokal speichern
            filename = f"test_download_{uuid.uuid4().hex}.jpg"
            file_path = GENERATED_FOLDER / filename
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Datei gespeichert: {file_path}")
            print(f"📁 Datei existiert: {file_path.exists()}")
            print(f"📏 Dateigröße: {file_path.stat().st_size} bytes")
            
            return jsonify({
                'success': True,
                'message': 'Bild erfolgreich heruntergeladen und gespeichert',
                'details': {
                    'url': test_url,
                    'local_path': str(file_path),
                    'file_size': len(response.content),
                    'content_type': response.headers.get('content-type'),
                    'file_exists': file_path.exists()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text[:200]}'
            }), 400
            
    except Exception as e:
        print(f"❌ Test-Download fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/admin/storage-status")
@require_auth
def admin_storage_status():
    """Überprüft den Status der dauerhaften Datenspeicherung."""
    try:
        # 1. Railway Volume Status
        volume_info = {
            'persistent_dir_exists': PERSISTENT_DIR.exists(),
            'persistent_dir_path': str(PERSISTENT_DIR),
            'upload_folder_exists': UPLOAD_FOLDER.exists(),
            'generated_folder_exists': GENERATED_FOLDER.exists(),
            'video_folder_exists': VIDEO_FOLDER.exists(),
            'persons_folder_exists': PERSONS_FOLDER.exists()
        }
        
        # 2. Ordner-Statistiken
        folder_stats = {}
        for folder_name, folder_path in [
            ('uploads/images', UPLOAD_FOLDER),
            ('uploads/generated', GENERATED_FOLDER), 
            ('uploads/videos', VIDEO_FOLDER),
            ('avatars', PERSONS_FOLDER)
        ]:
            if folder_path.exists():
                files = list(folder_path.glob('*'))
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                folder_stats[folder_name] = {
                    'file_count': len([f for f in files if f.is_file()]),
                    'total_size_mb': round(total_size / 1024 / 1024, 2),
                    'latest_file': max(files, key=lambda f: f.stat().st_mtime).name if files else None
                }
            else:
                folder_stats[folder_name] = {'file_count': 0, 'total_size_mb': 0, 'latest_file': None}
        
        # 3. Database Status
        db_info = {
            'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...' if len(app.config['SQLALCHEMY_DATABASE_URI']) > 50 else app.config['SQLALCHEMY_DATABASE_URI'],
            'is_postgresql': 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'],
            'is_sqlite': 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']
        }
        
        try:
            total_sessions = OutfitSession.query.count()
            sessions_with_images = OutfitSession.query.filter(
                (OutfitSession.generated_image_url.isnot(None)) | 
                (OutfitSession.generated_image_path.isnot(None))
            ).count()
            sessions_with_videos = OutfitSession.query.filter(
                (OutfitSession.generated_video_url.isnot(None)) | 
                (OutfitSession.generated_video_path.isnot(None))
            ).count()
            sessions_with_karl = OutfitSession.query.filter(OutfitSession.karl_analysis.isnot(None)).count()
            
            db_info.update({
                'connection_working': True,
                'total_sessions': total_sessions,
                'sessions_with_images': sessions_with_images,
                'sessions_with_videos': sessions_with_videos,
                'sessions_with_karl': sessions_with_karl,
                'image_persistence_rate': round((sessions_with_images / total_sessions * 100) if total_sessions > 0 else 0, 1),
                'video_persistence_rate': round((sessions_with_videos / total_sessions * 100) if total_sessions > 0 else 0, 1)
            })
        except Exception as db_error:
            db_info.update({
                'connection_working': False,
                'error': str(db_error)
            })
        
        # 4. Persistenz-Status
        persistence_status = {
            'volume_mounted': volume_info['persistent_dir_exists'],
            'all_folders_exist': all([
                volume_info['upload_folder_exists'],
                volume_info['generated_folder_exists'], 
                volume_info['video_folder_exists'],
                volume_info['persons_folder_exists']
            ]),
            'database_connected': db_info['connection_working'],
            'total_files': sum(stats['file_count'] for stats in folder_stats.values()),
            'total_storage_mb': sum(stats['total_size_mb'] for stats in folder_stats.values())
        }
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'app_version': BUILD_INFO,
            'volume_info': volume_info,
            'folder_stats': folder_stats,
            'database_info': db_info,
            'persistence_status': persistence_status,
            'recommendations': _get_storage_recommendations(persistence_status, folder_stats, db_info)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

def _get_storage_recommendations(persistence_status, folder_stats, db_info):
    """Generiert Empfehlungen basierend auf Storage-Status."""
    recommendations = []
    
    if not persistence_status['volume_mounted']:
        recommendations.append({
            'level': 'critical',
            'message': 'Railway Volume nicht gemountet - Daten gehen bei Restart verloren!'
        })
    
    if not persistence_status['database_connected']:
        recommendations.append({
            'level': 'critical', 
            'message': 'Database-Verbindung fehlgeschlagen - Metadaten werden nicht gespeichert!'
        })
    
    if persistence_status['total_storage_mb'] > 40000:  # 40GB von 50GB
        recommendations.append({
            'level': 'warning',
            'message': f"Speicher zu 80% voll ({persistence_status['total_storage_mb']:.1f}MB) - Volume-Upgrade empfohlen"
        })
    
    if db_info.get('image_persistence_rate', 0) < 90:
        recommendations.append({
            'level': 'warning',
            'message': f"Nur {db_info.get('image_persistence_rate', 0)}% der Bilder werden persistent gespeichert"
        })
    
    if db_info.get('video_persistence_rate', 0) < 90:
        recommendations.append({
            'level': 'warning',
            'message': f"Nur {db_info.get('video_persistence_rate', 0)}% der Videos werden persistent gespeichert"
        })
    
    if not recommendations:
        recommendations.append({
            'level': 'success',
            'message': '✅ Alle Daten werden vollständig persistent gespeichert!'
        })
    
    return recommendations

@app.route("/admin/storage")
@require_auth
def admin_storage():
    """Storage-Status-Dashboard."""
    return render_template("admin_storage.html", version=BUILD_INFO)

# === Einmaliger Storage-Export ===
_export_tokens = {}

def _zip_storage_tree(output_zip_path: Path) -> None:
    """Erstellt ein ZIP mit allen relevanten Storage-Verzeichnissen."""
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        def add_dir(dir_path: Path, arc_prefix: str):
            if not dir_path.exists():
                return
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    abs_path = Path(root) / f
                    rel_path = Path(arc_prefix) / abs_path.relative_to(dir_path)
                    zipf.write(abs_path, rel_path.as_posix())

        add_dir(UPLOAD_FOLDER, 'uploads/images')
        add_dir(GENERATED_FOLDER, 'uploads/generated')
        add_dir(VIDEO_FOLDER, 'uploads/videos')
        add_dir(PERSONS_FOLDER, 'avatars')

@app.route('/admin/storage-export/create', methods=['POST'])
@require_auth
def admin_storage_export_create():
    """Erstellt ein ZIP aller gespeicherten Dateien und gibt einen einmaligen Download-Link zurück."""
    try:
        EXPORTS_FOLDER.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        zip_name = f"storage_export_{timestamp}.zip"
        zip_path = EXPORTS_FOLDER / zip_name

        _zip_storage_tree(zip_path)

        token = secrets.token_urlsafe(24)
        _export_tokens[token] = {
            'zip_path': str(zip_path),
            'created_at': timestamp
        }

        return jsonify({
            'ok': True,
            'download_url': url_for('admin_storage_export_download', token=token, _external=True),
            'file_name': zip_name,
            'file_size_mb': round(zip_path.stat().st_size / (1024*1024), 2)
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/storage-export/download/<token>')
@require_auth
def admin_storage_export_download(token: str):
    """Einmaliger Download des zuvor erzeugten Exports. Token verfällt direkt nach Nutzung."""
    entry = _export_tokens.pop(token, None)
    if not entry:
        return "Ungültiger oder bereits verwendeter Download-Link", 404

    zip_path = Path(entry['zip_path'])
    if not zip_path.exists():
        return "Export-Datei nicht gefunden", 404

    @after_this_request
    def _cleanup(response):
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        return response

    return send_file(str(zip_path), as_attachment=True, download_name=zip_path.name, mimetype='application/zip')

# === SQLite-DB Download (nur wenn SQLite verwendet wird) ===
@app.route('/admin/sqlite-download')
@require_auth
def admin_sqlite_download():
    """Erlaubt den Download der lokalen SQLite-DB, falls SQLite aktiv ist.
    Sicherheitsaspekte:
    - Nur verfügbar, wenn die App aktuell SQLite nutzt.
    - Datei muss unter dem persistenten Verzeichnis liegen.
    - Download nur für authentifizierte Admins.
    """
    try:
        # Prüfen, ob SQLite aktiv ist
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if 'sqlite' not in uri:
            return "Diese Funktion ist nur bei SQLite verfügbar.", 400

        # Mögliche Speicherorte der DB extrahieren
        # Erwartete URIs: sqlite:////app/persistent/outfitsnap.db oder sqlite:///outfitsnap.db
        db_path_str = uri.split('sqlite:///')[-1]
        db_path = Path(db_path_str)

        # Falls relativer Pfad, relativ zu BASE_DIR auflösen
        if not db_path.is_absolute():
            # Bevorzugt persistenten Pfad
            candidate_persistent = PERSISTENT_DIR / db_path
            candidate_local = BASE_DIR / db_path
            if candidate_persistent.exists():
                db_path = candidate_persistent
            else:
                db_path = candidate_local

        if not db_path.exists() or not db_path.is_file():
            return "SQLite-Datei nicht gefunden.", 404

        # Zusatzcheck: Nur Dateien innerhalb des persistenten oder Projektverzeichnisses zulassen
        try:
            resolved = db_path.resolve()
            allowed_bases = [PERSISTENT_DIR.resolve(), BASE_DIR.resolve()]
            if not any(str(resolved).startswith(str(base)) for base in allowed_bases):
                return "Zugriff verweigert.", 403
        except Exception:
            return "Pfadvalidierung fehlgeschlagen.", 400

        return send_file(str(db_path), as_attachment=True, download_name=db_path.name, mimetype='application/octet-stream')
    except Exception as e:
        return f"Fehler beim SQLite-Download: {e}", 500

# === SQLite-Migration: Pfade in generated_image_path umschreiben ===
@app.route('/admin/migrate-image-paths', methods=['POST', 'GET'])
@require_auth
def admin_migrate_image_paths():
    """Schreibt Pfade in outfit_sessions.generated_image_path um.
    Von '/app/persistent/uploads/generated' →
        'https://style-ai.fra1.cdn.digitaloceanspaces.com/media/uploads/generated'

    Optionaler Dry-Run via ?dry=1 zeigt nur Anzahl der betroffenen Zeilen.
    """
    try:
        old_prefix = '/app/persistent/uploads/generated'
        new_prefix = 'https://style-ai.fra1.cdn.digitaloceanspaces.com/media/uploads/generated'

        dry = request.args.get('dry') in ('1', 'true', 'yes')

        # Anzahl betroffener Zeilen ermitteln
        count_sql = (
            "SELECT COUNT(*) AS cnt FROM outfit_sessions "
            "WHERE generated_image_path LIKE :prefix || '%'"
        )
        result = db.session.execute(db.text(count_sql), { 'prefix': old_prefix }).scalar() or 0

        if dry or request.method == 'GET':
            return jsonify({ 'ok': True, 'dry_run': True, 'affected': int(result), 'from': old_prefix, 'to': new_prefix })

        # Update ausführen
        update_sql = (
            "UPDATE outfit_sessions "
            "SET generated_image_path = REPLACE(generated_image_path, :old, :new) "
            "WHERE generated_image_path LIKE :prefix || '%'"
        )
        upd_res = db.session.execute(db.text(update_sql), { 'old': old_prefix, 'new': new_prefix, 'prefix': old_prefix })
        db.session.commit()

        return jsonify({ 'ok': True, 'updated_rows': upd_res.rowcount, 'from': old_prefix, 'to': new_prefix })
    except Exception as e:
        db.session.rollback()
        return jsonify({ 'ok': False, 'error': str(e) }), 500

# === SQLite-Migration: Pfade in generated_video_path umschreiben ===
@app.route('/admin/migrate-video-paths', methods=['POST', 'GET'])
@require_auth
def admin_migrate_video_paths():
    """Schreibt Pfade in outfit_sessions.generated_video_path um.
    Von '/app/persistent/' → 'https://style-ai.fra1.cdn.digitaloceanspaces.com/media/'

    Optionaler Dry-Run via ?dry=1 zeigt nur Anzahl der betroffenen Zeilen.
    """
    try:
        old_prefix = '/app/persistent/'
        new_prefix = 'https://style-ai.fra1.cdn.digitaloceanspaces.com/media/'

        dry = request.args.get('dry') in ('1', 'true', 'yes')

        # Anzahl betroffener Zeilen ermitteln
        count_sql = (
            "SELECT COUNT(*) AS cnt FROM outfit_sessions "
            "WHERE generated_video_path LIKE :prefix || '%'"
        )
        result = db.session.execute(db.text(count_sql), { 'prefix': old_prefix }).scalar() or 0

        if dry or request.method == 'GET':
            return jsonify({ 'ok': True, 'dry_run': True, 'affected': int(result), 'from': old_prefix, 'to': new_prefix })

        # Update ausführen
        update_sql = (
            "UPDATE outfit_sessions "
            "SET generated_video_path = REPLACE(generated_video_path, :old, :new) "
            "WHERE generated_video_path LIKE :prefix || '%'"
        )
        upd_res = db.session.execute(db.text(update_sql), { 'old': old_prefix, 'new': new_prefix, 'prefix': old_prefix })
        db.session.commit()

        return jsonify({ 'ok': True, 'updated_rows': upd_res.rowcount, 'from': old_prefix, 'to': new_prefix })
    except Exception as e:
        db.session.rollback()
        return jsonify({ 'ok': False, 'error': str(e) }), 500

@app.route("/admin/debug-sessions")
@require_auth
def admin_debug_sessions():
    """Debug-Endpoint für Session-Probleme."""
    try:
        # Database Status
        db_status = {
            'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...',
            'is_postgresql': 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'],
            'is_sqlite': 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']
        }
        
        # Versuche Database-Query
        try:
            total_sessions = OutfitSession.query.count()
            all_sessions = OutfitSession.query.order_by(OutfitSession.created_at.desc()).limit(10).all()
            
            sessions_data = []
            for s in all_sessions:
                sessions_data.append({
                    'id': str(s.id),
                    'created_at': s.created_at.isoformat(),
                    'person_image_path': s.person_image_path,
                    'top_image_path': s.top_image_path,
                    'bottom_image_path': s.bottom_image_path,
                    'generated_image_url': s.generated_image_url,
                    'generated_image_path': s.generated_image_path,
                    'karl_analysis': bool(s.karl_analysis)
                })
            
            db_status.update({
                'connection_working': True,
                'total_sessions': total_sessions,
                'recent_sessions': sessions_data
            })
            
        except Exception as db_error:
            db_status.update({
                'connection_working': False,
                'error': str(db_error)
            })
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'database': db_status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

## Entfernt: /admin/debug-postgres (nur SQLite wird unterstützt)

@app.route("/admin/debug-detailed")
@require_auth
def admin_debug_detailed():
    """Detaillierter Debug-Endpoint mit allen Informationen."""
    try:
        # Environment Variables
        env_vars = {
            'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT_SET',
            'PGHOST': os.getenv('PGHOST', 'NOT_SET'),
            'PGPORT': os.getenv('PGPORT', 'NOT_SET'),
            'PGUSER': os.getenv('PGUSER', 'NOT_SET'),
            'PGPASSWORD': 'SET' if os.getenv('PGPASSWORD') else 'NOT_SET',
            'PGDATABASE': os.getenv('PGDATABASE', 'NOT_SET')
        }
        
        # Database Status
        db_status = {
            'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...',
            'is_postgresql': 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'],
            'is_sqlite': 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']
        }
        
        # Versuche Database-Query
        try:
            total_sessions = OutfitSession.query.count()
            all_sessions = OutfitSession.query.order_by(OutfitSession.created_at.desc()).limit(5).all()
            
            sessions_data = []
            for s in all_sessions:
                sessions_data.append({
                    'id': str(s.id),
                    'created_at': s.created_at.isoformat(),
                    'person_image_path': s.person_image_path,
                    'top_image_path': s.top_image_path,
                    'bottom_image_path': s.bottom_image_path,
                    'generated_image_url': s.generated_image_url,
                    'generated_image_path': s.generated_image_path,
                    'generated_video_url': s.generated_video_url,
                    'generated_video_path': s.generated_video_path,
                    'karl_analysis': bool(s.karl_analysis),
                    'user_session': s.user_session
                })
            
            db_status.update({
                'connection_working': True,
                'total_sessions': total_sessions,
                'recent_sessions': sessions_data
            })
            
        except Exception as db_error:
            db_status.update({
                'connection_working': False,
                'error': str(db_error)
            })
        
        return jsonify({
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'environment_variables': env_vars,
            'database': db_status,
            'railway_info': {
                'environment': os.getenv('RAILWAY_ENVIRONMENT', 'unknown'),
                'project_name': os.getenv('RAILWAY_PROJECT_NAME', 'unknown'),
                'service_name': os.getenv('RAILWAY_SERVICE_NAME', 'unknown')
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route("/admin/test-video")
@require_auth
def admin_test_video():
    """Test-Endpoint um Video-Frontend zu testen."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video-Player Test</title>
        <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.5/dist/purify.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    </head>
    <body>
        <h1>Video-Player Test</h1>
        <button onclick="testVideo()">🎬 Test Video-Modal</button>
        
        <!-- Video Modal (kopiert aus result.html) -->
        <div id="videoModal" class="karl-modal">
          <div class="karl-modal-content">
            <div class="karl-modal-header">
              <span><center>Dein Outfit-Video</center></span>
              <button class="karl-close" onclick="closeVideoModal()">×</button>
            </div>
            <div class="karl-modal-body-wrapper">
              <div id="videoModalMediaContainer" style="padding:20px 20px 10px;display:flex;justify-content:center;"></div>
              <div class="karl-modal-body" id="videoModalBody"></div>
            </div>
          </div>
        </div>
        
        <style>
        .karl-modal { position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center; }
        .karl-modal-content { background-color: #fefefe; margin: auto; padding: 0; border: 1px solid #888; width: 90%; max-width: 600px; border-radius: 10px; max-height: 90vh; overflow-y: auto; }
        .karl-modal-header { padding: 15px 20px; background-color: #f1f1f1; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; border-radius: 10px 10px 0 0; }
        .karl-close { color: #aaa; float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .karl-modal-body { padding: 20px; }
        </style>
        
        <script>
        function showVideoModal(imageUrl = null, message) {
            const modal = document.getElementById('videoModal');
            const body = document.getElementById('videoModalBody');
            const mediaContainer = document.getElementById('videoModalMediaContainer');

            if (imageUrl) {
                mediaContainer.innerHTML = \`
                    <div style="width:100%;max-width:300px;overflow:hidden;border-radius:8px;display:flex;justify-content:center;margin-bottom:10px;">
                        <img src="\${imageUrl}" alt="Outfit Bild" style="width:100%;height:auto;object-fit:contain;display:block;"/>
                    </div>
                \`;
            } else if (!mediaContainer.innerHTML.includes('<video')) {
                mediaContainer.innerHTML = '';
            }

            if (message) {
                const parsed = DOMPurify.sanitize(marked.parse(message));
                body.innerHTML = parsed;
            }

            document.body.style.overflow = 'hidden';
            modal.style.display = 'flex';
        }
        
        function closeVideoModal() {
            document.getElementById('videoModal').style.display = 'none';
            document.body.style.overflow = '';
        }
        
        function testVideo() {
            const testVideoUrl = "https://replicate.delivery/xezq/GBUWmOEQ4AK2Cdd4u5EtJTwX9sf3LLgBjiXdi16TGTBwsZoKA/tmpt38vla1o.mp4";
            
            console.log('Test Video URL:', testVideoUrl);
            
            // Zuerst die Nachricht setzen
            showVideoModal(null, \`**🎬 Test Fashion-Video!**\\n\\n✨ Das Video wird automatisch gespeichert und ist dauerhaft verfügbar.\\n\\n[⬇ Video herunterladen](\${testVideoUrl})\`);

            // Dann das Video einfügen
            setTimeout(() => {
                const mediaContainer = document.getElementById('videoModalMediaContainer');
                if (mediaContainer) {
                    mediaContainer.innerHTML = \`
                        <div style="width:100%;max-width:400px;margin:0 auto;">
                            <video 
                                src="\${testVideoUrl}" 
                                controls 
                                playsinline 
                                autoplay 
                                muted
                                loop
                                style="width:100%;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.3);"
                                onloadstart="console.log('Video lädt:', this.src)"
                                oncanplay="console.log('Video bereit zum Abspielen')"
                                onerror="console.error('Video-Fehler:', this.error)">
                                <source src="\${testVideoUrl}" type="video/mp4">
                                Ihr Browser unterstützt das Video-Element nicht.
                            </video>
                        </div>
                    \`;
                    console.log('Video-Player eingefügt');
                } else {
                    console.error('videoModalMediaContainer nicht gefunden');
                }
            }, 100);
        }
        </script>
    </body>
    </html>
    """

# ---------- Öffentliche Feed-API (Read-Only) ---------- #
def _feed_auth_ok():
    """Token-Schutz für Feed-API über FEED_API_TOKEN (ohne gesetzten Token ist die API gesperrt)."""
    token_required = os.getenv("FEED_API_TOKEN")
    if not token_required:
        return False
    provided = request.headers.get("X-Feed-Token") or request.args.get("token") or ""
    return hmac.compare_digest(provided.encode("utf-8"), token_required.encode("utf-8"))

def _normalize_media_item(session_obj, include_products: bool = False):
    """Extrahiert Feed-relevante Felder aus OutfitSession.
    include_products: wenn True, ergänzt Produkt-Links
    """
    # Bestimme stabile Bild-/Video-URLs (lokal bevorzugt)
    image_url = None
    if session_obj.generated_image_path:
        # generated_image_path kann bereits eine DO-URL sein (nach Persistierung)
        if isinstance(session_obj.generated_image_path, str) and _is_spaces_url(session_obj.generated_image_path):
            image_url = session_obj.generated_image_path
        else:
            p = Path(session_obj.generated_image_path)
            if p.exists() and p.is_file():
                try:
                    rel = p.relative_to(PERSISTENT_DIR)
                    candidate = url_for('serve_public_media', filename=str(rel).replace('\\', '/'), _external=True)
                    # Nur DO-URLs zulassen
                    image_url = candidate if _is_spaces_url(candidate) else None
                except Exception:
                    image_url = None
    # Kein Fallback mehr auf generated_image_url (Replicate) für Feed-Export

    video_url = None
    if session_obj.generated_video_path:
        if isinstance(session_obj.generated_video_path, str) and _is_spaces_url(session_obj.generated_video_path):
            video_url = session_obj.generated_video_path
        else:
            p = Path(session_obj.generated_video_path)
            if p.exists() and p.is_file():
                try:
                    rel = p.relative_to(PERSISTENT_DIR)
                    candidate = url_for('serve_public_media', filename=str(rel).replace('\\', '/'), _external=True)
                    video_url = candidate if _is_spaces_url(candidate) else None
                except Exception:
                    video_url = None
    # Kein Fallback mehr auf generated_video_url (Replicate) für Feed-Export

    # Minimales Schema für Feed-Prototype
    item = {
        'id': str(session_obj.id),
        'created_at': session_obj.created_at.isoformat() if session_obj.created_at else None,
        'image_url': image_url,
        'video_url': video_url,
        'meta': {
            'has_karl': bool(session_obj.karl_analysis),
        }
    }
    if include_products:
        item['products'] = {
            'top_url': getattr(session_obj, 'top_product_url', None),
            'bottom_url': getattr(session_obj, 'bottom_product_url', None)
        }
    return item

@app.route("/api/feed/export")
def api_feed_export():
    """Voll-Export aller Feed-Items (paginiert optional)."""
    if not _feed_auth_ok():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from sqlalchemy import desc
        limit = int(request.args.get('limit', 500))
        cursor = request.args.get('cursor')  # erwartet created_at ISO oder UUID als Tie-Breaker

        query = OutfitSession.query.order_by(desc(OutfitSession.created_at), desc(OutfitSession.id))

        if cursor:
            # Simple cursor: erwartetes Format "<timestamp>|<uuid>"
            try:
                ts_part, id_part = cursor.split('|')
                ts = datetime.fromisoformat(ts_part)
                # Filter: created_at < ts OR (created_at == ts AND id < id_part)
                query = query.filter(
                    (OutfitSession.created_at < ts) |
                    ((OutfitSession.created_at == ts) & (OutfitSession.id < id_part))
                )
            except Exception:
                pass

        sessions = query.limit(limit + 1).all()
        include_products = request.args.get('include_products') in ('1','true','yes') or request.args.get('include') == 'products'
        items = [_normalize_media_item(s, include_products=include_products) for s in sessions[:limit]]
        # DO-only: Items ohne DO-URLs verwerfen
        items = [i for i in items if (_is_spaces_url(i.get('image_url')) or _is_spaces_url(i.get('video_url')))]

        # Wenn keine DO-Items vorhanden → 202/pending mit kompatibler Struktur
        if not items:
            pending_resp = {
                'status': 'pending',
                'items': [],
                'next_cursor': None,
                'count': 0
            }
            response = jsonify(pending_resp)
            response.status_code = 202
            response.headers['Cache-Control'] = 'no-store'
            return response

        next_cursor = None
        if len(sessions) > limit:
            last = sessions[limit - 1]
            ts = (last.created_at or datetime.utcnow()).isoformat()
            next_cursor = f"{ts}|{last.id}"

        resp = {
            'items': items,
            'next_cursor': next_cursor,
            'count': len(items)
        }

        # ETag zur Cache-Unterstützung
        etag = hashlib.sha256(str(resp).encode('utf-8')).hexdigest()
        response = jsonify(resp)
        response.headers['ETag'] = etag
        response.headers['Cache-Control'] = 'public, max-age=30'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/feed/changed")
def api_feed_changed():
    """Inkrementeller Export seit Zeitstempel.
    Query: ?since=ISO8601&limit=500
    """
    if not _feed_auth_ok():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        limit = int(request.args.get('limit', 500))
        since = request.args.get('since')
        if not since:
            return jsonify({'error': 'Param since fehlt (ISO8601)'}), 400

        try:
            since_dt = datetime.fromisoformat(since)
        except Exception:
            return jsonify({'error': 'since ist kein gültiges ISO8601-Datum'}), 400

        from sqlalchemy import or_, desc
        # Als "geändert" gelten neue Sessions oder solche mit generiertem Bild/Video nach since
        include_products = request.args.get('include_products') in ('1','true','yes') or request.args.get('include') == 'products'
        q = (
            OutfitSession.query
            .filter(OutfitSession.created_at >= since_dt)
            .order_by(desc(OutfitSession.created_at), desc(OutfitSession.id))
            .limit(limit)
            .all()
        )

        items = [_normalize_media_item(s, include_products=include_products) for s in q]

        resp = {
            'items': items,
            'count': len(items),
            'since': since
        }
        etag = hashlib.sha256(str(resp).encode('utf-8')).hexdigest()
        response = jsonify(resp)
        response.headers['ETag'] = etag
        response.headers['Cache-Control'] = 'public, max-age=15'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/persistent/<path:filename>")
@require_auth
def serve_persistent_file(filename):
    """Serviert Dateien aus dem persistenten Storage."""
    try:
        file_path = PERSISTENT_DIR / filename
        if file_path.exists() and file_path.is_file():
            from flask import send_file
            return send_file(str(file_path))
        else:
            return "Datei nicht gefunden", 404
    except Exception as e:
        return f"Fehler beim Laden der Datei: {e}", 500


# ---------- Öffentliche Medien-Auslieferung (nur generated/videos) ---------- #
def _is_public_media_allowed(full_path: Path) -> bool:
    """Erlaubt nur Dateien unter uploads/generated und uploads/videos."""
    allowed_bases = [
        (PERSISTENT_DIR / "uploads" / "generated").resolve(),
        (PERSISTENT_DIR / "uploads" / "videos").resolve(),
    ]
    try:
        resolved = full_path.resolve()
        for base in allowed_bases:
            try:
                resolved.relative_to(base)
                return True
            except Exception:
                continue
        return False
    except Exception:
        return False

@app.route("/media/<path:filename>")
def serve_public_media(filename):
    """Öffentliche Auslieferung von Medien in uploads/generated und uploads/videos."""
    try:
        rel = Path(filename)
        # Normalisiere absolute Pfade weg
        if rel.is_absolute():
            rel = Path(*rel.parts[1:])

        candidate = (PERSISTENT_DIR / rel)
        if not candidate.exists() or not candidate.is_file():
            return "Datei nicht gefunden", 404

        if not _is_public_media_allowed(candidate):
            return "Zugriff verweigert", 403

        from flask import send_file
        response = send_file(str(candidate))

        # Cache aggressiv für generierte Bilder, moderat für Videos
        rel_str = str(rel).replace('\\', '/').lower()
        if rel_str.startswith('uploads/generated/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'public, max-age=86400'
        return response
    except Exception as e:
        return f"Fehler beim Laden der Datei: {e}", 500

# === Neu: Ausgewählte Videos für Warte-Screen ===
@app.route("/videos/recent")
@require_auth
def recent_videos():
    """Gibt Videos für den Warte-Screen zurück.

    Wenn der Admin-Flag "wait_show_newest_local_only" aktiviert ist,
    werden ausschließlich die neuesten lokalen Videos (Railway/persistent) geliefert.
    Andernfalls bleibt das bisherige Verhalten: zuerst ausgewählte Videos,
    ansonsten Fallback auf neueste Sessions.
    """
    try:
        limit = int(request.args.get('limit', 8))
        # Admin-Flag lesen
        use_latest_local_only = (get_app_setting('wait_show_newest_local_only', 'false') == 'true')

        if use_latest_local_only:
            # Neueste Videos aus OutfitSession. Akzeptiere persistente Pfade UND CDN-URLs
            from sqlalchemy import desc
            sessions = (
                OutfitSession.query
                .filter(OutfitSession.generated_video_path.isnot(None))
                .order_by(desc(OutfitSession.created_at))
                .limit(limit * 3)  # etwas großzügiger holen, falls einige Dateien fehlen
                .all()
            )

            video_urls = []
            for s in sessions:
                if len(video_urls) >= limit:
                    break
                if not s.generated_video_path:
                    continue
                gp = s.generated_video_path

                # 1) CDN/HTTP-URLs direkt akzeptieren (aber keine flüchtigen Replicate-Links)
                try:
                    if isinstance(gp, str) and gp.lower().startswith(('http://', 'https://')):
                        if 'replicate.delivery' in gp.lower():
                            # Replicate-Links sind kurzlebig → überspringen
                            pass
                        else:
                            video_urls.append(gp)
                            continue
                except Exception:
                    pass

                # 2) Lokale/persistente Datei prüfen und als internen Pfad servieren
                p = Path(gp)
                if p.exists() and p.is_file():
                    try:
                        rel = p.relative_to(PERSISTENT_DIR)
                        url = url_for('serve_persistent_file', filename=str(rel).replace('\\', '/'), _external=True, _scheme='https')
                        video_urls.append(url)
                    except Exception:
                        continue

            return jsonify({ 'videos': video_urls, 'source': 'latest_local_only' })
        
        # Zuerst prüfen ob ausgewählte Videos vorhanden sind
        selected_videos = SelectedVideo.query.filter_by(is_active='true').all()
        
        if selected_videos:
            # Random-Auswahl aus vorselektierten Videos
            import random
            random_selection = random.sample(selected_videos, min(len(selected_videos), limit))
            
            video_urls = []
            for sv in random_selection:
                url = None
                
                # IMMER lokaler Pfad bevorzugen - externe URLs sind temporär!
                if sv.video_path:
                    # Wenn bereits eine Spaces-/CDN-URL gespeichert wurde, direkt verwenden
                    if str(sv.video_path).startswith('http'):
                        url = sv.video_path
                    else:
                        url = None
                
                # Fallback: URL aus SelectedVideo (aber nur wenn lokale Datei nicht verfügbar)
                if not url and sv.video_url and not sv.video_url.startswith('https://replicate.delivery'):
                    url = sv.video_url
                    
                # Wenn nur Replicate-URL verfügbar: Warnung loggen
                if not url and sv.video_url and sv.video_url.startswith('https://replicate.delivery'):
                    print(f"⚠️ Video nur als Replicate-URL verfügbar (wird bald gelöscht): {sv.video_url}")
                    # Als letzter Ausweg trotzdem verwenden, aber wird wahrscheinlich nicht funktionieren
                    url = sv.video_url
                
                if url:
                    video_urls.append(url)
            
            return jsonify({ 'videos': video_urls, 'source': 'selected' })
        
        else:
            # Fallback: Neueste Videos aus OutfitSession (wie vorher)
            from sqlalchemy import desc
            sessions = (
                OutfitSession.query
                .filter(
                    (OutfitSession.generated_video_path.isnot(None)) |
                    (OutfitSession.generated_video_url.isnot(None))
                )
                .order_by(desc(OutfitSession.created_at))
                .limit(limit)
                .all()
            )

            video_urls = []
            for s in sessions:
                url = None
                # Lokaler Pfad bevorzugen, falls vorhanden und Datei existiert
                if s.generated_video_path:
                    p = Path(s.generated_video_path)
                    if p.exists() and p.is_file():
                        try:
                            rel = p.relative_to(PERSISTENT_DIR)
                            url = url_for('serve_persistent_file', filename=str(rel).replace('\\', '/'), _external=True, _scheme='https')
                        except Exception:
                            url = None
                # Fallback Remote-URL
                if not url and s.generated_video_url:
                    url = s.generated_video_url

                if url:
                    video_urls.append(url)

            return jsonify({ 'videos': video_urls, 'source': 'fallback' })
            
    except Exception as e:
        return jsonify({ 'videos': [], 'error': str(e) }), 500

# ---------- Main Routes ---------- #
@app.route("/", methods=["GET", "POST"])
@require_auth
def index():
    if request.method == "POST":
        try:
            # Verwende die neue Funktion für alle drei Felder
            person = _get_url_or_upload("person")
            top    = _get_url_or_upload("top")
            bottom = _get_url_or_upload("bottom")
        except Exception as e:
            return f"Upload-Fehler: {e}", 400

        # Erstelle neue Outfit-Session (optional, falls Database verfügbar)
        outfit_session = None
        try:
            # Optionale Amazon-Produkt-Links aus dem Formular
            top_product_url = request.form.get('top_product_url')
            bottom_product_url = request.form.get('bottom_product_url')

            outfit_session = OutfitSession(
                person_image_path=person,  # Speichere die URL/Pfad wie sie ist
                top_image_path=top,
                bottom_image_path=bottom,
                top_product_url=top_product_url,
                bottom_product_url=bottom_product_url,
                user_session=session.get('session_id', str(uuid.uuid4()))
            )
            db.session.add(outfit_session)
            db.session.commit()
            print(f"✅ Session gespeichert: {outfit_session.id}")
            print(f"   Person: {person}")
            print(f"   Top: {top}")
            print(f"   Bottom: {bottom}")
        except Exception as e:
            print(f"Database session error (continuing without DB): {e}")
            outfit_session = None

        # Ein Outfit-Bild generieren (mit kurzer Retry-Strategie und sauberem Fehler-Response)
        try:
            pred = replicate.predictions.create(
                model="runwayml/gen4-image",
                input={
                    "prompt": "A realistic photo of @person wearing @top and @bottom, do not change the color of the hair, do not change the haircut",
                    "resolution": "1080p",
                    "aspect_ratio": "1:1",
                    "reference_tags": ["person", "top", "bottom"],
                    "reference_images": [person, top, bottom]
                }
            )
        except Exception as e:
            # Einmal kurzer Retry bei transienten Upstream-Fehlern
            try:
                import time as _t
                _t.sleep(1)
                pred = replicate.predictions.create(
                    model="runwayml/gen4-image",
                    input={
                        "prompt": "A realistic photo of @person wearing @top and @bottom, do not change the color of the hair, do not change the haircut",
                        "resolution": "1080p",
                        "aspect_ratio": "1:1",
                        "reference_tags": ["person", "top", "bottom"],
                        "reference_images": [person, top, bottom]
                    }
                )
            except Exception as e2:
                err_text = f"Temporärer Fehler bei der Bildgenerierung (Upstream). Bitte später erneut versuchen. Details: {str(e2)}"
                print(f"❌ Replicate create failed: {e2}")
                # 502 wenn Upstream 502, sonst 500
                status_code = 502 if "502" in str(e2) else 500
                return err_text, status_code
        prediction_ids = [pred.id]
        
        # Speichere Session-ID für spätere Referenz (falls Database verfügbar)
        if outfit_session:
            session['current_outfit_session'] = str(outfit_session.id)
        session['session_id'] = session.get('session_id', str(uuid.uuid4()))

        # Übergib die Prediction-IDs an die Ergebnis-Seite
        return redirect(url_for("result", ids=",".join(prediction_ids)))

    return render_template("index.html", version=BUILD_INFO)

@app.route("/result")
@require_auth
def result():
    # Erwartet ?ids=id1,id2,id3
    ids = request.args.get("ids", "")
    return render_template("result.html", prediction_ids=ids.split(","))

@app.route("/status/<prediction_id>")
@require_auth  # Auch geschützt, da nur authentifizierte User Predictions haben
def status(prediction_id):
    pred = replicate_client.predictions.get(prediction_id)
    
    # Wenn Prediction erfolgreich und Bild vorhanden, speichere in Database
    if pred.status == "succeeded" and pred.output:
        try:
            # Normalisiere Bild-URL (String oder Liste)
            if isinstance(pred.output, list) and len(pred.output) > 0:
                image_url = pred.output[0]
            else:
                image_url = str(pred.output)

            # Deterministischer Dateiname pro Prediction-ID → stabile URL
            deterministic_filename = f"prediction_{prediction_id}.jpg"
            deterministic_rel = f"uploads/generated/{deterministic_filename}"
            deterministic_path = GENERATED_FOLDER / deterministic_filename

            # Lade Bild herunter und speichere in Spaces (deterministischer Key)
            try:
                resp = requests.get(image_url, timeout=30)
                if resp.status_code == 200:
                    key = f"uploads/generated/{deterministic_filename}"
                    _spaces_upload_bytes(resp.content, key, content_type="image/jpeg")
                    print(f"✅ Bild in Spaces gespeichert: {key}")
                else:
                    print(f"❌ Download für deterministische Datei fehlgeschlagen: {resp.status_code}")
            except Exception as e:
                print(f"⚠️ Fehler beim Upload zu Spaces: {e}")

            current_session_id = session.get('current_outfit_session')
            print(f"🔍 Status-Check für Session: {current_session_id}")
            
            if current_session_id:
                # IDs sind Strings (UUID als Text)
                session_uuid = current_session_id
                outfit_session = OutfitSession.query.filter_by(id=session_uuid).first()
                if outfit_session and not outfit_session.generated_image_url:
                    print(f"📥 Speichere Bild: {image_url}")
                    # Speichere URL in Database
                    outfit_session.generated_image_url = image_url
                    # Speichere Spaces-URL als Pfad (vereinheitlichte Nutzung)
                    outfit_session.generated_image_path = _spaces_public_url(f"uploads/generated/{deterministic_filename}")
                    db.session.commit()
                    print(f"✅ Generiertes Bild in Database gespeichert!")
                else:
                    if not outfit_session:
                        print(f"❌ Session nicht gefunden: {session_uuid}")
                    else:
                        print(f"ℹ️ Bild bereits gespeichert für Session: {session_uuid}")
            else:
                print("⚠️ Keine aktuelle Session für Bild-Speicherung")
        except Exception as db_error:
            print(f"❌ Fehler beim Speichern des generierten Bildes: {db_error}")
            import traceback
            traceback.print_exc()

    # Immer eine stabile lokale URL zurückgeben, sofern möglich
    try:
        if pred.status == "succeeded" and pred.output:
            deterministic_filename = f"prediction_{prediction_id}.jpg"
            deterministic_rel = f"uploads/generated/{deterministic_filename}"
            deterministic_path = GENERATED_FOLDER / deterministic_filename
            local_url = None
            # Gebe Spaces-URL zurück (stabile CDN-URL)
            local_url = _spaces_public_url(deterministic_rel)
        else:
            local_url = None
    except Exception:
        local_url = None

    return jsonify({
        "status": pred.status,
        "output": pred.output,
        "local_url": local_url,
        "error": getattr(pred, "error", None),
        "logs": getattr(pred, "logs", None),
    })


# === NEU: Video-Prediction starten ===
@app.route("/video/create", methods=["POST"])
@require_auth
def video_create():
    data = request.get_json(force=True)
    image_url = data.get("image_url")
    prompt = data.get("prompt", "A short cinematic fashion shot of the outfit. Subtle camera dolly-in.")

    if not image_url:
        return jsonify({"error": "image_url fehlt"}), 400

    try:
        pred = replicate.predictions.create(
            model="runwayml/gen4-turbo",
            input={
                "image": image_url,
                "prompt": prompt,
                "aspect_ratio": "1:1"
                # Optional: weitere Parameter gem. Model-Schema
            }
        )
        return jsonify({"prediction_id": pred.id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === NEU: Video-Prediction pollen ===
@app.route("/video/status/<prediction_id>")
@require_auth
def video_status(prediction_id):
    pred = replicate_client.predictions.get(prediction_id)
    
    # Wenn Video erfolgreich und vorhanden, speichere in Database
    if pred.status == "succeeded" and pred.output:
        try:
            current_session_id = session.get('current_outfit_session')
            print(f"🎬 Video-Status-Check für Session: {current_session_id}")
            
            if current_session_id:
                # IDs sind Strings (UUID als Text)
                session_uuid = current_session_id
                outfit_session = OutfitSession.query.filter_by(id=session_uuid).first()
                if outfit_session and not outfit_session.generated_video_url:
                        # pred.output kann String oder Liste sein - normalisieren
                        if isinstance(pred.output, list) and len(pred.output) > 0:
                            video_url = pred.output[0]
                        else:
                            video_url = str(pred.output)
                        
                        print(f"🎥 Speichere Video: {video_url}")
                        
                        # Speichere URL in Database
                        outfit_session.generated_video_url = video_url
                        
                        # Lade Video herunter und speichere in Spaces
                        try:
                            print(f"⬇️ Lade Video herunter...")
                            response = requests.get(video_url, timeout=60)
                            if response.status_code == 200:
                                filename = f"video_{uuid.uuid4().hex}.mp4"
                                key = f"uploads/videos/{filename}"
                                _spaces_upload_bytes(response.content, key, content_type="video/mp4")
                                spaces_url = _spaces_public_url(key)
                                outfit_session.generated_video_path = spaces_url
                                print(f"✅ Video in Spaces gespeichert: {spaces_url}")
                                print(f"📏 Video-Größe: {len(response.content) / 1024 / 1024:.2f} MB")
                            else:
                                print(f"❌ Video-Download fehlgeschlagen: Status {response.status_code}")
                        except Exception as download_error:
                            print(f"⚠️ Video-Upload zu Spaces fehlgeschlagen: {download_error}")
                            # Weiter mit URL - kein kritischer Fehler
                        
                        db.session.commit()
                        print(f"✅ Generiertes Video in Database gespeichert!")
                else:
                    if not outfit_session:
                        print(f"❌ Session nicht gefunden: {session_uuid}")
                    else:
                        print(f"ℹ️ Video bereits gespeichert für Session: {session_uuid}")
            else:
                print("⚠️ Keine aktuelle Session für Video-Speicherung")
        except Exception as db_error:
            print(f"❌ Fehler beim Speichern des generierten Videos: {db_error}")
            import traceback
            traceback.print_exc()
    
    # CDN-URL ermitteln, falls wir oben erfolgreich in Spaces gespeichert haben
    cdn_url = None
    try:
        current_session_id = session.get('current_outfit_session')
        if current_session_id:
            s = OutfitSession.query.filter_by(id=current_session_id).first()
            if s and s.generated_video_path and str(s.generated_video_path).startswith('http'):
                cdn_url = s.generated_video_path
    except Exception:
        cdn_url = None

    return jsonify({
        "status": pred.status,
        "output": getattr(pred, "output", None),  # Original (Replicate) URL
        "local_url": cdn_url,                       # CDN-URL aus Spaces
        "error": getattr(pred, "error", None),
        "logs": getattr(pred, "logs", None),
    })


# === Video-Auswahl Admin-Interface ===
@app.route("/admin/videos")
@require_auth
def admin_videos():
    """Admin-Interface für Video-Auswahl."""
    # Nur Videos mit lokalen Pfaden - externe URLs sind temporär!
    from sqlalchemy import desc
    available_sessions = (
        OutfitSession.query
        .filter(OutfitSession.generated_video_path.isnot(None))
        .order_by(desc(OutfitSession.created_at))
        .all()
    )
    
    # Zusätzlich prüfen ob Dateien tatsächlich existieren
    valid_sessions = []
    for session in available_sessions:
        if not session.generated_video_path:
            continue
        path_val = session.generated_video_path
        try:
            # CDN/HTTP-URLs direkt akzeptieren
            if isinstance(path_val, str) and path_val.lower().startswith(('http://', 'https://')):
                valid_sessions.append(session)
                continue
            # Lokale/persistente Datei prüfen
            p = Path(path_val)
            if p.exists() and p.is_file():
                valid_sessions.append(session)
            else:
                print(f"⚠️ Video-Datei nicht gefunden: {path_val}")
        except Exception:
            print(f"⚠️ Ungültiger Videopfad: {path_val}")
    
    available_sessions = valid_sessions
    
    # Bereits ausgewählte Videos
    selected_videos = SelectedVideo.query.all()
    selected_session_ids = {str(sv.outfit_session_id) for sv in selected_videos if sv.outfit_session_id}
    
    # Flag aus Settings lesen
    newest_first_flag = (get_app_setting('wait_show_newest_local_only', 'false') == 'true')
    return render_template('admin_videos.html', 
                         available_sessions=available_sessions,
                         selected_videos=selected_videos,
                         selected_session_ids=selected_session_ids,
                         newest_first_flag=newest_first_flag)

@app.route("/admin/videos/toggle", methods=["POST"])
@require_auth
def admin_videos_toggle():
    """Video zur Auswahl hinzufügen oder entfernen."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        action = data.get('action')  # 'add' oder 'remove'
        
        if not session_id or not action:
            return jsonify({'error': 'session_id und action erforderlich'}), 400
        
        # UUID konvertieren
        import uuid as uuid_module
        if action == 'add':
            # Session finden
            outfit_session = OutfitSession.query.filter_by(id=session_id).first()
            if not outfit_session:
                return jsonify({'error': 'Session nicht gefunden'}), 404
            
            # Prüfen ob bereits ausgewählt
            existing = SelectedVideo.query.filter_by(outfit_session_id=session_uuid).first()
            if existing:
                return jsonify({'error': 'Video bereits ausgewählt'}), 400
            
            # Neuen SelectedVideo-Eintrag erstellen - lokaler Pfad bevorzugt
            video_url = None
            if outfit_session.generated_video_path:
                # Lokale URL generieren
                p = Path(outfit_session.generated_video_path)
                if p.exists() and p.is_file():
                    try:
                        rel = p.relative_to(PERSISTENT_DIR)
                        video_url = url_for('serve_persistent_file', filename=str(rel).replace('\\', '/'), _external=True, _scheme='https')
                    except Exception:
                        video_url = None
            
            # Fallback nur wenn lokale Datei nicht verfügbar
            if not video_url:
                video_url = outfit_session.generated_video_url
            
            selected_video = SelectedVideo(
                outfit_session_id=session_id,
                video_url=video_url,  # Lokale URL bevorzugt
                video_path=outfit_session.generated_video_path,
                title=f"Video {outfit_session.created_at.strftime('%Y-%m-%d %H:%M')}",
                is_active='true'
            )
            
            db.session.add(selected_video)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Video zur Auswahl hinzugefügt'})
        
        elif action == 'remove':
            # SelectedVideo-Eintrag finden und löschen
            selected_video = SelectedVideo.query.filter_by(outfit_session_id=session_id).first()
            if not selected_video:
                return jsonify({'error': 'Video nicht in Auswahl gefunden'}), 404
            
            db.session.delete(selected_video)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Video aus Auswahl entfernt'})
        
        else:
            return jsonify({'error': 'Ungültige Aktion'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/admin/videos/toggle-active", methods=["POST"])
@require_auth
def admin_videos_toggle_active():
    """Video aktivieren/deaktivieren ohne es zu löschen."""
    try:
        data = request.get_json()
        video_id = data.get('video_id')
        is_active = data.get('is_active')  # 'true' oder 'false'
        
        if not video_id or is_active not in ['true', 'false']:
            return jsonify({'error': 'video_id und is_active (true/false) erforderlich'}), 400
        
        # UUID konvertieren
        import uuid as uuid_module
        try:
            video_uuid = uuid_module.UUID(video_id)
        except ValueError:
            return jsonify({'error': 'Ungültige Video-ID'}), 400
        
        # SelectedVideo finden und Status ändern
        selected_video = SelectedVideo.query.filter_by(id=video_uuid).first()
        if not selected_video:
            return jsonify({'error': 'Video nicht gefunden'}), 404
        
        selected_video.is_active = is_active
        db.session.commit()
        
        status = 'aktiviert' if is_active == 'true' else 'deaktiviert'
        return jsonify({'success': True, 'message': f'Video {status}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/admin/videos/mode", methods=["POST"])
@require_auth
def admin_videos_mode():
    """Schaltet den Wartemodus um: neueste lokale Videos zuerst vs. Vorauswahl."""
    try:
        data = request.get_json()
        enabled = data.get('enabled')  # 'true' oder 'false'
        if str(enabled).lower() not in ['true', 'false']:
            return jsonify({'error': 'enabled muss true/false sein'}), 400
        enabled_str = 'true' if str(enabled).lower() == 'true' else 'false'
        set_app_setting('wait_show_newest_local_only', enabled_str)
        return jsonify({'success': True, 'message': 'Modus aktualisiert', 'enabled': enabled_str})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@require_auth  # Auch geschützt, da nur authentifizierte User Karl fragen können
def api_chat():
    """
    KI-basierte Outfit-Beratung über Replicate.
    Analysiert das generierte Outfit-Bild und gibt stilistische Tipps.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Keine JSON-Daten erhalten"}), 400
        
        image_url = data.get("image_url")
        user_message = data.get("message", "Analysiere dieses Outfit und gib Styling-Tipps.")
        
        if not image_url:
            return jsonify({"error": "image_url ist erforderlich"}), 400
        
        # System-Prompt für GPT-4.1 Fashion-Analyse
        prompt = f"""You are Karl, a professional fashion stylist and outfit consultant. 
Analyze the outfit in this image and provide a stylistic assessment.

IMPORTANT GUIDELINES:
- Refer directly to the outfit shown in the image in your response
- Address colors, style, fit, moods and concrete improvement suggestions
- Judge only clothing & accessories (cut, colors, combination suggestions, care/material)
- NO statements about identity, demographics (age, gender, ethnicity), body characteristics or attractiveness
- If a person is visible, treat them like a mannequin

Task: {user_message}

Please structure your response as follows:
## 👗 Outfit Analysis

### ✅ What I like:
- [Positive aspects of the outfit - colors, cuts, style]

### 💡 Improvement suggestions:
- [Concrete styling tips for clothing and accessories]

### 🎨 Styling Tip of the Day:
[A special tip for this outfit]

Respond in English and be constructive and encouraging! Focus only on fashion and styling."""

        # Replicate API-Aufruf mit GPT-4.1 Vision-Modell
        # Verwende OpenAI GPT-4.1 über Replicate (stabil und leistungsstark)
        output = replicate.run(
            "openai/gpt-4.1",
            input={
                "prompt": user_message,
                "image_input": [image_url],
                "system_prompt": prompt
            }
        )
        
        # GPT-4.1 gibt direkt Text zurück (nicht als Prediction-Objekt)
        if output:
            response_text = "".join(output) if isinstance(output, list) else str(output)
            
            # Speichere Karl-Analyse in Database (falls Session vorhanden)
            try:
                current_session_id = session.get('current_outfit_session')
                print(f"🔍 Karl-Analyse für Session: {current_session_id}")
                
                if current_session_id:
                    # Konvertiere String zu UUID falls nötig
                    import uuid as uuid_module
                    try:
                        if isinstance(current_session_id, str):
                            session_uuid = uuid_module.UUID(current_session_id)
                        else:
                            session_uuid = current_session_id
                    except ValueError:
                        print(f"❌ Ungültige Session-UUID: {current_session_id}")
                        session_uuid = None
                    
                    if session_uuid:
                        outfit_session = OutfitSession.query.filter_by(id=session_uuid).first()
                        if outfit_session:
                            outfit_session.karl_analysis = response_text
                            db.session.commit()
                            print(f"✅ Karl-Analyse gespeichert für Session {session_uuid}")
                        else:
                            print(f"❌ Session nicht gefunden: {session_uuid}")
                else:
                    print("⚠️ Keine aktuelle Session für Karl-Analyse")
            except Exception as db_error:
                print(f"❌ Fehler beim Speichern der Karl-Analyse: {db_error}")
                # Weiter ohne Fehler - Karl funktioniert trotzdem
            
            return jsonify({
                "response": response_text,
                "status": "success"
            })
        else:
            return jsonify({
                "error": "GPT-4.1 gab keine Antwort zurück",
                "status": "failed"
            }), 500

            
    except Exception as e:
        print(f"Chat API Fehler: {str(e)}")
        return jsonify({
            "error": f"Unerwarteter Fehler: {str(e)}",
            "status": "error"
        }), 500


@app.route("/setup-persons")
@require_auth
def setup_persons():
    """
    Hilfsfunktion zum Einrichten der Personen-Ordner.
    Kann einmalig aufgerufen werden, um die Ordnerstruktur zu erstellen.
    """
    try:
        female_folder, male_folder = _ensure_persons_folder()

        # Erstelle Platzhalter-Info-Dateien
        info_text = """
Platzieren Sie hier die vorgefertigten Personen-Bilder:

Für weibliche Personen:
- person_f1.jpg bis person_f12.jpg

Für männliche Personen:
- person_m1.jpg bis person_m12.jpg

Die Bilder sollten hochauflösend und gut beleuchtet sein.
Idealerweise zeigen sie eine Person in neutraler Pose vor einem einfachen Hintergrund.
"""

        (female_folder / "README.txt").write_text(info_text)
        (male_folder / "README.txt").write_text(info_text)

        return jsonify({
            "success": True,
            "message": f"Personen-Ordner erstellt unter: {PERSONS_FOLDER}",
            "female_folder": str(female_folder),
            "male_folder": str(male_folder)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/search/amazon", methods=["POST"])
@require_auth
def amazon_search():
    """
    Server-seitige Amazon PA-API Suche (löst CORS-Problem)
    """
    import json
    import hmac
    import hashlib
    from datetime import datetime
    from urllib.parse import quote

    # Amazon Konfiguration (AUS UMGEBUNGSVARIABLEN)
    ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
    SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
    PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG")
    REGION = "eu-west-1"
    HOST = "webservices.amazon.de"
    URI_PATH = "/paapi5/searchitems"

    # Debug-Ausgabe
    print(f"Amazon Keys - Access: {'gesetzt' if ACCESS_KEY else 'NICHT GESETZT'}, Secret: {'gesetzt' if SECRET_KEY else 'NICHT GESETZT'}")

    if not ACCESS_KEY or not SECRET_KEY or not PARTNER_TAG:
        return jsonify({"error": "Amazon API-Schlüssel nicht konfiguriert!"}), 500

    try:
        # Request-Daten vom Frontend
        data = request.get_json()
        keywords = data.get("keywords", "")
        # gewünschte Gesamtanzahl (mobil 12, Desktop 36), Server sammelt seitenweise
        total_count = int(data.get("totalCount", data.get("itemCount", 8)))
        total_count = max(1, min(total_count, 40))  # hartes Cap für Serverlast

        print(f"Amazon-Suche für: {keywords}")  # Debug

        # Amazon PA-API Payload
        def build_payload(item_count_page: int, item_page: int):
            return json.dumps({
                "Keywords": keywords,
                "Resources": [
                    "Images.Primary.Large",
                    "Images.Primary.Medium",
                    "Images.Primary.Small",
                    "Images.Variants.Large",
                    "Images.Variants.Medium",
                    "Images.Variants.Small"
                ],
                "PartnerTag": PARTNER_TAG,
                "PartnerType": "Associates",
                "Marketplace": "www.amazon.de",
                "SearchIndex": "Fashion",
                "ItemCount": item_count_page,
                "ItemPage": item_page
            })

        # AWS V4 Signatur erstellen
        def sign_request(method, uri, headers, payload, access_key, secret_key, region, service):
            now = datetime.utcnow()
            amzdate = now.strftime('%Y%m%dT%H%M%SZ')
            datestamp = now.strftime('%Y%m%d')

            canonical_headers = '\n'.join([f"{k.lower()}:{v}" for k, v in sorted(headers.items())]) + '\n'
            signed_headers = ';'.join([k.lower() for k in sorted(headers.keys())])

            payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            canonical_request = f"{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

            algorithm = 'AWS4-HMAC-SHA256'
            credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
            string_to_sign = f"{algorithm}\n{amzdate}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

            def get_signature_key(key, date_stamp, region_name, service_name):
                k_date = hmac.new(('AWS4' + key).encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
                k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
                k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
                k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
                return k_signing

            signing_key = get_signature_key(SECRET_KEY, datestamp, region, service)
            signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

            authorization_header = f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

            return {
                **headers,
                'X-Amz-Date': amzdate,
                'Authorization': authorization_header
            }

        headers = {
            'host': HOST,
            'content-type': 'application/json; charset=UTF-8',
            'x-amz-target': 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems',
            'content-encoding': 'amz-1.0'
        }

        def call_amazon(item_count_page: int, item_page: int):
            payload = build_payload(item_count_page, item_page)
            signed = sign_request('POST', URI_PATH, headers, payload, ACCESS_KEY, SECRET_KEY, REGION, 'ProductAdvertisingAPI')
            r = requests.post(
                f"https://{HOST}{URI_PATH}",
                headers=signed,
                data=payload,
                timeout=30
            )
            return r

        # Cache-Key bilden: Keywords + gewünschte Anzahl (Desktop/Mobil)
        cache_key = f"amazon::{keywords.strip()}::n={total_count}"
        cached = search_cache.get(cache_key)
        if cached is not None:
            resp = jsonify(cached)
            try:
                resp.headers['X-Cache'] = 'HIT'
            except Exception:
                pass
            return resp

        print(f"Rufe Amazon API auf: {HOST}{URI_PATH} (ziel: {total_count} Produkte)")

        seen_asins = set()
        aggregated = []
        page = 1
        max_pages = 5  # Sicherheitsgrenze
        while len(aggregated) < total_count and page <= max_pages:
            remaining = total_count - len(aggregated)
            per_page = 10 if remaining > 10 else remaining
            response = call_amazon(per_page, page)
            print(f"Amazon API Response (page {page}): Status {response.status_code}")
            if response.status_code != 200:
                error_text = response.text[:500]
                print(f"Amazon API Fehler: {response.status_code} - {error_text}")
                if page == 1:
                    return jsonify({"error": f"Amazon API Fehler: {response.status_code}", "details": error_text}), 500
                break

            amazon_data = response.json()
            items = amazon_data.get('SearchResult', {}).get('Items', [])
            if not items:
                print("Keine Items in Amazon Response (leer)")
                break

            for item in items:
                asin = item.get('ASIN') or ''
                if asin in seen_asins:
                    continue
                seen_asins.add(asin)

                image_url = 'https://via.placeholder.com/300x400?text=No+Image'
                if item.get('Images', {}).get('Primary', {}).get('Large', {}).get('URL'):
                    image_url = item['Images']['Primary']['Large']['URL']
                elif item.get('Images', {}).get('Primary', {}).get('Medium', {}).get('URL'):
                    image_url = item['Images']['Primary']['Medium']['URL']
                elif item.get('Images', {}).get('Primary', {}).get('Small', {}).get('URL'):
                    image_url = item['Images']['Primary']['Small']['URL']
                elif item.get('Images', {}).get('Variants') and len(item['Images']['Variants']) > 0:
                    variant = item['Images']['Variants'][0]
                    if variant.get('Large', {}).get('URL'):
                        image_url = variant['Large']['URL']
                    elif variant.get('Medium', {}).get('URL'):
                        image_url = variant['Medium']['URL']

                aggregated.append({
                    'id': f"amazon-{asin}",
                    'name': 'Fashion Item',
                    'image': image_url,
                    'thumbnail': image_url,
                    'asin': asin,
                    'detailUrl': item.get('DetailPageURL')
                })

                if len(aggregated) >= total_count:
                    break

            page += 1

        result = aggregated[:total_count]
        # im Cache speichern (15 Minuten)
        search_cache.set(cache_key, result, ttl_seconds=900)
        print(f"Verarbeitet: {len(result)} Produkte (gewünscht: {total_count}) – gecached")
        resp = jsonify(result)
        try:
            resp.headers['X-Cache'] = 'MISS'
        except Exception:
            pass
        return resp

    except Exception as e:
        print(f"Amazon Search Fehler: {str(e)}")
        import traceback
        traceback.print_exc()  # Vollständiger Stack-Trace
        return jsonify({"error": str(e)}), 500

# ---------- Database Initialization ---------- #
def init_database():
    """Initialisiert die Datenbank und erstellt alle Tabellen."""
    try:
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # Fallback: Continue without database for now
        return False
    return True

# ---------- Helper Functions für persistente Speicherung ---------- #
def save_generated_image(image_url, session_id=None):
    """Lädt ein generiertes Bild herunter und speichert es persistent."""
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            filename = f"generated_{uuid.uuid4().hex}.jpg"
            file_path = GENERATED_FOLDER / filename
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return str(file_path)
    except Exception as e:
        print(f"Fehler beim Speichern des generierten Bildes: {e}")
    return None

# Initialisiere Database beim Import (nicht nur bei __main__)
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables created successfully!")
        # Sicherstellen, dass neue Spalten vorhanden sind (SQLite/Postgres)
        def _ensure_outfit_product_url_columns():
            try:
                from sqlalchemy import text as _sa_text
                engine = db.engine
                dialect = engine.dialect.name
                with engine.connect() as conn:
                    if dialect == 'sqlite':
                        rows = conn.execute(_sa_text("PRAGMA table_info('outfit_sessions')")).fetchall()
                        cols = {row[1] for row in rows}
                        if 'top_product_url' not in cols:
                            conn.execute(_sa_text("ALTER TABLE outfit_sessions ADD COLUMN top_product_url TEXT"))
                        if 'bottom_product_url' not in cols:
                            conn.execute(_sa_text("ALTER TABLE outfit_sessions ADD COLUMN bottom_product_url TEXT"))
                    else:
                        # Postgres und andere: IF NOT EXISTS verwenden
                        conn.execute(_sa_text("ALTER TABLE outfit_sessions ADD COLUMN IF NOT EXISTS top_product_url VARCHAR(1000)"))
                        conn.execute(_sa_text("ALTER TABLE outfit_sessions ADD COLUMN IF NOT EXISTS bottom_product_url VARCHAR(1000)"))
                print("✅ OutfitSession Produkt-Link-Spalten geprüft/angelegt")
            except Exception as _e:
                print(f"⚠️ Konnte Produkt-Link-Spalten nicht sicherstellen: {_e}")
        _ensure_outfit_product_url_columns()
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

if __name__ == "__main__":
    # Erstelle Ordner
    _ensure_persons_folder()  # Erstelle Personen-Ordner beim Start
    
    # Tabellen erstellen falls sie nicht existieren
    with app.app_context():
        db.create_all()
        print("✅ Database-Tabellen erstellt/aktualisiert")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')