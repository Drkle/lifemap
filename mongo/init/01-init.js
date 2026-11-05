// Inicialización de la base LifeMap. Solo corre al crear el volumen por primera vez.
// Crea las colecciones de negocios con un validador GeoJSON y los índices 2dsphere.
const dbName = process.env.MONGO_DB || "lifemap";
const lm = db.getSiblingDB(dbName);

// location debe ser un Point GeoJSON con [longitud, latitud] en rango.
const validadorPunto = {
  $jsonSchema: {
    bsonType: "object",
    required: ["location"],
    properties: {
      location: {
        bsonType: "object",
        required: ["type", "coordinates"],
        properties: {
          type: { enum: ["Point"] },
          coordinates: {
            bsonType: "array",
            minItems: 2,
            maxItems: 2,
            items: [
              { bsonType: "number", minimum: -180, maximum: 180 },  // longitud
              { bsonType: "number", minimum: -90, maximum: 90 }     // latitud
            ]
          }
        }
      }
    }
  }
};

for (const nombre of ["negocios", "negocios_semilla"]) {
  if (!lm.getCollectionNames().includes(nombre)) {
    try {
      lm.createCollection(nombre, { validator: validadorPunto, validationLevel: "strict" });
    } catch (e) {
      print(`[init] AVISO: validador no aplicado a ${nombre}: ${e.message}`);
      lm.createCollection(nombre);
    }
  }
  lm[nombre].createIndex({ location: "2dsphere" }, { name: "location_2dsphere" });
  lm[nombre].createIndex({ categoria_principal: 1 }, { name: "categoria_principal_1" });
  lm[nombre].createIndex({ geohash: 1 }, { name: "geohash_1" });
}

for (const nombre of ["resenas", "resenas_semilla"]) {
  lm[nombre].createIndex({ business_id: 1 }, { name: "business_id_1" });
  lm[nombre].createIndex({ fecha: 1 }, { name: "fecha_1" });
  lm[nombre].createIndex({ geohash: 1 }, { name: "geohash_1" });
}

print(`[init] Base '${dbName}' lista: validador GeoJSON e índices 2dsphere.`);
