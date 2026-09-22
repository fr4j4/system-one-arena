// RFC-style quoted fields, doubled quotes and multiline cells; no code evaluation.
export function importCSV(text: string) {
  const records: string[][] = [];
  let row: string[] = [],
    field = "",
    quoted = false;
  text = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') {
        field += '"';
        i++;
      } else quoted = !quoted;
    } else if (c === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((c === "\n" || c === "\r") && !quoted) {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      if (row.some(Boolean)) records.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (quoted) throw new Error("CSV inválido: comillas sin cerrar");
  row.push(field);
  if (row.some(Boolean)) records.push(row);
  const header = records.shift();
  if (!header || (!header.includes("text") && !header.includes("state")))
    throw new Error("CSV requiere columna text o state (JSON)");
  const parseValue = (v: string) => {
    try {
      return JSON.parse(v);
    } catch {
      return v;
    }
  };
  return records.map((values, index) => {
    if (values.length !== header.length)
      throw new Error(`CSV: columnas inconsistentes en fila ${index + 2}`);
    const data = Object.fromEntries(
      header.map((k, i) => [k.trim(), values[i]]),
    );
    const expected = data.expected ? JSON.parse(data.expected) : {};
    for (const key of header.filter((k) => k.startsWith("expected.")))
      if (data[key] !== "") expected[key.slice(9)] = parseValue(data[key]);
    return {
      id: data.id || `import-${index + 1}`,
      state: data.state ? JSON.parse(data.state) : { text: data.text },
      expected,
    };
  });
}
