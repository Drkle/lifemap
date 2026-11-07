section LifeMap;
shared BaseUrl = "https://aviation-decrease-hunger.ngrok-free.dev";
shared Latitud = "27.95";
shared Longitud = "-82.45";
shared Radio = "5000";
shared Categoria = "Pizza";
shared Consultar = (Ruta as text) as table =>
    let
        Respuesta = Json.Document(Web.Contents(BaseUrl, [RelativePath=Ruta,
            Query=[lat=Latitud, lon=Longitud, radio=Radio, limit="1000"],
            Headers=[#"ngrok-skip-browser-warning"="true"]])),
        Filas = Respuesta[resultados],
        Tabla = if List.IsEmpty(Filas) then #table({}, {}) else Table.FromRecords(Filas)
    in Tabla;
shared Coordenadas = (Tabla as table, Campo as text) as table =>
    if Table.IsEmpty(Tabla) then Tabla else
    let
        Lon = Table.AddColumn(Tabla, "longitud", each Record.Field(_, Campo)[coordinates]{0}, type number),
        Lat = Table.AddColumn(Lon, "latitud", each Record.Field(_, Campo)[coordinates]{1}, type number)
    in Lat;
shared Hotspots = Coordenadas(Consultar("live/hotspots"), "centro");
shared Alertas = Coordenadas(Consultar("alerts"), "location");
shared Ventanas = Consultar("live/windows");
shared Riesgo = Coordenadas(Consultar("risk/near"), "location");
shared Supervivencia =
    let
        Datos=Json.Document(Web.Contents(BaseUrl, [RelativePath="survival/" & Uri.EscapeDataString(Categoria),
            Headers=[#"ngrok-skip-browser-warning"="true"]])),
        Filas=Datos[curva]
    in if List.IsEmpty(Filas) then #table({"dias", "supervivencia", "en_riesgo", "cierres", "censuras"}, {}) else Table.FromRecords(Filas);
