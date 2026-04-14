import { useState, useRef, useEffect, useMemo } from "react";

// Gesorteerd op populariteit (meest voorkomend eerst)
const ALLERGENS = [
  { id: "gluten",       label: "Gluten",       emoji: "🌾" },
  { id: "lactose",      label: "Lactose",      emoji: "🥛" },
  { id: "noten",        label: "Noten",        emoji: "🥜" },
  { id: "ei",           label: "Ei",           emoji: "🥚" },
  { id: "soja",         label: "Soja",         emoji: "🫘" },
  { id: "schaaldieren", label: "Schaaldieren", emoji: "🦐" },
  { id: "vis",          label: "Vis",          emoji: "🐟" },
  { id: "sesam",        label: "Sesam",        emoji: "🫚" },
  { id: "mosterd",      label: "Mosterd",      emoji: "🟡" },
  { id: "selderij",     label: "Selderij",     emoji: "🌿" },
  { id: "weekdieren",   label: "Weekdieren",   emoji: "🦑" },
  { id: "paprika",      label: "Paprika",      emoji: "🫑" },
  { id: "ui",           label: "Ui",           emoji: "🧅" },
  { id: "knoflook",     label: "Knoflook",     emoji: "🧄" },
  { id: "lupine",       label: "Lupine",       emoji: "🌸" },
  { id: "sulfiet",      label: "Sulfiet",      emoji: "🍷" },
];

const DIETS = [
  { id: "vegetarisch", label: "Vegetarisch", emoji: "🥦" },
  { id: "vegan",       label: "Vegan",       emoji: "🌱" },
  { id: "halal",       label: "Halal",       emoji: "☪️" },
  { id: "keto",        label: "Keto",        emoji: "🥑" },
  { id: "suikervrij",  label: "Suikervrij",  emoji: "🚫🍬" },
  { id: "fodmap",      label: "FODMAP",      emoji: "🍎" },
  { id: "paleo",       label: "Paleo",       emoji: "🦴" },
  { id: "koosjer",     label: "Koosjer",     emoji: "✡️" },
  { id: "whole30",     label: "Whole30",     emoji: "🥩" },
];

const MOBILE_ALLERGEN_LIMIT = 8;
const MOBILE_DIET_LIMIT = 7;

const API_BASE = "https://api.swapchef.nl";

