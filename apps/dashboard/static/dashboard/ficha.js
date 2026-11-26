/* Fichas técnicas en PDF (generadas en el navegador con jsPDF).
 * La usan el tablero del panel y la página principal.
 *
 *   BrujulaFicha.vistaPrevia(datos)        ficha individual en la ventana de vista previa
 *   BrujulaFicha.descargar(datos)          descarga la ficha individual
 *   BrujulaFicha.vistaPreviaReporte(rep)   reporte de un grupo o del total
 *   BrujulaFicha.descargarReporte(rep)
 *
 * datos   = { result, evaluation, student, group, questionnaire, points: {V: 3, ...}, interpretation }
 * reporte = { alcance: "Total" | "Grupo: …" | "Alumno: …", filas: [datos, ...], incluirFichas: true }
 * Requiere vendor/jspdf.umd.min.js cargado antes.
 */
(() => {
  const labels = {
    V: "Visual", A: "Auditivo", R: "Lectura/Escritura", K: "Kinestésico",
    E: "Extroversión", I: "Introversión", S: "Sensación", N: "Intuición",
    T: "Pensamiento", F: "Sentimiento", J: "Juicio", P: "Percepción",
  };
  const VARK = ["V", "A", "R", "K"];
  const varkColors = { V: "#63a881", A: "#d6a461", R: "#8c7ab8", K: "#d78671" };
  const personalityAxes = [
    ["E", "I", "Energía"], ["S", "N", "Información"], ["T", "F", "Decisiones"], ["J", "P", "Estilo de vida"],
  ];
  const statusLabels = { FINALIZADA: "Finalizada", EN_PROGRESO: "En progreso" };
  const C = {
    green: "#28775f", ink: "#24362d", muted: "#6b7d72", soft: "#8a9a90", body: "#52675a",
    line: "#e4eae5", track: "#edf2ee", mint: "#f0f6f2", lav: "#c5bbdc", greenBar: "#63a881",
  };
  const M = 18; // margen en mm

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value)
      : date.toLocaleString("es-MX", { dateStyle: "long", timeStyle: "short" });
  }

  function isPersonality(questionnaire, points = {}) {
    return questionnaire?.tipo === "PERSONALIDAD" || ["E", "I"].some((key) => key in points);
  }

  function studentName(student) {
    return student ? `${student.nombres} ${student.apellidos}` : "Estudiante no disponible";
  }

  function limpiarNombre(texto) {
    return `${texto.replace(/[\\/:*?"<>|]+/g, "").replace(/\s+/g, " ").trim()}.pdf`;
  }

  function nombreArchivo({ student }) {
    return limpiarNombre(`Ficha ${studentName(student)} ${student?.matricula || ""}`);
  }

  function nombreReporte({ alcance }) {
    return limpiarNombre(`Reporte de resultados - ${alcance || "Total"}`);
  }

  // ------------------------------------------------------------------ utilidades de dibujo

  function nuevoDocumento() {
    const { jsPDF } = window.jspdf || {};
    if (!jsPDF) throw new Error("No se pudo cargar el generador de PDF.");
    return new jsPDF({ unit: "mm", format: "letter" });
  }

  function lienzo(doc) {
    const W = doc.internal.pageSize.getWidth();
    const H = doc.internal.pageSize.getHeight();
    const right = W - M;
    const width = right - M;
    const font = (size, style = "normal", color = C.ink) => {
      doc.setFont("helvetica", style);
      doc.setFontSize(size);
      doc.setTextColor(color);
    };
    const hline = (y, color = C.line, weight = 0.25, x1 = M, x2 = right) => {
      doc.setDrawColor(color);
      doc.setLineWidth(weight);
      doc.line(x1, y, x2, y);
    };
    // Texto con espaciado entre letras alineado a la derecha (jsPDF no descuenta ese espacio).
    const spacedRight = (text, x, y, space) => {
      const ancho = doc.getTextWidth(text) + space * (text.length - 1);
      doc.text(text, x - ancho, y, { charSpace: space });
    };
    const bar = (x, top, w, h, percent, color, track = C.track) => {
      doc.setFillColor(track);
      doc.roundedRect(x, top, w, h, h / 2, h / 2, "F");
      if (percent > 0) {
        doc.setFillColor(color);
        doc.roundedRect(x, top, Math.max(h, (w * percent) / 100), h, h / 2, h / 2, "F");
      }
    };
    return { W, H, right, width, font, hline, spacedRight, bar };
  }

  function encabezado(doc, etiqueta, titulo) {
    const { right, font, hline, spacedRight } = lienzo(doc);
    let y = M;
    doc.setFillColor(C.green);
    doc.roundedRect(M, y, 12, 12, 2.5, 2.5, "F");
    font(14, "bold", "#ffffff");
    doc.text("b.", M + 6, y + 8.2, { align: "center" });
    font(13, "bold");
    doc.text("brújula", M + 15, y + 5.5);
    font(7, "normal", C.muted);
    doc.text("APRENDIZAJE CONSCIENTE", M + 15, y + 10, { charSpace: 0.5 });
    font(7.5, "bold", C.green);
    spacedRight(etiqueta, right, y + 3.5, 0.5);
    font(17, "bold");
    doc.text(titulo, right, y + 11, { align: "right" });
    y += 16;
    hline(y, C.green, 0.9);
    return y;
  }

  function tituloSeccion(doc, y, texto) {
    const { font } = lienzo(doc);
    y += 8;
    font(9, "bold", C.green);
    doc.text(texto.toUpperCase(), M, y, { charSpace: 0.4 });
    return y + 5;
  }

  function datosEnColumnas(doc, y, fields) {
    const { width, right, font, hline } = lienzo(doc);
    const colW = (width - 10) / 2;
    y += 5;
    for (let i = 0; i < fields.length; i += 2) {
      let rowH = 0;
      fields.slice(i, i + 2).forEach(([label, value], col) => {
        const x = M + col * (colW + 10);
        font(7, "bold", C.muted);
        doc.text(label.toUpperCase(), x, y + 3, { charSpace: 0.3 });
        font(10, "bold");
        const lines = doc.splitTextToSize(String(value), colW);
        doc.text(lines, x, y + 8);
        rowH = Math.max(rowH, 6 + lines.length * 4.6);
      });
      y += rowH + 1.5;
      hline(y, C.line, 0.25, M, M + colW);
      hline(y, C.line, 0.25, M + colW + 10, right);
      y += 2;
    }
    return y;
  }

  function recuadro(doc, y, texto) {
    const { width, font } = lienzo(doc);
    font(11, "bold");
    const lines = doc.splitTextToSize(texto, width - 12);
    const boxH = lines.length * 5.2 + 8;
    doc.setFillColor(C.mint);
    doc.roundedRect(M, y, width, boxH, 2, 2, "F");
    doc.setFillColor(C.green);
    doc.rect(M, y, 1.4, boxH, "F");
    doc.text(lines, M + 7, y + 7.5);
    return y + boxH;
  }

  function tablaVark(doc, y, points) {
    const { right, width, font, hline, bar } = lienzo(doc);
    const total = VARK.reduce((sum, key) => sum + (points[key] || 0), 0);
    const top = Math.max(...VARK.map((key) => points[key] || 0));
    const cols = { name: M, bar: M + 42, barW: width - 42 - 34, score: right - 16, pct: right };
    font(7, "bold", C.muted);
    doc.text("DIMENSIÓN", cols.name, y + 3);
    doc.text("DISTRIBUCIÓN", cols.bar, y + 3);
    doc.text("PUNTAJE", cols.score, y + 3, { align: "right" });
    doc.text("%", cols.pct, y + 3, { align: "right" });
    y += 5;
    hline(y, "#d5e3d9", 0.5);
    VARK.forEach((key) => {
      const value = points[key] || 0;
      const percent = total ? Math.round((value / total) * 100) : 0;
      const isTop = value && value === top;
      font(10, isTop ? "bold" : "normal");
      doc.text(labels[key], cols.name, y + 6.5);
      bar(cols.bar, y + 3.6, cols.barW, 3.6, percent, varkColors[key]);
      doc.text(String(value), cols.score, y + 6.5, { align: "right" });
      doc.text(`${percent}%`, cols.pct, y + 6.5, { align: "right" });
      y += 10;
      hline(y);
    });
    return y;
  }

  function ejesPersonalidad(doc, y, points) {
    const { right, width, font, hline } = lienzo(doc);
    personalityAxes.forEach(([left, rightKey, axis]) => {
      const a = points[left] || 0;
      const b = points[rightKey] || 0;
      const leftPercent = a + b ? (a / (a + b)) * 100 : 50;
      font(7, "bold", C.muted);
      doc.text(axis.toUpperCase(), M, y + 3.5, { charSpace: 0.3 });
      font(10, a > b ? "bold" : "normal", a > b ? C.ink : C.body);
      doc.text(`${labels[left]}  ${a}`, M, y + 9.5);
      font(10, b > a ? "bold" : "normal", b > a ? C.ink : C.body);
      doc.text(`${b}  ${labels[rightKey]}`, right, y + 9.5, { align: "right" });
      const barX = M + 50;
      const barW = width - 100;
      doc.setFillColor(C.lav);
      doc.roundedRect(barX, y + 6.6, barW, 3.6, 1.8, 1.8, "F");
      doc.setFillColor(C.greenBar);
      doc.roundedRect(barX, y + 6.6, (barW * leftPercent) / 100, 3.6, 1.8, 1.8, "F");
      y += 13;
      hline(y);
    });
    return y;
  }

  function notaLegal(doc, y) {
    const { width, font } = lienzo(doc);
    font(8.5, "normal", C.muted);
    const note = doc.splitTextToSize(
      "Resultado educativo y de reflexión personal; no constituye un diagnóstico clínico ni una evaluación psicológica. Interprétalo junto con la orientación de tu docente o psicopedagogo.",
      width,
    );
    doc.text(note, M, y);
    return y + note.length * 4;
  }

  // Pie con número de página en todas las hojas.
  function numerarPaginas(doc, izquierda) {
    const total = doc.getNumberOfPages();
    const { H, right, font, hline } = lienzo(doc);
    for (let page = 1; page <= total; page += 1) {
      doc.setPage(page);
      hline(H - 13);
      font(8, "normal", C.soft);
      doc.text(izquierda, M, H - 8.5);
      doc.text(`Página ${page} de ${total}`, right, H - 8.5, { align: "right" });
    }
  }

  // ------------------------------------------------------------------ ficha individual

  function dibujarFicha(doc, datos) {
    const { result, evaluation, student, group, questionnaire, points = {}, interpretation = "" } = datos;
    const { font } = lienzo(doc);
    const personality = isPersonality(questionnaire, points);
    let y = encabezado(doc, "DOCUMENTO DE RESULTADOS", "Ficha de resultado");
    y = datosEnColumnas(doc, y, [
      ["Estudiante", studentName(student)],
      ["Matrícula", student?.matricula || "—"],
      ["Grupo", group ? `${group.nombre} (${group.clave})` : "—"],
      ["Instrumento", questionnaire?.titulo || "—"],
      ["Tipo", personality ? "Personalidad" : "VARK · Estilos de aprendizaje"],
      ["Estado", statusLabels[evaluation?.estado] || "—"],
      ["Fecha", formatDate(evaluation?.finalizada_en || result.calculado_en)],
      ["Preguntas", `${result.preguntas_contestadas ?? "—"} contestadas · ${result.preguntas_omitidas ?? 0} omitidas`],
    ]);
    y = tituloSeccion(doc, y, "Interpretación orientativa");
    y = recuadro(doc, y, interpretation || "Sin interpretación registrada.");
    y = tituloSeccion(doc, y, "Puntajes por dimensión");
    if (!Object.keys(points).length) {
      font(10, "normal", C.muted);
      doc.text("No hay puntajes registrados.", M, y + 4);
      y += 8;
    } else {
      y = personality ? ejesPersonalidad(doc, y, points) : tablaVark(doc, y, points);
    }
    y = notaLegal(doc, y + 10);
    font(8, "normal", C.soft);
    doc.text(`Folio de evaluación #${result.evaluacion}`, M, y + 4);
  }

  function crearPdf(datos) {
    const doc = nuevoDocumento();
    dibujarFicha(doc, datos);
    numerarPaginas(doc, `Generado el ${formatDate(new Date().toISOString())}`);
    doc.setProperties({ title: nombreArchivo(datos).replace(/\.pdf$/, ""), subject: "Ficha de resultado", creator: "Brújula" });
    return doc;
  }

  // ------------------------------------------------------------------ reporte grupal / total

  function sumar(filas, keys) {
    return Object.fromEntries(keys.map((key) => [key, filas.reduce((sum, fila) => sum + (fila.points?.[key] || 0), 0)]));
  }

  function frecuencias(valores) {
    const conteo = new Map();
    valores.filter(Boolean).forEach((valor) => conteo.set(valor, (conteo.get(valor) || 0) + 1));
    return [...conteo.entries()].sort((a, b) => b[1] - a[1]);
  }

  function preferenciaVark(points) {
    const max = Math.max(...VARK.map((key) => points[key] || 0));
    return max ? VARK.filter((key) => (points[key] || 0) === max).map((key) => labels[key]).join(" y ") : "";
  }

  function tipoPersonalidad(points) {
    return personalityAxes.map(([a, b]) => {
      const x = points[a] || 0;
      const y = points[b] || 0;
      return x === y ? `${a}/${b}` : x > y ? a : b;
    }).join("");
  }

  function crearReporte(reporte) {
    const { alcance = "Total", filas = [], incluirFichas = true } = reporte;
    const doc = nuevoDocumento();
    const { H, right, width, font, hline } = lienzo(doc);
    const vark = filas.filter((fila) => !isPersonality(fila.questionnaire, fila.points));
    const personalidad = filas.filter((fila) => isPersonality(fila.questionnaire, fila.points));
    const estudiantes = new Set(filas.map((fila) => fila.student?.id).filter(Boolean));
    const grupos = new Set(filas.map((fila) => fila.group?.id).filter(Boolean));

    let y = encabezado(doc, "REPORTE DE RESULTADOS", "Ficha técnica");
    y = datosEnColumnas(doc, y, [
      ["Alcance", alcance],
      ["Generado", formatDate(new Date().toISOString())],
      ["Resultados", `${filas.length} (${vark.length} VARK · ${personalidad.length} personalidad)`],
      ["Estudiantes evaluados", `${estudiantes.size} en ${grupos.size || 0} grupo${grupos.size === 1 ? "" : "s"}`],
    ]);

    if (!filas.length) {
      y = tituloSeccion(doc, y, "Resumen");
      recuadro(doc, y, "No hay resultados registrados para este alcance.");
    }

    if (vark.length) {
      const totales = sumar(vark, VARK);
      const masFrecuente = frecuencias(vark.map((fila) => preferenciaVark(fila.points)))[0];
      y = tituloSeccion(doc, y, `VARK · puntos acumulados (${vark.length} resultado${vark.length === 1 ? "" : "s"})`);
      y = recuadro(doc, y, `Preferencia del ${alcance.toLowerCase().startsWith("alumno") ? "alumno" : "conjunto"}: ${preferenciaVark(totales) || "sin datos"}.${
        masFrecuente ? ` Preferencia individual más frecuente: ${masFrecuente[0]} (${masFrecuente[1]} de ${vark.length}).` : ""}`);
      y = tablaVark(doc, y + 3, totales);
    }

    if (personalidad.length) {
      if (y > H - 95) { doc.addPage(); y = M; }
      const totales = sumar(personalidad, personalityAxes.flatMap(([a, b]) => [a, b]));
      const tipos = frecuencias(personalidad.map((fila) => tipoPersonalidad(fila.points))).slice(0, 3);
      y = tituloSeccion(doc, y, `Personalidad · puntos acumulados (${personalidad.length} resultado${personalidad.length === 1 ? "" : "s"})`);
      y = recuadro(doc, y, `Tendencia del conjunto: ${tipoPersonalidad(totales)}. Tipos más frecuentes: ${
        tipos.map(([tipo, n]) => `${tipo} (${n})`).join(", ")}.`);
      y = ejesPersonalidad(doc, y + 3, totales);
    }

    // Detalle: una fila por resultado.
    if (filas.length) {
      const cols = [
        ["ESTUDIANTE", M, 52], ["MATRÍCULA", M + 54, 22], ["GRUPO", M + 78, 26],
        ["INSTRUMENTO", M + 106, 40], ["RESULTADO", M + 148, width - 148],
      ];
      const cabecera = () => {
        font(7, "bold", C.muted);
        cols.forEach(([titulo, x]) => doc.text(titulo, x, y + 3));
        y += 5;
        hline(y, "#d5e3d9", 0.5);
      };
      if (y > H - 60) { doc.addPage(); y = M; }
      y = tituloSeccion(doc, y, "Detalle de resultados");
      cabecera();
      filas.forEach((fila) => {
        const personality = isPersonality(fila.questionnaire, fila.points);
        const celdas = [
          studentName(fila.student),
          fila.student?.matricula || "—",
          fila.group?.clave || "—",
          fila.questionnaire?.titulo || "—",
          personality ? tipoPersonalidad(fila.points) : (preferenciaVark(fila.points) || "—"),
        ];
        font(8.5, "normal");
        const lineas = celdas.map((texto, i) => doc.splitTextToSize(String(texto), cols[i][2]));
        const alto = Math.max(...lineas.map((l) => l.length)) * 3.8 + 3;
        if (y + alto > H - 18) {
          doc.addPage();
          y = M;
          cabecera();
          font(8.5, "normal");
        }
        lineas.forEach((l, i) => doc.text(l, cols[i][1], y + 4.6));
        y += alto;
        hline(y);
      });
    }

    y = Math.min(y + 10, H - 30);
    notaLegal(doc, y);

    if (incluirFichas) {
      filas.forEach((fila) => {
        doc.addPage();
        dibujarFicha(doc, fila);
      });
    }
    numerarPaginas(doc, `Reporte de resultados · ${alcance}`);
    doc.setProperties({ title: nombreReporte(reporte).replace(/\.pdf$/, ""), subject: "Reporte de resultados", creator: "Brújula" });
    return doc;
  }

  // ------------------------------------------------------------------ vista previa

  let modal = null;
  let urlActual = null;

  function cerrar() {
    if (!modal) return;
    modal.hidden = true;
    modal.querySelector("iframe").removeAttribute("src");
    delete modal.querySelector("iframe").dataset.pdfUrl;
    if (urlActual) URL.revokeObjectURL(urlActual);
    urlActual = null;
    document.removeEventListener("keydown", alPresionarTecla);
  }

  function alPresionarTecla(event) {
    if (event.key === "Escape") cerrar();
  }

  function crearModal() {
    const estilos = document.createElement("style");
    estilos.textContent = `
.bru-pdf-modal{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:24px;background:rgba(24,42,33,.55)}
.bru-pdf-modal[hidden]{display:none!important}
.bru-pdf-dialog{display:flex;flex-direction:column;width:min(920px,100%);height:min(92vh,1100px);background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 24px 60px rgba(20,40,30,.35)}
.bru-pdf-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#24362d;color:#e6efe9}
.bru-pdf-bar strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:600 14px/1.3 "Segoe UI",Arial,sans-serif}
.bru-pdf-bar button{padding:9px 16px;border:0;border-radius:8px;background:#28775f;color:#fff;font:600 13px "Segoe UI",Arial,sans-serif;cursor:pointer}
.bru-pdf-bar button:hover{background:#205e4c}
.bru-pdf-bar button.is-secondary{background:transparent;border:1px solid #7f978a;color:#e6efe9}
.bru-pdf-dialog iframe{flex:1;width:100%;border:0;background:#525659}
@media(max-width:600px){.bru-pdf-modal{padding:0}.bru-pdf-dialog{height:100%;border-radius:0}}`;
    document.head.append(estilos);
    modal = document.createElement("div");
    modal.className = "bru-pdf-modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="bru-pdf-dialog" role="dialog" aria-modal="true" aria-labelledby="bruPdfTitle">
        <div class="bru-pdf-bar">
          <strong id="bruPdfTitle">Ficha de resultado</strong>
          <button type="button" data-pdf="download">Descargar PDF</button>
          <button type="button" class="is-secondary" data-pdf="close">Cerrar</button>
        </div>
        <iframe title="Vista previa del PDF"></iframe>
      </div>`;
    modal.addEventListener("click", (event) => {
      if (event.target === modal || event.target.closest('[data-pdf="close"]')) cerrar();
    });
    document.body.append(modal);
    return modal;
  }

  function mostrar(doc, archivo) {
    const ventana = modal || crearModal();
    if (urlActual) URL.revokeObjectURL(urlActual);
    urlActual = URL.createObjectURL(doc.output("blob"));
    ventana.querySelector("#bruPdfTitle").textContent = archivo;
    const iframe = ventana.querySelector("iframe");
    iframe.dataset.pdfUrl = urlActual;
    // Las pruebas automáticas desactivan el visor: el visor de PDF del navegador sin interfaz se cierra solo.
    if (!window.__BRUJULA_SIN_VISOR_PDF__) iframe.src = `${urlActual}#view=FitH`;
    ventana.querySelector('[data-pdf="download"]').onclick = () => doc.save(archivo);
    ventana.hidden = false;
    ventana.querySelector('[data-pdf="close"]').focus();
    document.addEventListener("keydown", alPresionarTecla);
    return true;
  }

  window.BrujulaFicha = {
    crearPdf,
    crearReporte,
    nombreArchivo,
    nombreReporte,
    cerrar,
    labels,
    vistaPrevia: (datos) => mostrar(crearPdf(datos), nombreArchivo(datos)),
    descargar: (datos) => { crearPdf(datos).save(nombreArchivo(datos)); return true; },
    vistaPreviaReporte: (reporte) => mostrar(crearReporte(reporte), nombreReporte(reporte)),
    descargarReporte: (reporte) => { crearReporte(reporte).save(nombreReporte(reporte)); return true; },
  };
})();
