/* ------------------------------------------------------------------ */
/* 1 — Konfiguration (Nur Amazon, keine Google APIs)                  */
/* ------------------------------------------------------------------ */

window.searchQueries = {
  tops: {
    'dresses': 'Kleider elegant',
    'shirts'  : 'Hemd Frau',
    'sweaters': 'Pullover Frau',
    'jackets' : 'Jacke Frau'
  },
  bottoms: {
    'jeans'   : 'Jeans frau',
    'trousers': 'Hose frau',
    'skirts'  : 'Rock',
    'shorts'  : 'Shorts kurze Hose frau'
  }
};

// Standard-Suchbegriffe für den Suche-Tab
window.defaultSearchQueries = {
  tops: 'Bluse',
  bottoms: 'Hose chino frau'
};

/* ------------------------------------------------------------- */
/* Genderspezifische Konfiguration (abweichend für männlich)     */
/* ------------------------------------------------------------- */
// Weiblich nutzt die bestehenden Objekte (window.searchQueries, window.defaultSearchQueries)
window.searchQueriesMale = {
  tops: {
    't-shirts': 'T-Shirt Herren',
    'shirts'  : 'Hemd Herren',
    'sweaters': 'Pullover Herren',
    'jackets' : 'Jacke Herren'
  },
  bottoms: {
    'jeans'   : 'Jeans Herren',
    'trousers': 'Hose Herren',
    // Bei männlich lassen wir „skirts" weg
    'shorts'  : 'Shorts Herren'
  }
};

window.defaultSearchQueriesMale = {
  tops: 'Hemd',
  bottoms: 'Jeans Herren'
};

// Aktuell gewähltes Geschlecht (bei Personenauswahl gesetzt)
window.selectedGender = null; // 'female' | 'male'

function getGenderedSearchQueries() {
  return window.selectedGender === 'male' ? window.searchQueriesMale : window.searchQueries;
}

function getGenderedDefaultSearchQueries() {
  return window.selectedGender === 'male' ? window.defaultSearchQueriesMale : window.defaultSearchQueries;
}

