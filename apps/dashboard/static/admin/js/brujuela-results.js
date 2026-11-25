(() => {
  const root = document.querySelector(".bru-results-dashboard");
  if (!root) return;

  const $ = (selector) => root.querySelector(selector);
  const labels = {
    V: "Visual", A: "Auditivo", R: "Lectura/Escritura", K: "Kinestésico",
    E: "Extroversión", I: "Introversión", S: "Sensación", N: "Intuición",
    T: "Pensamiento", F: "Sentimiento", J: "Juicio", P: "Percepción",
  };
  let state = null;

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function notice(message) {
    const element = $("#resultsNotice");
    element.textContent = message;
    element.hidden = !message;
  }

  async function loadData() {
    const refresh = $("#refreshResults");
    refresh.disabled = true;
    notice("Cargando resultados…");
    try {
      const resources = ["grupos", "estudiantes", "cuestionarios", "evaluaciones", "resultados", "puntajes"];
      const data = await Promise.all(resources.map(async (resource) => {
        const response = await fetch(`/api/${resource}/`);
        if (!response.ok) throw new Error(`${resource}: HTTP ${response.status}`);
        const rows = await response.json();
        if (!Array.isArray(rows)) throw new Error(`${resource}: respuesta inválida`);
        return rows;
      }));
      const [groups, students, questionnaires, evaluations, results, scores] = data;
      state = { groups, students, questionnaires, evaluations, results, scores };
      const select = $("#groupFilter");
      const selected = select.value;
      select.replaceChildren(new Option("Todos los grupos", ""));
      groups.filter((group) => group.activo).forEach((group) => select.add(new Option(group.nombre, group.id)));
      select.value = Array.from(select.options).some((option) => option.value === selected) ? selected : "";
      notice("");
      renderDashboard();
      findResults($("#resultSearch").value);
    } catch (error) {
      notice(`No se pudo actualizar el tablero: ${error.message}. ${state ? "Se muestran los datos anteriores." : "Inténtalo de nuevo."}`);
    } finally {
      refresh.disabled = false;
    }
  }

  function resultDetails(result) {
    const evaluation = state.evaluations.find((item) => item.id === result.evaluacion);
    const student = evaluation && state.students.find((item) => item.id === evaluation.estudiante);
    const questionnaire = evaluation && state.questionnaires.find((item) => item.id === evaluation.cuestionario);
    const group = student && state.groups.find((item) => item.id === student.grupo);
    return { result, evaluation, student, questionnaire, group };
  }

  function filteredResults() {
    const group = $("#groupFilter").value;
    return state.results.map(resultDetails).filter((row) => !group || String(row.student?.grupo) === group);
  }

  function renderDashboard() {
    const group = $("#groupFilter").value;
    const students = state.students.filter((student) => !group || String(student.grupo) === group);
    const studentIds = new Set(students.map((student) => student.id));
    const evaluations = state.evaluations.filter((evaluation) => !group || studentIds.has(evaluation.estudiante));
    const results = filteredResults();
    $("#statEvaluations").textContent = evaluations.length;
    $("#statStudents").textContent = students.filter((student) => student.activo).length;
    $("#statResults").textContent = results.length;

    const resultIds = new Set(results.map((row) => row.result.id));
    const dimensions = ["V", "A", "R", "K"];
    const totals = dimensions.map((dimension) => state.scores
      .filter((score) => score.dimension === dimension && resultIds.has(score.resultado))
      .reduce((sum, score) => sum + Number(score.puntaje || 0), 0));
    const max = Math.max(...totals);
    const chart = $("#varkChart");
    chart.setAttribute("aria-label", `Gráfico de resultados VARK: ${dimensions.map((d, i) => `${labels[d]} ${totals[i]}`).join(", ")}`);
    chart.innerHTML = max ? dimensions.map((dimension, index) => {
      const height = Math.max(4, Math.round((totals[index] / max) * 100));
      const color = { V: "#63a881", A: "#d6a461", R: "#8c7ab8", K: "#d78671" }[dimension];
      return `<div class="bru-results-bar-group"><span>${totals[index]}</span><div class="bru-results-bar" style="--height:${height}%;--color:${color}"></div><small>${labels[dimension]}</small></div>`;
    }).join("") : '<p>Los datos aparecerán cuando haya evaluaciones completadas.</p>';

    const recent = results.slice().sort((a, b) => String(b.result.calculado_en).localeCompare(String(a.result.calculado_en))).slice(0, 4);
    $("#recentResults").innerHTML = recent.length ? recent.map(({ result, student, questionnaire }) => {
      const name = student ? `${student.nombres} ${student.apellidos}` : `Evaluación ${result.evaluacion}`;
      return `<div class="bru-results-recent"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(questionnaire?.titulo || "Instrumento")}</span></div>`;
    }).join("") : "<p>Todavía no hay resultados para mostrar.</p>";
  }

  function findResults(query) {
    if (!state) return;
    const normalized = query.trim().toLocaleLowerCase("es");
    const body = $("#searchResults");
    if (!normalized) {
      body.innerHTML = '<tr><td colspan="6">Escribe una búsqueda para consultar resultados.</td></tr>';
      return;
    }
    const rows = filteredResults().filter(({ student, questionnaire, group }) =>
      [student?.nombres, student?.apellidos, student?.matricula, group?.nombre, group?.clave, questionnaire?.titulo]
        .join(" ").toLocaleLowerCase("es").includes(normalized));
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6">No se encontraron resultados con ese criterio.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(({ result, student, questionnaire }) => {
      const name = student ? `${student.nombres} ${student.apellidos}` : `Estudiante #${result.evaluacion}`;
      return `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(student?.matricula || "—")}</td><td>${escapeHtml(questionnaire?.titulo || "—")}</td><td>Completada</td><td>${escapeHtml(result.interpretacion || "Ver ficha")}</td><td><button type="button" data-result="${result.id}">PDF / imprimir</button></td></tr>`;
    }).join("");
  }

  function printResult(resultId) {
    const result = state.results.find((item) => item.id === resultId);
    if (!result) {
      notice("No fue posible encontrar el resultado que quieres imprimir.");
      return;
    }
    const { student, questionnaire } = resultDetails(result);
    const scores = state.scores.filter((item) => item.resultado === resultId);
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      notice("El navegador bloqueó la ficha. Permite ventanas emergentes para imprimir o guardar como PDF.");
      return;
    }
    printWindow.opener = null;
    printWindow.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Ficha de resultado | Brújula</title><style>body{font:15px Arial,sans-serif;color:#24362d;max-width:760px;margin:50px auto;padding:0 24px}h1{font-size:26px}h2{font-size:17px;margin-top:30px}small{color:#718078}.brand{color:#28775f;font-size:12px;letter-spacing:2px;font-weight:bold}.summary{padding:18px;background:#f0f5f0;border-radius:8px;line-height:1.6}.scores{border-collapse:collapse;width:100%}.scores td,.scores th{text-align:left;padding:10px;border-bottom:1px solid #e4eae5}.scores th{font-size:11px;color:#75817b}@media print{body{margin:0 auto}}</style></head><body><p class="brand">BRÚJULA · APRENDIZAJE CONSCIENTE</p><h1>Ficha de resultado</h1><p><strong>Estudiante:</strong> ${escapeHtml(student ? `${student.nombres} ${student.apellidos}` : "No disponible")}<br><strong>Matrícula:</strong> ${escapeHtml(student?.matricula || "—")}<br><strong>Instrumento:</strong> ${escapeHtml(questionnaire?.titulo || "—")}<br><strong>Fecha:</strong> ${escapeHtml(result.calculado_en || "—")}</p><h2>Interpretación orientativa</h2><p class="summary">${escapeHtml(result.interpretacion || "Sin interpretación registrada.")}</p><h2>Puntajes por dimensión</h2><table class="scores"><thead><tr><th>Dimensión</th><th>Puntaje</th></tr></thead><tbody>${scores.map((score) => `<tr><td>${escapeHtml(labels[score.dimension] || score.dimension)}</td><td>${escapeHtml(score.puntaje)}</td></tr>`).join("") || '<tr><td colspan="2">No hay puntajes registrados.</td></tr>'}</tbody></table><p><small>Resultado educativo y de reflexión personal; no constituye un diagnóstico clínico.</small></p><script>window.addEventListener("load",()=>window.print())<\/script></body></html>`);
    printWindow.document.close();
  }

  $("#refreshResults").addEventListener("click", loadData);
  $("#groupFilter").addEventListener("change", () => {
    if (!state) return;
    renderDashboard();
    findResults($("#resultSearch").value);
  });
  $("#searchButton").addEventListener("click", () => findResults($("#resultSearch").value));
  $("#resultSearch").addEventListener("keydown", (event) => {
    if (event.key === "Enter") findResults(event.currentTarget.value);
  });
  $("#searchResults").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-result]");
    if (button && state) printResult(Number(button.dataset.result));
  });
  loadData();
})();
