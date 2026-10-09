# OutfitSnap Storage Architecture

## 🎯 Ziel
Persistente Speicherung aller Daten (Bilder, Videos, Metadaten) bei Railway

## 🏗️ Architektur

### 1. Railway Volume (Dateien)
```
/app/persistent/
├── uploads/           # User-Uploads
│   ├── images/        # Original Bilder
│   ├── generated/     # Gen-4 Outfit-Bilder
│   └── videos/        # Generierte Videos
├── avatars/           # Vorgefertigte Personen
└── cache/             # Temporäre Dateien
```

### 2. PostgreSQL Database (Metadaten)
```sql
-- Outfit Sessions
CREATE TABLE outfit_sessions (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP,
    person_image_path TEXT,
    top_image_path TEXT,
    bottom_image_path TEXT,
    generated_image_url TEXT,
    generated_video_url TEXT,
    karl_analysis TEXT
);

-- User Preferences (optional)
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY,
    session_id TEXT,
    preferred_styles JSON,
    created_at TIMESTAMP
);
```

## 🔧 Implementation Steps

### Phase 1: Volume Setup
1. Railway Volume erstellen (50GB)
2. Mount Point: `/app/persistent`
3. Ordnerstruktur erstellen
4. Upload-Logic anpassen

### Phase 2: Database Setup  
1. PostgreSQL Service hinzufügen
2. Database Schema erstellen
3. SQLAlchemy Integration
4. Session-Tracking implementieren

### Phase 3: File Management
1. Permanente Speicherung aller Uploads
2. Generated Content speichern
3. Cleanup-Jobs für alte Dateien
4. Backup-Strategie

## 💰 Kosten (geschätzt)
- Railway Volume 50GB: ~$12.50/Monat
- PostgreSQL Hobby: ~$5/Monat
- **Total: ~$17.50/Monat**

## ✅ Vorteile
- Vollständige Datenpersistenz
- Schneller lokaler Zugriff
- Backup-Integration
- Skalierbare Architektur
- Keine externen Dependencies
