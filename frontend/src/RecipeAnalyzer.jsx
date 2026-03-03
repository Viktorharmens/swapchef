import { useState } from "react";

const ALLERGENS = [
  { id: "lactose",      label: "Lactose",      emoji: "🥛" },
  { id: "gluten",       label: "Gluten",        emoji: "🌾" },
  { id: "noten",        label: "Noten",         emoji: "🥜" },
  { id: "ei",           label: "Ei",            emoji: "🥚" },
  { id: "soja",         label: "Soja",          emoji: "🫘" },
  { id: "schaaldieren", label: "Schaaldieren",  emoji: "🦐" },
  { id: "vis",          label: "Vis",           emoji: "🐟" },
  { id: "weekdieren",   label: "Weekdieren",    emoji: "🦑" },
  { id: "sesam",        label: "Sesam",         emoji: "🫚" },
  { id: "mosterd",      label: "Mosterd",       emoji: "🟡" },
  { id: "selderij",     label: "Selderij",      emoji: "🌿" },
  { id: "lupine",       label: "Lupine",        emoji: "🌸" },
  { id: "sulfiet",      label: "Sulfiet",       emoji: "🍷" },
  { id: "paprika",      label: "Paprika",       emoji: "🫑" },
  { id: "ui",           label: "Ui",            emoji: "🧅" },
  { id: "knoflook",     label: "Knoflook",      emoji: "🧄" },
];

const DIETS = [
  { id: "vegetarisch", label: "Vegetarisch", emoji: "🥦" },
  { id: "vegan",       label: "Vegan",       emoji: "🌱" },
  { id: "keto",        label: "Keto",        emoji: "🥑" },
  { id: "halal",       label: "Halal",       emoji: "☪️" },
  { id: "koosjer",     label: "Koosjer",     emoji: "✡️" },
  { id: "paleo",       label: "Paleo",       emoji: "🦴" },
  { id: "whole30",     label: "Whole30",     emoji: "🥩" },
  { id: "fodmap",      label: "FODMAP",      emoji: "🍎" },
  { id: "suikervrij",  label: "Suikervrij",  emoji: "🚫🍬" },
];

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export default function RecipeAnalyzer() {
  const [url, setUrl]                   = useState("");
  const [selected, setSelected]         = useState([]);
  const [selectedDiets, setSelectedDiets] = useState([]);
  const [loading, setLoading]           = useState(false);
  const [result, setResult]             = useState(null);
  const [error, setError]               = useState(null);

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
    <div className="min-h-screen px-4 py-10 relative overflow-hidden">

      {/* Background photo */}
      <img
        src="/kitchen.jpg"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-cover pointer-events-none"
      />
      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-black/40 pointer-events-none" />

      <div className="max-w-2xl relative" style={{ marginLeft: "50px" }}>

        {/* Form card */}
        <form
          onSubmit={handleSubmit}
          className="rounded-3xl bg-white/60 backdrop-blur-md border border-white/40 p-8 shadow-2xl"
        >
          {/* Header inside card */}
          <div className="mb-6 text-center">
            <img src="/logo.png" alt="SwapChef" className="mx-auto h-32 w-auto" />
            <p className="mt-2 text-base text-gray-500 font-medium">
              De slimme assistent voor elk dieet of allergie.
            </p>
          </div>

          {/* URL input */}
          <label className="block text-base font-bold text-gray-800 mb-2">
            Recept-URL
          </label>
          <div className="relative">
            <input
              type="url"
              required
              placeholder="https://www.allerhande.nl/recept/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-xl border border-gray-200 px-4 py-3 pr-10 text-base
                         focus:border-orange-400 focus:outline-none focus:ring-2
                         focus:ring-orange-100 transition"
            />
            {url && (
              <button
                type="button"
                onClick={() => setUrl("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400
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
            <legend className="text-base font-bold text-gray-800 mb-3">
              Mijn allergieën
            </legend>
            <div className="flex flex-wrap gap-2">
              {ALLERGENS.map(({ id, label, emoji }) => {
                const active = selected.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleAllergen(id)}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2
                                text-base font-medium transition select-none
                                ${active
                                  ? "border-orange-400 bg-orange-50 text-orange-700 shadow-sm"
                                  : "border-gray-200 bg-white text-gray-600 hover:border-orange-300 hover:bg-orange-50"
                                }`}
                  >
                    <span>{emoji}</span>
                    {label}
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Diet multi-select */}
          <fieldset className="mt-6">
            <legend className="text-base font-bold text-gray-800 mb-3">
              Mijn dieet
            </legend>
            <div className="flex flex-wrap gap-2">
              {DIETS.map(({ id, label, emoji }) => {
                const active = selectedDiets.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleDiet(id)}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2
                                text-base font-medium transition select-none
                                ${active
                                  ? "border-green-500 bg-green-50 text-green-700 shadow-sm"
                                  : "border-gray-200 bg-white text-gray-600 hover:border-green-400 hover:bg-green-50"
                                }`}
                  >
                    <span>{emoji}</span>
                    {label}
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="mt-8 w-full rounded-2xl bg-orange-500 px-6 py-4 text-lg font-bold
                       text-white hover:bg-orange-600 active:scale-95
                       disabled:cursor-not-allowed disabled:opacity-60 transition"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner /> Ingrediënten swappen…
              </span>
            ) : (
              "Swap ingrediënten"
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
          <div className="mt-6 rounded-3xl bg-white/60 backdrop-blur-md border border-white/40 p-8 shadow-2xl">

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
                      className="flex flex-col rounded-2xl border border-red-100
                                 bg-red-50 px-4 py-3 sm:flex-row sm:items-start sm:gap-4"
                    >
                      <div className="flex-1">
                        <p className="font-medium text-red-800">{ing.original}</p>
                        <p className="mt-0.5 text-base text-red-400 capitalize">
                          {ing.issue_type === "dieet" ? "Dieet" : "Allergie"}: {ing.matched_allergen}
                        </p>
                      </div>
                      <div className="mt-2 sm:mt-0 sm:text-right">
                        <span className="inline-block rounded-full bg-green-100 px-3 py-1
                                         text-base font-semibold text-green-800">
                          ✔ {ing.alternative}
                        </span>
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
      </div>
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