// Vorgefertigte Personen-Datenbank
window.personDatabase = {
  female: [
    { id: 'f13', name: 'Clara', image: '/static/persons/female/person_f13.jpg' },
    { id: 'f14', name: 'Elena', image: '/static/persons/female/person_f14.jpg' },
    { id: 'f15', name: 'Petra', image: '/static/persons/female/person_f15.jpg' },
    { id: 'f16', name: 'Katharina', image: '/static/persons/female/person_f16.jpg' },
    { id: 'f17', name: 'Melanie', image: '/static/persons/female/person_f17.jpg' },
    { id: 'f18', name: 'Sandra', image: '/static/persons/female/person_f18.jpg' },
    { id: 'f19', name: 'Stefanie', image: '/static/persons/female/person_f19.jpg' },
    { id: 'f20', name: 'Nadine', image: '/static/persons/female/person_f20.jpg' },
    { id: 'f21', name: 'Isabelle', image: '/static/persons/female/person_f21.jpg' },
    { id: 'f22', name: 'Vanessa', image: '/static/persons/female/person_f22.jpg' },
    { id: 'f23', name: 'Jessica', image: '/static/persons/female/person_f23.jpg' },
    { id: 'f24', name: 'Michelle', image: '/static/persons/female/person_f24.jpg' },
    { id: 'f25', name: 'Andrea', image: '/static/persons/female/person_f25.jpg' },
    { id: 'f26', name: 'Christina', image: '/static/persons/female/person_f26.jpg' },
    { id: 'f27', name: 'Daniela', image: '/static/persons/female/person_f27.jpg' },
    { id: 'f28', name: 'Franziska', image: '/static/persons/female/person_f28.jpg' },
    { id: 'f29', name: 'Sabrina', image: '/static/persons/female/person_f29.jpg' },
    { id: 'f30', name: 'Jennifer', image: '/static/persons/female/person_f30.jpg' },
    { id: 'f31', name: 'Claudia', image: '/static/persons/female/person_f31.jpg' },
    { id: 'f32', name: 'Verena', image: '/static/persons/female/person_f32.jpg' },
    { id: 'f33', name: 'Bianca', image: '/static/persons/female/person_f33.jpg' },
    { id: 'f34', name: 'Carina', image: '/static/persons/female/person_f34.jpg' },
    { id: 'f35', name: 'Diana', image: '/static/persons/female/person_f35.jpg' },
    { id: 'f36', name: 'Evelyn', image: '/static/persons/female/person_f36.jpg' },
    { id: 'f37', name: 'Gabriela', image: '/static/persons/female/person_f37.jpg' },
    { id: 'f38', name: 'Helena', image: '/static/persons/female/person_f38.jpg' },
    { id: 'f39', name: 'Ines', image: '/static/persons/female/person_f39.jpg' },
    { id: 'f40', name: 'Jasmin', image: '/static/persons/female/person_f40.jpg' },
    { id: 'f41', name: 'Karin', image: '/static/persons/female/person_f41.jpg' },
    { id: 'f42', name: 'Larisa', image: '/static/persons/female/person_f42.jpg' },
    { id: 'f43', name: 'Martina', image: '/static/persons/female/person_f43.jpg' },
    { id: 'f44', name: 'Nora', image: '/static/persons/female/person_f44.jpg' },
    { id: 'f45', name: 'Olivia', image: '/static/persons/female/person_f45.jpg' },
    { id: 'f46', name: 'Paula', image: '/static/persons/female/person_f46.jpg' },
    { id: 'f47', name: 'Ricarda', image: '/static/persons/female/person_f47.jpg' },
    { id: 'f48', name: 'Simone', image: '/static/persons/female/person_f48.jpg' },
    { id: 'f49', name: 'Tanja', image: '/static/persons/female/person_f49.jpg' },
    { id: 'f50', name: 'Ulrike', image: '/static/persons/female/person_f50.jpg' },
    { id: 'f51', name: 'Victoria', image: '/static/persons/female/person_f51.jpg' },
    { id: 'f52', name: 'Yvonne', image: '/static/persons/female/person_f52.jpg' },
    { id: 'f53', name: 'Zoe', image: '/static/persons/female/person_f53.jpg' },
    { id: 'f54', name: 'Antonia', image: '/static/persons/female/person_f54.jpg' },
    { id: 'f55', name: 'Beatrice', image: '/static/persons/female/person_f55.jpg' },
    { id: 'f56', name: 'Celina', image: '/static/persons/female/person_f56.jpg' },
    { id: 'f57', name: 'Denise', image: '/static/persons/female/person_f57.jpg' },
    { id: 'f58', name: 'Fabienne', image: '/static/persons/female/person_f58.jpg' },
    { id: 'f59', name: 'Gisela', image: '/static/persons/female/person_f59.jpg' },
    { id: 'f1', name: 'Anna', image: '/static/persons/female/person_f1.jpg' },
    { id: 'f2', name: 'Maria', image: '/static/persons/female/person_f2.jpg' },
    { id: 'f3', name: 'Julia', image: '/static/persons/female/person_f3.jpg' },
    { id: 'f4', name: 'Sophie', image: '/static/persons/female/person_f4.jpg' },
    { id: 'f5', name: 'Lisa', image: '/static/persons/female/person_f5.jpg' },
    { id: 'f6', name: 'Emma', image: '/static/persons/female/person_f6.jpg' },
    { id: 'f7', name: 'Nina', image: '/static/persons/female/person_f7.jpg' },
    { id: 'f8', name: 'Sarah', image: '/static/persons/female/person_f8.jpg' },
    { id: 'f9', name: 'Laura', image: '/static/persons/female/person_f9.jpg' },
    { id: 'f10', name: 'Mia', image: '/static/persons/female/person_f10.jpg' },
    { id: 'f11', name: 'Jana', image: '/static/persons/female/person_f11.jpg' },
    { id: 'f12', name: 'Lena', image: '/static/persons/female/person_f12.jpg' }
  ],
  male: [
    { id: 'm1', name: 'Max', image: '/static/persons/male/person_m1.jpg' },
    { id: 'm2', name: 'Tom', image: '/static/persons/male/person_m2.jpg' },
    { id: 'm3', name: 'Paul', image: '/static/persons/male/person_m3.jpg' },
    { id: 'm4', name: 'Leon', image: '/static/persons/male/person_m4.jpg' },
    { id: 'm5', name: 'Felix', image: '/static/persons/male/person_m5.jpg' },
    { id: 'm6', name: 'Lucas', image: '/static/persons/male/person_m6.jpg' },
    { id: 'm7', name: 'Tim', image: '/static/persons/male/person_m7.jpg' },
    { id: 'm8', name: 'Jan', image: '/static/persons/male/person_m8.jpg' },
    { id: 'm9', name: 'David', image: '/static/persons/male/person_m9.jpg' },
    { id: 'm10', name: 'Michael', image: '/static/persons/male/person_m10.jpg' },
    { id: 'm11', name: 'Alex', image: '/static/persons/male/person_m11.jpg' },
    { id: 'm12', name: 'Chris', image: '/static/persons/male/person_m12.jpg' }
  ]
};

/* ------------------------------------------------------------------ */
/* 2 — Hilfsfunktionen (Formatierung, Mock‑Daten)                      */
/* ------------------------------------------------------------------ */
window.cleanProductName = t =>
  (t || 'Fashion Item')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[|›»«‹]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 40);

