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
      fillStudentFilter();
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

  const fullName = (student) => `${student.nombres} ${student.apellidos}`;

  // Alumnos del grupo elegido: permite ver los resultados de forma individual.
  function fillStudentFilter() {
    const group = $("#groupFilter").value;
    const select = $("#studentFilter");
    const selected = select.value;
    const students = state.students
      .filter((student) => !group || String(student.grupo) === group)
      .sort((a, b) => fullName(a).localeCompare(fullName(b), "es"));
    select.replaceChildren(new Option("Todos los alumnos", ""));
    students.forEach((student) => select.add(new Option(`${fullName(student)} · ${student.matricula}`, student.id)));
    select.value = students.some((student) => String(student.id) === selected) ? selected : "";
  }

  function scopeText() {
    const studentId = $("#studentFilter").value;
    const groupId = $("#groupFilter").value;
    if (studentId) {
      const student = state.students.find((item) => String(item.id) === studentId);
      return `Alumno: ${student ? `${fullName(student)} (${student.matricula})` : studentId}`;
    }
    if (groupId) {
      const group = state.groups.find((item) => String(item.id) === groupId);
      return `Grupo: ${group ? `${group.nombre} (${group.clave})` : groupId}`;
    }
    return "Total";
  }

  function filteredResults() {
    const group = $("#groupFilter").value;
    const student = $("#studentFilter").value;
    return state.results.map(resultDetails).filter((row) =>
      (!group || String(row.student?.grupo) === group) && (!student || String(row.student?.id) === student));
  }

  function renderDashboard() {
    const group = $("#groupFilter").value;
    const studentFilter = $("#studentFilter").value;
    const students = state.students.filter((student) =>
      (!group || String(student.grupo) === group) && (!studentFilter || String(student.id) === studentFilter));
    const studentIds = new Set(students.map((student) => student.id));
    const evaluations = state.evaluations.filter((evaluation) => (!group && !studentFilter) || studentIds.has(evaluation.estudiante));
    const results = filteredResults();
    $("#statEvaluations").textContent = evaluations.length;
    $("#statStudents").textContent = studentFilter ? students.length : students.filter((student) => student.activo).length;
    $("#statResults").textContent = results.length;
    $("#scopeLabel").textContent = scopeText();

    const resultIds = new Set(results.map((row) => row.result.id));
    renderChart($("#varkChart"), "VARK", ["V", "A", "R", "K"], resultIds,
      { V: "#63a881", A: "#d6a461", R: "#8c7ab8", K: "#d78671" });
    // Cada eje usa un color; el segundo polo, una variante más clara.
    renderChart($("#personalityChart"), "de personalidad", ["E", "I", "S", "N", "T", "F", "J", "P"], resultIds, {
      E: "#63a881", I: "#a9d1b9", S: "#d6a461", N: "#ebcd9f",
      T: "#8c7ab8", F: "#c5bbdc", J: "#d78671", P: "#ecbcae",
    });

    const recent = results.slice().sort((a, b) => String(b.result.calculado_en).localeCompare(String(a.result.calculado_en))).slice(0, 4);
    $("#recentResults").innerHTML = recent.length ? recent.map(({ result, student, questionnaire }) => {
      const name = student ? `${student.nombres} ${student.apellidos}` : `Evaluación ${result.evaluacion}`;
      return `<div class="bru-results-recent"><strong>${escapeHtml(name)}</strong><span>${escapeHtml(questionnaire?.titulo || "Instrumento")}</span></div>`;
    }).join("") : "<p>Todavía no hay resultados para mostrar.</p>";
  }

  function renderChart(chart, name, dimensions, resultIds, colors) {
    const totals = dimensions.map((dimension) => state.scores
      .filter((score) => score.dimension === dimension && resultIds.has(score.resultado))
      .reduce((sum, score) => sum + Number(score.puntaje || 0), 0));
    const max = Math.max(...totals);
    chart.setAttribute("aria-label", `Gráfico de resultados ${name}: ${dimensions.map((d, i) => `${labels[d]} ${totals[i]}`).join(", ")}`);
    chart.innerHTML = max ? dimensions.map((dimension, index) => {
      const height = totals[index] ? Math.max(4, Math.round((totals[index] / max) * 100)) : 0;
      return `<div class="bru-results-bar-group"><span>${totals[index]}</span><div class="bru-results-bar" style="--height:${height}%;--color:${colors[dimension]}"></div><small>${labels[dimension]}</small></div>`;
    }).join("") : '<p>Los datos aparecerán cuando haya evaluaciones completadas.</p>';
  }

  // Los resultados VARK pueden llegar sin interpretación guardada; se calcula a partir de los puntajes.
  function interpretation(result) {
    if (result.interpretacion) return result.interpretacion;
    const scores = state.scores.filter((score) => score.resultado === result.id);
    const vark = ["V", "A", "R", "K"]
      .map((key) => ({ key, score: Number(scores.find((s) => s.dimension === key)?.puntaje || 0) }));
    const top = Math.max(...vark.map((item) => item.score));
    if (!scores.length || !top) return "";
    const names = vark.filter((item) => item.score === top).map((item) => labels[item.key]);
    return `Preferencia${names.length > 1 ? "s" : ""} más alta${names.length > 1 ? "s" : ""}: ${names.join(" y ")}`;
  }

  const statusLabels = { FINALIZADA: "Finalizada", EN_PROGRESO: "En progreso" };
  let showAll = false; // «Ver todos»: lista todo el alcance sin escribir una búsqueda.

  function findResults(query) {
    if (!state) return;
    const normalized = query.trim().toLocaleLowerCase("es");
    const body = $("#searchResults");
    if (!normalized && !showAll) {
      body.innerHTML = '<tr><td colspan="6">Escribe una búsqueda o pulsa «Ver todos» para consultar resultados.</td></tr>';
      return;
    }
    const rows = filteredResults().filter(({ student, questionnaire, group }) =>
      !normalized || [student?.nombres, student?.apellidos, student?.matricula, group?.nombre, group?.clave, questionnaire?.titulo]
        .join(" ").toLocaleLowerCase("es").includes(normalized));
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="6">${normalized ? "No se encontraron resultados con ese criterio." : "No hay resultados en este alcance."}</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(({ result, evaluation, student, questionnaire }) => {
      const name = student ? `${student.nombres} ${student.apellidos}` : `Estudiante #${result.evaluacion}`;
      const status = statusLabels[evaluation?.estado] || evaluation?.estado || "—";
      return `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(student?.matricula || "—")}</td><td>${escapeHtml(questionnaire?.titulo || "—")}</td><td>${escapeHtml(status)}</td><td>${escapeHtml(interpretation(result) || "Ver ficha")}</td><td><button type="button" data-result="${result.id}">Ver PDF</button></td></tr>`;
    }).join("");
  }

  function fichaData(row) {
    const points = Object.fromEntries(state.scores
      .filter((item) => item.resultado === row.result.id)
      .map((item) => [item.dimension, Number(item.puntaje || 0)]));
    return { ...row, points, interpretation: interpretation(row.result) };
  }

  function printResult(resultId) {
    const result = state.results.find((item) => item.id === resultId);
    if (!result) {
      notice("No fue posible encontrar el resultado que quieres imprimir.");
      return;
    }
    try {
      window.BrujulaFicha.vistaPrevia(fichaData(resultDetails(result)));
    } catch (error) {
      notice(`No se pudo generar la ficha en PDF. ${error.message}`);
    }
  }

  // Reporte del alcance elegido (total, grupo o alumno): resumen, gráficas, detalle y fichas.
  function printReport() {
    if (!state) return;
    try {
      window.BrujulaFicha.vistaPreviaReporte({
        alcance: scopeText(),
        filas: filteredResults().map(fichaData),
        incluirFichas: true,
      });
    } catch (error) {
      notice(`No se pudo generar el reporte en PDF. ${error.message}`);
    }
  }

  function refreshView() {
    if (!state) return;
    renderDashboard();
    findResults($("#resultSearch").value);
  }

  $("#refreshResults").addEventListener("click", loadData);
  $("#groupFilter").addEventListener("change", () => {
    if (!state) return;
    fillStudentFilter();
    refreshView();
  });
  $("#studentFilter").addEventListener("change", refreshView);
  $("#reportButton").addEventListener("click", printReport);
  $("#showAllResults").addEventListener("click", () => {
    showAll = true;
    $("#resultSearch").value = "";
    findResults("");
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
