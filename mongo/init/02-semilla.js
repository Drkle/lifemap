// Semilla determinista para las pruebas de Jenkins (staging y verificación de Spark).
// Nunca se mezcla con los datos reales: vive en negocios_semilla y resenas_semilla.
//
// 100 negocios en una grilla de 10 x 10 (paso 0,001°) alrededor de (27.9505, -82.4575),
// todos a menos de 1 km del centro. Valores esperados (ver scripts/smoke_api.sh):
//   - 50 "Pizza" (i par) y 50 "Mexican" (i impar)
//   - cerrados: i % 5 == 0, o i par con i % 5 == 1  ->  30 cierres (Pizza 20, Mexican 10)
//   - dias_negocio = 365 * (1 + i % 5)  ->  109.500 días-negocio (300 años-negocio)
//   - tasa total = 30 / 300 * 100 = 10 %;  Pizza 13,333 %;  Mexican 6,667 %
//   - 4 reseñas por negocio: Pizza 2 negativas (50 %), Mexican 1 negativa (25 %)
//   - pct_negativas medio = 37,5 %;  sentimiento_medio medio = 0,25
const dbName = process.env.MONGO_DB || "lifemap";
const lm = db.getSiblingDB(dbName);

const BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz";
function geohash(lat, lon, precision) {
  let latR = [-90, 90], lonR = [-180, 180], par = true, bits = 0, valor = 0, out = "";
  while (out.length < precision) {
    const r = par ? lonR : latR, c = par ? lon : lat, m = (r[0] + r[1]) / 2;
    if (c >= m) { valor = (valor << 1) | 1; r[0] = m; } else { valor = valor << 1; r[1] = m; }
    par = !par;
    if (++bits === 5) { out += BASE32[valor]; bits = 0; valor = 0; }
  }
  return out;
}

const TEXTOS = {
  5: "Amazing food, friendly staff and great prices. We will definitely come back!",
  4: "Good tacos and pizza, nice place, service was quick.",
  2: "Bad experience, the food was cold and the waiter was rude.",
  1: "Terrible service, dirty tables and awful food. Never again."
};
const ETIQUETA = (e) => (e <= 2 ? 0 : e === 3 ? 1 : 2);
const NOMBRE = ["negativo", "neutral", "positivo"];
const corte = new Date("2022-01-19T00:00:00Z");
const DIA = 24 * 3600 * 1000;

if (lm.negocios_semilla.countDocuments({}) === 0) {
  const negocios = [], resenas = [];
  for (let i = 0; i < 100; i++) {
    const lon = -82.4620 + (i % 10) * 0.001;
    const lat = 27.9460 + Math.floor(i / 10) * 0.001;
    const cat = i % 2 === 0 ? "Pizza" : "Mexican";
    const cerrado = i % 5 === 0 || (i % 2 === 0 && i % 5 === 1);
    const dias = 365 * (1 + (i % 5));
    const primera = new Date(Date.UTC(2015, 0, 1));
    const ultima = new Date(primera.getTime() + (dias - 1) * DIA);
    const gh = geohash(lat, lon, 6);
    const estrellas = [5, 4, 2, i % 2 === 0 ? 1 : 5];
    const negativas = estrellas.filter((e) => e <= 2).length;
    const puntaje = estrellas.reduce((s, e) => s + ETIQUETA(e) - 1, 0);
    negocios.push({
      _id: `semilla_${i}`, nombre: `Negocio semilla ${i}`, ciudad: "Tampa", estado: "FL",
      location: { type: "Point", coordinates: [lon, lat] }, geohash: gh,
      estrellas: 3.5, review_count_yelp: 4, is_open: cerrado ? 0 : 1,
      categorias: ["Restaurants", cat], categoria_principal: cat,
      primera_resena: primera, ultima_resena: ultima, n_resenas: 4, dias_negocio: dias,
      evento: cerrado ? 1 : 0, censurado: !cerrado,
      dias_hasta_corte: Math.round((corte - primera) / DIA) + 1, fecha_corte: corte,
      negativas: negativas, pct_negativas: (negativas / 4) * 100, sentimiento_medio: puntaje / 4
    });
    estrellas.forEach((e, k) => {
      const et = ETIQUETA(e);
      resenas.push({
        _id: `semilla_${i}_${k}`, business_id: `semilla_${i}`, estrellas: e, texto: TEXTOS[e],
        fecha: new Date(primera.getTime() + Math.floor(((dias - 1) * k) / 3) * DIA),
        etiqueta: et, sentimiento: NOMBRE[et], negativa: et === 0 ? 1 : 0,
        geohash: gh, categoria_principal: cat, ciudad: "Tampa"
      });
    });
  }
  lm.negocios_semilla.insertMany(negocios);
  lm.resenas_semilla.insertMany(resenas);
}
print(`[semilla] negocios_semilla=${lm.negocios_semilla.countDocuments({})} resenas_semilla=${lm.resenas_semilla.countDocuments({})}`);