/* Minimal‑Mock‑Datenbank – kannst du beliebig erweitern */
window.mockProductDatabase = {
  tops: {
    't-shirts': [
      { id:1,name:'Fashion Item',  image:'https://via.placeholder.com/300x400?text=T1' },
      { id:2,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=T2' }
    ],
    'shirts':   [
      { id:3,name:'Fashion Item',  image:'https://via.placeholder.com/300x400?text=S1' },
      { id:4,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=S2' }
    ],
    'sweaters': [
      { id:5,name:'Fashion Item',  image:'https://via.placeholder.com/300x400?text=SW1' },
      { id:6,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=SW2' }
    ],
    'jackets':  [
      { id:7,name:'Fashion Item',  image:'https://via.placeholder.com/300x400?text=J1' },
      { id:8,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=J2' }
    ]
  },
  bottoms: {
    'jeans': [
      { id:101,name:'Fashion Item',   image:'https://via.placeholder.com/300x400?text=JE1' },
      { id:102,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=JE2' }
    ],
    'trousers': [
      { id:103,name:'Fashion Item',   image:'https://via.placeholder.com/300x400?text=TR1' },
      { id:104,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=TR2' }
    ],
    'skirts'  : [
      { id:105,name:'Fashion Item',   image:'https://via.placeholder.com/300x400?text=SK1' },
      { id:106,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=SK2' }
    ],
    'shorts'  : [
      { id:107,name:'Fashion Item',   image:'https://via.placeholder.com/300x400?text=SH1' },
      { id:108,name:'Fashion Item',image:'https://via.placeholder.com/300x400?text=SH2' }
    ]
  }
};

window.getMockProducts = type => {
  const map = {
    't-shirts':'tops', 'shirts':'tops', 'sweaters':'tops', 'jackets':'tops',
    'jeans':'bottoms', 'trousers':'bottoms', 'skirts':'bottoms', 'shorts':'bottoms'
  };
  return (window.mockProductDatabase[map[type]] || {})[type] || [];
};

window.createMockSearchResults = (term, cat) =>
  (cat === 'tops'
      ? window.mockProductDatabase.tops['t-shirts']
      : window.mockProductDatabase.bottoms['jeans'])
    .map((p,i)=>({ ...p, id:`mock-${i}`, name:'Fashion Item' }));

/* ------------------------------------------------------------------ */
/* 3 — Amazon über Server-Proxy (Keine Google APIs)                  */
/* ------------------------------------------------------------------ */

// Amazon Suche über Server-Proxy
async function amazonServerSearch(keywords, category) {
  try {
    const isDesktop = window.matchMedia && window.matchMedia('(min-width: 1024px)').matches;
    const desiredTotal = isDesktop ? 36 : 12; // Desktop 36, Mobil 12

    // Der Server liefert bis zu 10 pro Seite; wir geben die Gesamtanzahl an
    const response = await fetch('/search/amazon', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        keywords: keywords,
        totalCount: desiredTotal
      })
    });

    if (!response.ok) {
      throw new Error(`Server Error: ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    console.log('Amazon Server-Suche erfolgreich:', data.length, 'Produkte');
    return data;

  } catch (error) {
    console.error('Amazon Server-Suche Fehler:', error);
    return null; // Signalisiert Fallback zu Mock-Daten
  }
}

// Hauptsuchfunktionen - nur Amazon, sonst Mock-Daten
async function googleImageSearch(query, category) {
  console.log('Amazon-Suche für:', query);

  // Amazon über Server versuchen
  const amazonResults = await amazonServerSearch(query, category);
  if (amazonResults && amazonResults.length > 0) {
    return amazonResults;
  }

  // Fallback zu Mock-Daten
  console.log('Fallback zu Mock-Daten für:', query);
  return window.getMockProducts(category.split('-')[1] || 't-shirts');
}

async function googleFreeText(term, category) {
  console.log('Amazon Freitext-Suche für:', term);

  // Amazon über Server versuchen
  const searchKeywords = term;
  const amazonResults = await amazonServerSearch(searchKeywords, category);
  if (amazonResults && amazonResults.length > 0) {
    return amazonResults;
  }

  // Fallback zu Mock-Daten
  console.log('Fallback zu Mock-Daten für Freitext:', term);
  return window.createMockSearchResults(term, category);
}

async function performDefaultSearch(category) {
  const defaultTerm = getGenderedDefaultSearchQueries()[category];
  console.log('Amazon Standard-Suche für:', category, '-', defaultTerm);

  // Amazon über Server versuchen
  const amazonResults = await amazonServerSearch(defaultTerm, category);
  if (amazonResults && amazonResults.length > 0) {
    return amazonResults;
  }

  // Fallback zu Mock-Daten
  console.log('Fallback zu Mock-Daten für Standard-Suche:', category);
  return window.mockSearchResults[category] || [];
}

/* ------------------------------------------------------------------ */
/* 4 — Bild als File über Proxy laden (für echte Upload‑Inputs)        */
/* ------------------------------------------------------------------ */
async function fetchImageAsFile(url, filename='image.jpg') {
  const proxied = `https://images.weserv.nl/?url=${encodeURIComponent(url)}`;
  const resp    = await fetch(proxied);
  if (!resp.ok) throw new Error('Bild konnte nicht geladen werden');
  const blob    = await resp.blob();
  return new File([blob], filename, { type: blob.type || 'image/jpeg' });
}

/* ------------------------------------------------------------------ */
/* 5 — Modal für Vollbildanzeige (erweitert für alle Kategorien)       */
/* ------------------------------------------------------------------ */
let currentModalProduct = null;
let currentModalCategory = null;

function showImageModal(imageSrc, product = null, category = null) {
  const modal = document.getElementById('imageModal');
  const modalImg = document.getElementById('modalImage');
  const modalSelectBtn = document.getElementById('modalSelectBtn');

  if (modal && modalImg) {
    modalImg.src = imageSrc;
    modal.style.display = 'block';
    currentModalProduct = product;
    currentModalCategory = category;

    // Select-Button für alle Kategorien anzeigen, wenn ein Produkt vorhanden ist
    if (modalSelectBtn) {
      modalSelectBtn.style.display = product ? 'flex' : 'none';

      // Button-Text je nach Kategorie anpassen
      const buttonText = modalSelectBtn.querySelector('svg').nextSibling;
      if (buttonText) {
        switch(category) {
          case 'persons':
            modalSelectBtn.title = 'Select person';
            break;
          case 'tops':
            modalSelectBtn.title = 'Select top';
            break;
          case 'bottoms':
            modalSelectBtn.title = 'Select bottom';
            break;
          default:
            modalSelectBtn.title = 'Select';
        }
      }
    }
  } else {
    console.error('Modal elements not found');
  }
}

/* ------------------------------------------------------------------ */
/* 6 — Produkt übernehmen (Vorschau + Datei + Hidden‑URL)              */
/* ------------------------------------------------------------------ */
function selectProduct(product, category) {
  const inputName = category === 'tops' ? 'top' : (category === 'bottoms' ? 'bottom' : 'person');
  const wrapper   = document.querySelector(`.file-input-wrapper[data-input="${inputName}"]`);
  const fileInput = wrapper.querySelector('.file-input');

  /* — Vorschau sofort aktualisieren — */
  const img     = wrapper.querySelector('.preview-image');
  const label   = wrapper.querySelector('.file-name');
  const preview = wrapper.querySelector('.preview-container');
  img.src  = product.image;
  label.textContent = product.name;
  preview.classList.add('show');
  wrapper.classList.add('has-file');
  wrapper.querySelector('.upload-content').style.display = 'none';

  /* — Hidden‑URL setzen — */
  let hidden = wrapper.querySelector('input.url-input');
  if (!hidden) {
    hidden           = document.createElement('input');
    hidden.type      = 'hidden';
    hidden.className = 'url-input';
    hidden.name      = `${inputName}_url`;
    wrapper.appendChild(hidden);
  }
  hidden.value = product.image;

  /* — Amazon Produkt-Link als Hidden‑Input setzen (falls vorhanden) — */
  if (inputName === 'top' || inputName === 'bottom') {
    const fieldName = inputName === 'top' ? 'top_product_url' : 'bottom_product_url';
    let linkHidden = wrapper.querySelector(`input[name="${fieldName}"]`);
    if (!linkHidden) {
      linkHidden = document.createElement('input');
      linkHidden.type = 'hidden';
      linkHidden.name = fieldName;
      wrapper.appendChild(linkHidden);
    }
    linkHidden.value = product.detailUrl || product.detailURL || product.url || '';
  }

  /* — Datei für den echten Upload‑Input erzeugen (nur bei externen URLs) — */
  if (category !== 'persons') {
    (async ()=>{
      try {
        const safe = product.name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'') || 'bild';
        const file = await fetchImageAsFile(product.image, `${safe}.jpg`);
        const dt   = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
        fileInput.removeAttribute('required');     // Validierung deaktivieren
      } catch(err) {
        console.error(err);
        alert('Bild konnte nicht übernommen werden.');
      }
    })();
  } else {
    // For pre-made person images, simply disable validation
    fileInput.removeAttribute('required');
    // Geschlecht aus gewählter Person übernehmen und UI anpassen
    if (product && product.gender) {
      window.selectedGender = product.gender === 'male' ? 'male' : 'female';
      applyGenderToGalleries();
    }
  }

  // Nach jeder Auswahl prüfen, ob alle 3 Bilder vorhanden sind
  checkAndShowFinalPreview();
}

/* ------------------------------------------------------------------ */
/* 6b — Finale Vorschau aller 3 ausgewählten Bilder                    */
/* ------------------------------------------------------------------ */
function checkAndShowFinalPreview() {
  // Prüfen ob alle 3 Bilder ausgewählt wurden
  const personImg = document.querySelector('.file-input-wrapper[data-input="person"] .preview-image')?.src;
  const topImg = document.querySelector('.file-input-wrapper[data-input="top"] .preview-image')?.src;
  const bottomImg = document.querySelector('.file-input-wrapper[data-input="bottom"] .preview-image')?.src;

  // Nur anzeigen wenn alle 3 Bilder vorhanden sind
  if (personImg && topImg && bottomImg &&
      !personImg.includes('data:image/svg') &&
      !topImg.includes('data:image/svg') &&
      !bottomImg.includes('data:image/svg')) {

    // Step 3 ausblenden, da alle Bilder ausgewählt wurden
    const step3 = document.getElementById('step3');
    if (step3) {
      step3.style.display = 'none';
    }

    // Container für finale Vorschau finden oder erstellen
    let previewContainer = document.getElementById('final-preview-container');

    if (!previewContainer) {
      // Container direkt vor dem Submit-Button einfügen
      const submitButton = document.querySelector('button[type="submit"]');
      if (!submitButton) return;

      previewContainer = document.createElement('div');
      previewContainer.id = 'final-preview-container';
      previewContainer.className = 'final-preview-container';
      previewContainer.style.cssText = `
        margin: 0rem 0;
        padding: .3rem;
        background: #1c1c1e;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      `;

      previewContainer.innerHTML = `
        <h3 style="color: white; text-align: center; margin-bottom: 1rem; font-size: 1.2rem;">
          Your Outfit Selection
        </h3>
        <div class="final-preview-grid" style="
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1rem;
          max-width: 600px;
          margin: 0 auto;
        ">
          <div class="final-preview-item" style="
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
          ">
            <img src="${personImg}" alt="Person" style="
              width: 100%;
              height: 200px;
              object-fit: cover;
            ">
            <div style="padding: 0.5rem; text-align: center; font-size: 0.9rem; color: #4a5568;">
              Person
            </div>
          </div>
          <div class="final-preview-item" style="
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
          ">
            <img src="${topImg}" alt="Top" style="
              width: 100%;
              height: 200px;
              object-fit: cover;
            ">
            <div style="padding: 0.5rem; text-align: center; font-size: 0.9rem; color: #4a5568;">
              Top
            </div>
          </div>
          <div class="final-preview-item" style="
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
          ">
            <img src="${bottomImg}" alt="Bottom" style="
              width: 100%;
              height: 200px;
              object-fit: cover;
            ">
            <div style="padding: 0.5rem; text-align: center; font-size: 0.9rem; color: #4a5568;">
              Bottom
            </div>
          </div>
        </div>
      `;

      submitButton.parentNode.insertBefore(previewContainer, submitButton);
    } else {
      // Container existiert bereits, nur Bilder aktualisieren
      const images = previewContainer.querySelectorAll('.final-preview-item img');
      if (images[0]) images[0].src = personImg;
      if (images[1]) images[1].src = topImg;
      if (images[2]) images[2].src = bottomImg;
    }

    // Sanft zur Vorschau scrollen
    setTimeout(() => {
      previewContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 300);
  }
}

/* ------------------------------------------------------------------ */
/* 7 — Produkte laden & anzeigen (erweitert für Modal-Verhalten)       */
/* ------------------------------------------------------------------ */
async function loadProducts(category, type, grid) {
  console.log('loadProducts aufgerufen:', { category, type }); // Debug
  grid.innerHTML =
    '<div class="loading-spinner"><div class="spinner"></div><span>Loading...</span></div>';

  let items = [];

  if (category === 'persons') {
    console.log('Loading persons for type:', type); // Debug
    // Vorgefertigte Personen laden
    items = (window.personDatabase[type] || []).map(p => ({ ...p, gender: type }));
    console.log('Found persons:', items.length); // Debug
  } else if (type === 'search') {
    // Standard-Suche für den Suche-Tab durchführen
    items = await performDefaultSearch(category);
  } else {
    const genderedQueries = getGenderedSearchQueries();
    const query = genderedQueries[category]?.[type];
    items = query
        ? await googleImageSearch(query, `${category}-${type}`)
        : window.getMockProducts(type);
  }

  if (!items.length) {
    console.log('Keine Items gefunden für:', { category, type }); // Debug
    grid.innerHTML =
      '<div style="text-align:center;color:#718096;padding:2rem;">No products found</div>';
    return;
  }

  console.log('Rendere', items.length, 'Items'); // Debug
  grid.innerHTML = '';
  items.forEach(p=>{
    const div = document.createElement('div');
    div.className = 'product-item';

    if (category === 'persons') {
      // Spezielle Darstellung für Personen mit erweiterter Klickfläche
      div.innerHTML = `
        <img src="${p.image}" alt="${p.name}">
        <div class="person-overlay" data-action="zoom" title="Vergrößern">
          <svg data-lucide="zoom-in" width="32" height="32"></svg>
        </div>
        <div class="person-name">${p.name}</div>
      `;

      // Event-Handler direkt auf das Overlay setzen (ganze Fläche klickbar)
      const overlay = div.querySelector('.person-overlay');

      if (overlay) {
        overlay.onclick = (e) => {
          e.stopPropagation();
          console.log('Overlay geklickt für:', p.name); // Debug
          showImageModal(p.image, p, category);
        };
      }
    } else {
      // Erweiterte Darstellung für Kleidung mit Modal-Funktionalität
      div.innerHTML = `
        <img src="${p.thumbnail || p.image}" alt="${p.name}">
        <div class="product-overlay" title="Vergrößern">
          <svg data-lucide="zoom-in" width="14" height="14"></svg>
        </div>
        <div class="overlay">${p.name}</div>
      `;

      // Klick öffnet Modal statt direkte Auswahl
      div.onclick = (e) => {
        e.stopPropagation();
        console.log('Produkt geklickt für Modal:', p.name); // Debug
        showImageModal(p.image, p, category);
      };
    }

    grid.appendChild(div);
  });

  // Lucide Icons für die neuen Buttons initialisieren
  if (typeof lucide !== 'undefined' && lucide.createIcons) {
    lucide.createIcons();
  }
}

/* ---------------------------------------------------- */
/*  Hilfs-Funktion: zeigt oder versteckt Grund-Elemente  */
/* ---------------------------------------------------- */
function toggleInitialElems(section, hide=true){
  if(!section) return;
  section     // Datei-Upload, „ODER"-Text und Button
    .querySelectorAll('.file-input-wrapper, .product-gallery-toggle, p, .or-divider')
    .forEach(el=>{
      // Nur das „ODER"-P-Tag oder or-divider ausblenden, andere <p> ignorieren
      if(el.tagName==='P' && 
         !el.classList.contains('or-divider') &&
         el.textContent.trim().toUpperCase()!=='ODER') return;
      el.classList.toggle('hidden', hide);
    });
}

/* ------------------------------------------------------------- */
/* Genderspezifische Tabs dynamisch aufbauen                      */
/* ------------------------------------------------------------- */
function toLabel(typeKey) {
  if (!typeKey) return '';
  return typeKey
    .split('-')
    .map(s => s.charAt(0).toUpperCase() + s.slice(1))
    .join('-');
}

function bindTabsForGallery(gal) {
  gal.querySelectorAll('.gallery-tab').forEach(tab=>{
    tab.onclick = (e)=>{
      e.preventDefault();
      e.stopPropagation();
      tab.blur();
      gal.querySelectorAll('.gallery-tab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      const cat  = gal.dataset.category;
      const type = tab.dataset.type;
      const grid = gal.querySelector('.product-grid');
      const sc   = gal.querySelector('.search-container');
      if (sc) sc.style.display = type==='search' ? 'block' : 'none';
      loadProducts(cat, type, grid);
    };
  });
}

function applyGenderToGalleries() {
  const gender = window.selectedGender === 'male' ? 'male' : 'female';
  const allowedTabs = {
    female: {
      tops: ['jackets','shirts','dresses','sweaters'],
      bottoms: ['jeans','skirts','trousers','shorts']
    },
    male: {
      tops: ['t-shirts','shirts','sweaters','jackets'],
      bottoms: ['jeans','trousers','shorts']
    }
  };

  ['tops','bottoms'].forEach(cat => {
    const gal = document.querySelector(`.product-gallery[data-category="${cat}"]`);
    if (!gal) return;

    const tabsWrap = gal.querySelector('.gallery-tabs');
    if (!tabsWrap) return;

    // Tabs neu aufbauen: immer mit Search-Tab beginnen
    tabsWrap.innerHTML = '';

    const searchBtn = document.createElement('button');
    searchBtn.type = 'button';
    searchBtn.className = 'gallery-tab active';
    searchBtn.dataset.type = 'search';
    searchBtn.setAttribute('onclick', 'return false;');
    searchBtn.innerHTML = '<svg data-lucide="search"></svg> Search';
    tabsWrap.appendChild(searchBtn);

    const types = (allowedTabs[gender][cat] || []);
    types.forEach(typeKey => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'gallery-tab';
      btn.dataset.type = typeKey;
      btn.setAttribute('onclick', 'return false;');
      btn.textContent = toLabel(typeKey);
      tabsWrap.appendChild(btn);
    });

    // Suchfeld sichtbar halten, da "search" aktiv ist
    const sc = gal.querySelector('.search-container');
    if (sc) sc.style.display = 'block';

    // Event-Handler für neue Tabs setzen
    bindTabsForGallery(gal);

    // Produkte für aktiven Tab laden
    const grid = gal.querySelector('.product-grid');
    gal.dataset.loaded = '';
    loadProducts(cat, 'search', grid);

    // Lucide Icons für neue Buttons
    if (typeof lucide !== 'undefined' && lucide.createIcons) {
      lucide.createIcons();
    }
  });
}

/* ------------------------------------------------------------------ */
/* 8 — Dom Ready: Galerien, Tabs, Suche, Upload‑Inputs                */
/* ------------------------------------------------------------------ */
document.addEventListener('DOMContentLoaded', ()=>{

  /* Modal schließen - mit Fehlerbehandlung */
  const modalClose = document.querySelector('.modal-close');
  const imageModal = document.getElementById('imageModal');
  const modalSelectBtn = document.getElementById('modalSelectBtn');

  if (modalClose && imageModal) {
    modalClose.onclick = () => {
      imageModal.style.display = 'none';
      currentModalProduct = null;
      currentModalCategory = null;
    };

    imageModal.onclick = (e) => {
      if (e.target.id === 'imageModal') {
        imageModal.style.display = 'none';
        currentModalProduct = null;
        currentModalCategory = null;
      }
    };
  }

  // Modal-Select-Button Event-Handler (erweitert für alle Kategorien)
  if (modalSelectBtn) {
    modalSelectBtn.onclick = (e) => {
      e.stopPropagation();
      if (currentModalProduct && currentModalCategory) {
        console.log('Modal-Select-Button geklickt für:', currentModalProduct.name, 'Kategorie:', currentModalCategory);
        selectProduct(currentModalProduct, currentModalCategory);
        imageModal.style.display = 'none';

        // Entsprechende Galerie schließen
        const gallery = document.querySelector(`.product-gallery[data-category="${currentModalCategory}"]`);
        if (gallery) {
          gallery.classList.remove('show');
        }

        currentModalProduct = null;
        currentModalCategory = null;
      }
    };
  }

  /* Datei‑Inputs – Preview + Remove */
  document.querySelectorAll('.file-input-wrapper').forEach(w=>{
    const input   = w.querySelector('.file-input');
    const preview = w.querySelector('.preview-container');
    const img     = preview.querySelector('.preview-image');
    const label   = preview.querySelector('.file-name');
    const uploadC = w.querySelector('.upload-content');

    const removeBtn = w.querySelector('.remove-file');
    if (removeBtn) {
      removeBtn.onclick = e=>{
        e.stopPropagation();
        input.value='';
        preview.classList.remove('show');
        uploadC.style.display='flex';
        w.classList.remove('has-file');
        img.src=''; label.textContent='';
        const hid=w.querySelector('.url-input'); if (hid) hid.remove();
        input.setAttribute('required','required');
        // Finale Vorschau entfernen wenn ein Bild gelöscht wird
        const finalPreview = document.getElementById('final-preview-container');
        if (finalPreview) finalPreview.remove();
        // Step 3 wieder einblenden, falls es ausgeblendet war
        const step3 = document.getElementById('step3');
        if (step3) step3.style.display = 'block';
      };
    }

    input.onchange = e=>{
      const f=e.target.files[0]; if(!f||!f.type.startsWith('image/'))return;
      const fr=new FileReader();
      fr.onload=ev=>{
        img.src=ev.target.result; label.textContent=f.name;
        preview.classList.add('show'); uploadC.style.display='none'; w.classList.add('has-file');
        // Nach Upload auch finale Vorschau prüfen
        checkAndShowFinalPreview();
      };
      fr.readAsDataURL(f);
    };
  });

/* Galerie‑Schalter */
document.querySelectorAll('.product-gallery-toggle').forEach(btn=>{
  btn.onclick = ()=>{
    console.log('Galerie-Button geklickt:', btn.dataset.category); // Debug
    const cat = btn.dataset.category;
    const gal = document.querySelector(`.product-gallery[data-category="${cat}"]`);

    if (!gal) {
      console.error('Galerie nicht gefunden für Kategorie:', cat);
      return;
    }

    document.querySelectorAll('.product-gallery').forEach(g=>g!==gal&&g.classList.remove('show'));
    gal.classList.toggle('show');
    // <<< NEU >>>
    toggleInitialElems(btn.closest('.upload-section'),
                       gal.classList.contains('show'));

// Scroll-Funktionalität hinzufügen
if (gal.classList.contains('show')) {
  setTimeout(() => {
    // Zur Galerie scrollen und dann noch etwas weiter nach unten
    gal.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
      inline: 'nearest'
    });

    // Zusätzlich nach unten scrollen, um mehr von der Galerie zu zeigen
    setTimeout(() => {
      window.scrollBy({
        top: 150,
        behavior: 'smooth'
      });
    }, 200);
  }, 100);
}

    if (!gal.dataset.loaded) {
      const first = gal.querySelector('.gallery-tab.active');
      if (first) {
        console.log('Lade Produkte für:', cat, first.dataset.type); // Debug
        loadProducts(cat, first.dataset.type, gal.querySelector('.product-grid'));
        gal.dataset.loaded = 'true';
      }
    }
  };
});

  /* Tabs */
  document.querySelectorAll('.gallery-tab').forEach(tab=>{
    tab.onclick = (e)=>{
      e.preventDefault();
      e.stopPropagation();
      tab.blur();
      const gal = tab.closest('.product-gallery');
      gal.querySelectorAll('.gallery-tab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      const cat  = gal.dataset.category;
      const type = tab.dataset.type;
      const grid = gal.querySelector('.product-grid');
      const sc   = gal.querySelector('.search-container');
      if (sc) sc.style.display = type==='search' ? 'block' : 'none';
      loadProducts(cat, type, grid);
    };
  });

  /* Freitext‑Suche */
  document.querySelectorAll('.search-button').forEach(btn=>{
    btn.onclick = async ()=>{
      const gal  = btn.closest('.product-gallery');
      const term = gal.querySelector('.search-input').value.trim();
      if (!term) { alert('Suchbegriff eingeben'); return; }
      const cat  = gal.dataset.category;
      const grid = gal.querySelector('.product-grid');
      grid.innerHTML =
        '<div class="loading-spinner"><div class="spinner"></div><span>Searching...</span></div>';
      const res = await googleFreeText(term, cat);
      grid.innerHTML='';
      res.forEach(p=>{
        const div=document.createElement('div');
        div.className='product-item';
        div.innerHTML=`
          <img src="${p.thumbnail || p.image}" alt="${p.name}">
          <div class="product-overlay" title="Vergrößern">
            <svg data-lucide="zoom-in" width="14" height="14"></svg>
          </div>
          <div class="overlay">${p.name}</div>
        `;
        // Auch hier Modal-Verhalten für Suchergebnisse
        div.onclick=(e)=>{
          e.stopPropagation();
          showImageModal(p.image, p, cat);
        };
        grid.appendChild(div);
      });
      // Icons für neue Elemente initialisieren
      if (typeof lucide !== 'undefined' && lucide.createIcons) {
        lucide.createIcons();
      }
    };
  });
document.querySelectorAll('.search-input').forEach(inp => {
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();                       // Seite nicht neu laden
      const btn = inp.closest('.search-container')
                      .querySelector('.search-button');
      if (btn) btn.click();                     // vorhandenen Click-Handler nutzen
    }
  });
});

  /* Galerie schließen */
  document.querySelectorAll('.gallery-close').forEach(btn=>{
    btn.onclick = ()=>{
      const gal     = btn.closest('.product-gallery');
      gal.classList.remove('show');
      // <<< NEU >>>
      toggleInitialElems(gal.closest('.upload-section'), false);
    };
  });

});

/* ------------------------------------------------------------------ */
/* 9 — Debug & Test-Funktionen                                       */
/* ------------------------------------------------------------------ */

// Debug-Funktion für Amazon API-Tests
window.testAmazonAPI = async function(searchTerm = 'Damen Bluse') {
  console.log('Teste Amazon Server-API mit:', searchTerm);
  try {
    const results = await amazonServerSearch(searchTerm, 'tops-shirts');
    console.log('Amazon Server API Ergebnisse:', results);
    return results;
  } catch (error) {
    console.error('Amazon Server API Test fehlgeschlagen:', error);
    return null;
  }
};

console.log('Amazon-Only Fashion Search geladen (Kein Google).');
console.log('- Nur Amazon PA-API über Server-Proxy');
console.log('- Mock-Daten als Fallback bei Amazon-Fehlern');
console.log('- Verwende window.testAmazonAPI() zum Testen');
console.log('- Alle DOM-Handler sind vollständig implementiert');