export default function RecipeAnalyzer() {
  const isPWA = useMemo(() =>
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true,
  []);

  const [url, setUrl]                   = useState("");
  const [selected, setSelected]         = useState([]);
  const [selectedDiets, setSelectedDiets] = useState([]);
  const [loading, setLoading]           = useState(false);
  const [result, setResult]             = useState(null);
  const [error, setError]               = useState(null);
  const [activeModal, setActiveModal]   = useState(null);
  const [showAllAllergens, setShowAllAllergens] = useState(false);
  const [showAllDiets, setShowAllDiets]         = useState(false);
  const [showInfo, setShowInfo]                 = useState(false);
  const [dragY, setDragY]                       = useState(0);
  const [isDragging, setIsDragging]             = useState(false);
  const [infoSlide, setInfoSlide]               = useState("main");
  const dragStartY = useRef(0);
  const resultsRef = useRef(null);

  function handleDragStart(e) {
    dragStartY.current = e.touches[0].clientY;
    setIsDragging(true);
  }

  function handleDragMove(e) {
    const delta = e.touches[0].clientY - dragStartY.current;
    if (delta > 0) setDragY(delta);
  }

  function handleDragEnd() {
    setIsDragging(false);
    if (dragY > 100) {
      setShowInfo(false);
    }
    setDragY(0);
  }

  useEffect(() => {
    if (result && resultsRef.current) {
      const top = resultsRef.current.getBoundingClientRect().top + window.scrollY - 24;
      window.scrollTo({ top, behavior: "smooth" });
    }
  }, [result]);

  useEffect(() => {
    if (!showInfo) {
      const t = setTimeout(() => setInfoSlide("main"), 300);
      return () => clearTimeout(t);
    }
  }, [showInfo]);

  function toggleAllergen(id) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  }

  function toggleDiet(id) {
    setSelectedDiets((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!url.trim()) return;
    if (selected.length === 0 && selectedDiets.length === 0) {
      setError("Selecteer minimaal één allergie of dieet.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, user_allergies: selected, user_diets: selectedDiets }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail ?? "Er ging iets mis.");
      }

      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const safeIngredients   = result?.ingredients.filter((i) => !i.is_unsafe)  ?? [];
  const unsafeIngredients = result?.ingredients.filter((i) => i.is_unsafe)   ?? [];

  return (
    <div className="min-h-screen relative bg-gray-100 sm:bg-transparent">

      {/* Background photo — alleen op desktop */}
      <img
        src="/swapchef-bg.png"
        alt=""
        aria-hidden="true"
        className="fixed inset-0 w-full h-full object-cover pointer-events-none -z-10 hidden sm:block"
      />

      {/* Bottom sheet — mobile/PWA only */}
      <div
        className={`fixed inset-0 z-50 sm:hidden transition-opacity duration-300
                    ${showInfo ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
        onClick={() => setShowInfo(false)}
      >
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div
          className={`absolute bottom-0 inset-x-0 rounded-t-3xl bg-white px-6 pt-4 pb-10
                      shadow-2xl
                      ${isDragging ? "" : "transition-transform duration-300 ease-out"}
                      ${showInfo ? "translate-y-0" : "translate-y-full"}`}
          style={{ transform: showInfo ? `translateY(${dragY}px)` : "translateY(100%)" }}
          onClick={(e) => e.stopPropagation()}
          onTouchStart={handleDragStart}
          onTouchMove={handleDragMove}
          onTouchEnd={handleDragEnd}
        >
          {/* Drag handle */}
          <div className="w-10 h-1 bg-gray-200 rounded-full mx-auto mb-5" />

          {/* Sliding panels */}
          <div className="overflow-hidden">
            <div
              className="flex transition-transform duration-300 ease-out"
              style={{
                transform: infoSlide === "main"
                  ? "translateX(0%)"
                  : infoSlide === "disclaimer"
                  ? "translateX(-100%)"
                  : "translateX(-200%)"
              }}
            >
              {/* Panel 1: hoofdpagina */}
              <div className="w-full shrink-0">
                <h2 className="text-lg font-bold text-gray-900 mb-2">Hoe werkt SwapChef?</h2>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Plak een recept-URL van een site zoals Allerhande of Leukerecepten,
                  kies jouw allergieën of dieetwensen en SwapChef analyseert automatisch
                  de ingrediënten. Onveilige ingrediënten krijgen een slim alternatief —
                  afgestemd op jouw situatie.
                </p>
                <hr className="my-5 border-gray-100" />
                <div className="flex items-center justify-between text-sm text-gray-500">
                  <span>© {new Date().getFullYear()} SwapChef</span>
                  <div className="flex gap-4">
                    <button
                      onClick={() => setInfoSlide("disclaimer")}
                      className="underline underline-offset-2 hover:text-gray-800 transition"
                    >
                      Disclaimer
                    </button>
                    <button
                      onClick={() => setInfoSlide("privacy")}
                      className="underline underline-offset-2 hover:text-gray-800 transition"
                    >
                      Privacy
                    </button>
                  </div>
                </div>
              </div>

              {/* Panel 2: disclaimer */}
              <div className="w-full shrink-0">
                <button
                  onClick={() => setInfoSlide("main")}
                  className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 transition mb-4"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  Terug
                </button>
                <div className="overflow-y-auto max-h-[55vh] pr-1">
                  <DisclaimerContent />
                </div>
              </div>

              {/* Panel 3: privacy */}
              <div className="w-full shrink-0">
                <button
                  onClick={() => setInfoSlide("main")}
                  className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 transition mb-4"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  Terug
                </button>
                <div className="overflow-y-auto max-h-[55vh] pr-1">
                  <PrivacyContent />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* App wrapper — roze achtergrond alleen op mobiel als blok, op desktop transparant links */}
      <div className="min-h-screen max-w-lg mx-auto sm:mx-0 sm:ml-[60px] sm:min-h-0 sm:max-w-[42rem] sm:mt-8 sm:rounded-3xl overflow-hidden"
           style={{ backgroundColor: "#fbeee9" }}>

        {/* Top navbar — logo links, ⓘ knop rechts (alleen mobiel) */}
        <div className="px-5 py-3 bg-white/80 backdrop-blur-sm shadow-sm flex items-center justify-between">
          <img src="/logo.png" alt="SwapChef" className="h-14 w-auto" />
          <button
            type="button"
            onClick={() => setShowInfo(true)}
            className="sm:hidden w-10 h-10 rounded-full flex items-center justify-center
                       text-gray-400 hover:text-gray-500 transition"
            aria-label="Informatie"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
          </button>
        </div>

      <div className="px-5 pb-10">

        {/* Greeting */}
        <div className="mb-8 mt-8">
          <h1 className="text-3xl font-bold text-gray-900">Hallo Chef! 👋</h1>
          <p className="mt-1 text-base text-gray-500">
            Klaar om je recepten allergievriendelijk of dieetvriendelijk te maken?
          </p>
        </div>

        {/* Form — geen card wrapper */}
        <form onSubmit={handleSubmit}>

          {/* URL input — pill met link-icoon */}
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-[#ff4423]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
            </span>
            <input
              type="url"
              required
              placeholder="plak hier je recept url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setResult(null); setError(null); }}
              className="w-full rounded-full bg-white pl-12 pr-10 py-4 text-base text-gray-700
                         placeholder-gray-400 shadow-sm focus:outline-none focus:ring-2
                         focus:ring-[#ff4423]/30 transition"
            />
            {url && (
              <button
                type="button"
                onClick={() => { setUrl(""); setResult(null); setError(null); }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400
                           hover:text-gray-600 transition"
                aria-label="URL wissen"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </button>
            )}
          </div>

          {/* Allergen multi-select */}
          <fieldset className="mt-6">
            <legend className="text-xl font-bold text-gray-800 mb-3">
              Allergieën
            </legend>
            <div className="flex flex-wrap gap-2">
              {ALLERGENS.map(({ id, label, emoji }, idx) => {
                const active = selected.includes(id);
                const hiddenOnMobile = !showAllAllergens && idx >= MOBILE_ALLERGEN_LIMIT;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleAllergen(id)}
                    style={active ? { backgroundColor: "#ff4423", borderColor: "#ff4423" } : {}}
                    className={`rounded-full border-2 px-4 py-2 text-base font-semibold
                                transition select-none
                                ${hiddenOnMobile ? "hidden sm:inline-flex" : "inline-flex"}
                                ${active
                                  ? "text-white shadow-md"
                                  : "border-[#f5ddd6] bg-white text-gray-600 hover:border-[#ff4423] hover:bg-orange-50"
                                }`}
                  >
                    <span style={{ marginRight: "5px" }}>{emoji}</span>{label}
                  </button>
                );
              })}
              {!showAllAllergens && (
                <button
                  type="button"
                  onClick={() => setShowAllAllergens(true)}
                  className="sm:hidden inline-flex items-center rounded-full border-2 border-dashed
                             border-[#f5ddd6] px-4 py-2
                             text-base font-semibold text-gray-500
                             hover:border-[#ff4423] hover:text-[#ff4423] transition select-none"
                >
                  +{ALLERGENS.length - MOBILE_ALLERGEN_LIMIT} meer
                </button>
              )}
            </div>
          </fieldset>

          {/* Diet multi-select */}
          <fieldset className="mt-6">
            <legend className="text-xl font-bold text-gray-800 mb-3">
              Dieet
            </legend>
            <div className="flex flex-wrap gap-2">
              {DIETS.map(({ id, label, emoji }, idx) => {
                const active = selectedDiets.includes(id);
                const hiddenOnMobile = !showAllDiets && idx >= MOBILE_DIET_LIMIT;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleDiet(id)}
                    style={active ? { backgroundColor: "#ff4423", borderColor: "#ff4423" } : {}}
                    className={`rounded-full border-2 px-4 py-2 text-base font-semibold
                                transition select-none
                                ${hiddenOnMobile ? "hidden sm:inline-flex" : "inline-flex"}
                                ${active
                                  ? "text-white shadow-md"
                                  : "border-[#f5ddd6] bg-white text-gray-600 hover:border-[#ff4423] hover:bg-orange-50"
                                }`}
                  >
                    <span style={{ marginRight: "5px" }}>{emoji}</span>{label}
                  </button>
                );
              })}
              {!showAllDiets && (
                <button
                  type="button"
                  onClick={() => setShowAllDiets(true)}
                  className="sm:hidden inline-flex items-center rounded-full border-2 border-dashed
                             border-[#f5ddd6] px-4 py-2
                             text-base font-semibold text-gray-500
                             hover:border-[#ff4423] hover:text-[#ff4423] transition select-none"
                >
                  +{DIETS.length - MOBILE_DIET_LIMIT} meer
                </button>
              )}
            </div>
          </fieldset>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{ backgroundColor: "#ff4423" }}
            onMouseEnter={e => e.currentTarget.style.backgroundColor = "#e03a1e"}
            onMouseLeave={e => e.currentTarget.style.backgroundColor = "#ff4423"}
            className="group mt-8 w-full rounded-full px-6 py-4 text-lg font-bold
                       text-white active:scale-95
                       disabled:cursor-not-allowed disabled:opacity-60 transition"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner /> Ingrediënten swappen…
              </span>
            ) : (
              <span className="relative block overflow-hidden">
                <span className="invisible block" aria-hidden="true">Swap ingrediënten</span>
                {/* Huidige tekst: elk woord schuift los omhoog */}
                <span className="absolute inset-0 flex items-center justify-center gap-2">
                  <span className="transition-transform duration-500 ease-in-out group-hover:-translate-y-full">
                    Swap
                  </span>
                  <span className="transition-transform duration-500 ease-in-out delay-75 group-hover:-translate-y-full">
                    ingrediënten
                  </span>
                </span>
                {/* Nieuwe tekst: elk woord schuift los van onder */}
                <span className="absolute inset-0 flex items-center justify-center gap-2">
                  <span className="transition-transform duration-500 ease-in-out translate-y-full delay-100 group-hover:translate-y-0">
                    Ingrediënten
                  </span>
                  <span className="transition-transform duration-500 ease-in-out translate-y-full delay-150 group-hover:translate-y-0">
                    swappen
                  </span>
                </span>
              </span>
            )}
          </button>
        </form>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4
                          text-base text-red-700">
            ⚠️ {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div ref={resultsRef} className="mt-6 rounded-3xl bg-white p-6 shadow-sm">

            {/* Recipe title + summary */}
            <h2 className="text-2xl font-bold text-gray-800 truncate">
              {result.recipe_title}
            </h2>
            <div className="mt-1 flex gap-4 text-base text-gray-500">
              <span>{result.total_ingredients} ingrediënten</span>
              {result.unsafe_count > 0 ? (
                <span className="font-medium text-red-600">
                  {result.unsafe_count} onveilig
                </span>
              ) : (
                <span className="font-medium text-green-600">Alles veilig ✓</span>
              )}
            </div>

            {/* Unsafe ingredients */}
            {unsafeIngredients.length > 0 && (
              <section className="mt-5">
                <h3 className="mb-3 text-base font-bold uppercase tracking-wide text-red-500">
                  Onveilige ingrediënten
                </h3>
                <ul className="space-y-2">
                  {unsafeIngredients.map((ing, i) => (
                    <li
                      key={i}
                      className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-red-800">{ing.original}</p>
                        <span className="shrink-0 text-xs font-semibold uppercase tracking-wide
                                         text-red-400">
                          {ing.issue_type === "dieet" ? "Dieet" : "Allergie"}: {ing.matched_allergen}
                        </span>
                      </div>
                      <div className="mt-2 rounded-xl bg-green-100 px-3 py-2 text-sm font-semibold text-green-800">
                        ✔ {ing.alternative}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Safe ingredients */}
            {safeIngredients.length > 0 && (
              <section className="mt-5">
                <h3 className="mb-3 text-base font-bold uppercase tracking-wide text-green-600">
                  Veilige ingrediënten
                </h3>
                <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  {safeIngredients.map((ing, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 rounded-xl border border-green-100
                                 bg-green-50 px-3 py-2 text-base text-green-900"
                    >
                      <span className="text-green-500">✓</span>
                      {ing.original}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        {/* Footer — desktop only */}
        <footer className="hidden sm:block mt-10 pb-6 text-center text-sm text-gray-400">
          <p>© {new Date().getFullYear()} SwapChef. Alle rechten voorbehouden.</p>
          <div className="mt-1 flex justify-center gap-4">
            <button
              onClick={() => setActiveModal("disclaimer")}
              className="underline underline-offset-2 hover:text-gray-600 transition"
            >
              Disclaimer
            </button>
            <button
              onClick={() => setActiveModal("privacy")}
              className="underline underline-offset-2 hover:text-gray-600 transition"
            >
              Privacybeleid
            </button>
          </div>
        </footer>
      </div>
      </div>

      {/* Modal */}
      {activeModal && (
        <Modal onClose={() => setActiveModal(null)}>
          {activeModal === "disclaimer" ? <DisclaimerContent /> : <PrivacyContent />}
        </Modal>
      )}
    </div>
  );
}

function Modal({ onClose, children }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-3xl
                   bg-white p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-5 top-5 text-gray-400 hover:text-gray-600 transition"
          aria-label="Sluiten"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        </button>
        {children}
      </div>
    </div>
  );
}

function DisclaimerContent() {
  return (
    <div className="prose prose-sm max-w-none text-gray-700">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Disclaimer</h2>
      <p>
        SwapChef is een informatief hulpmiddel dat ingrediënten analyseert op basis van publiek beschikbare receptinformatie. De resultaten zijn bedoeld als algemene indicatie en kunnen onvolledig of onjuist zijn.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Geen medisch advies</h3>
      <p>
        De informatie op SwapChef vormt geen medisch of dieetkundig advies. Personen met (ernstige) allergieën of medische aandoeningen dienen altijd een arts, diëtist of allergoloog te raadplegen voordat zij op basis van deze tool voedselkeuzes maken.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Aansprakelijkheid</h3>
      <p>
        SwapChef aanvaardt geen aansprakelijkheid voor schade — direct of indirect — die voortvloeit uit het gebruik van de informatie op dit platform. Controleer altijd zelf de etiketten van producten op allergenen.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Externe websites</h3>
      <p>
        SwapChef analyseert recepten van externe websites. Wij zijn niet verantwoordelijk voor de inhoud, nauwkeurigheid of beschikbaarheid van deze externe bronnen.
      </p>
    </div>
  );
}

function PrivacyContent() {
  return (
    <div className="prose prose-sm max-w-none text-gray-700">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Privacybeleid</h2>
      <p>
        SwapChef hecht veel waarde aan de bescherming van uw persoonsgegevens. In dit privacybeleid informeren wij u over hoe wij omgaan met gegevens die via ons platform worden verwerkt.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Welke gegevens verwerken wij?</h3>
      <p>
        SwapChef verwerkt geen persoonsgegevens. Wij slaan geen gebruikersinformatie, IP-adressen of sessiedata op. De ingevoerde recept-URL en geselecteerde allergieën/dieetvoorkeuren worden uitsluitend gebruikt voor de analyse en worden niet opgeslagen.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Cookies</h3>
      <p>
        SwapChef maakt geen gebruik van tracking-cookies of analytische cookies van derden. Er worden uitsluitend functioneel noodzakelijke cookies gebruikt voor de werking van de applicatie.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Externe diensten</h3>
      <p>
        De backend van SwapChef draait op Render.com. Raadpleeg het privacybeleid van Render voor informatie over hoe zij gegevens verwerken.
      </p>
      <h3 className="font-semibold text-gray-800 mt-4 mb-2">Contact</h3>
      <p>
        Heeft u vragen over dit privacybeleid? Neem dan contact op via{" "}
        <a href="mailto:info@swapchef.nl" className="text-orange-500 underline">
          info@swapchef.nl
        </a>.
      </p>
      <p className="mt-4 text-xs text-gray-400">Laatst bijgewerkt: maart 2026</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" strokeWidth="4" />
      <path
        className="opacity-75"
        d="M4 12a8 8 0 018-8"
        strokeLinecap="round"
      />
    </svg>
  );
}
