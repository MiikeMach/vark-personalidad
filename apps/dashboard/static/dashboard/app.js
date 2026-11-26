(() => {
  const API = "/api/";
  const state = {
    students: [],
    groups: [],
    questionnaires: [],
    details: {},          // id de cuestionario → cuestionario completo (con preguntas)
    questions: [],
    answers: [],
    evaluationId: null,
    currentQuestion: 0,
    kind: "VARK",
    user: null,
    loaded: false,
    active: null,         // { student, questionnaire } de la evaluación en curso
    lastResult: null,     // datos de la ficha del último resultado
  };
  const labels = {
    V: "Visual", A: "Auditivo", R: "Lectura/Escritura", K: "Kinestésico",
    E: "Extroversión", I: "Introversión", S: "Sensación", N: "Intuición",
    T: "Pensamiento", F: "Sentimiento", J: "Juicio", P: "Percepción",
  };
  const varkColors = { V: "#63a881", A: "#d6a461", R: "#8c7ab8", K: "#d78671" };
  const personalityPairs = ["EI", "SN", "TF", "JP"];
  const SKIPPED = "omitida"; // Marca de pregunta VARK omitida a propósito.
  const personalityAxes = [["E", "I", "Energía"], ["S", "N", "Información"], ["T", "F", "Decisiones"], ["J", "P", "Estilo de vida"]];
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  async function api(path, options = {}) {
    const csrf = $('input[name="csrfmiddlewaretoken"]');
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.method && options.method !== "GET" ? { "X-CSRFToken": csrf.value } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      let detail = `La solicitud falló (${response.status}).`;
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
      } catch (_) {
        // Se conserva el estado HTTP cuando la respuesta no es JSON.
      }
      throw new Error(detail);
    }
    return response.status === 204 ? null : response.json();
  }

  function showNotice(message, type = "error") {
    const notice = $("#globalNotice");
    notice.textContent = message;
    notice.className = `notice ${type}`;
    notice.hidden = false;
    notice.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function clearNotice() {
    $("#globalNotice").hidden = true;
  }

  function routeTo(name) {
    const safeName = ["inicio", "instrumentos", "guia"].includes(name) ? name : "inicio";
    $$(".page-section").forEach((section) => section.classList.toggle("current", section.id === `page-${safeName}`));
    $$(".nav-link[data-route]:not([data-scroll])").forEach((link) => link.classList.toggle("active", link.dataset.route === safeName));
    $("#pageName").textContent = $(`#page-${safeName}`).dataset.title;
    document.title = `${$("#pageName").textContent[0]}${$("#pageName").textContent.slice(1).toLowerCase()} | Brújula`;
    $("#sidebar").classList.remove("open");
    $("#mobileScrim").classList.remove("visible");
    $("#menuToggle").setAttribute("aria-expanded", "false");
    clearNotice();
    window.scrollTo({ top: 0, behavior: "smooth" });
    // Al entrar a Instrumentos se vuelve a pedir la lista: así aparecen los cuestionarios recién creados.
    if (safeName === "instrumentos" && state.loaded) refreshQuestionnaires();
  }

  function setOptions(select, rows, emptyLabel, getLabel) {
    const previous = select.value;
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = rows.length ? "Selecciona una opción" : emptyLabel;
    select.append(empty);
    rows.forEach((row) => {
      const option = document.createElement("option");
      option.value = row.id;
      option.textContent = getLabel(row);
      select.append(option);
    });
    if ([...select.options].some((option) => option.value === previous && !option.disabled)) select.value = previous;
  }

  // ---------------------------------------------------------------- carga de datos

  async function fetchQuestionnaires() {
    const rows = await api("cuestionarios/");
    const active = rows.filter((questionnaire) => questionnaire.activo);
    const details = await Promise.allSettled(active.map((questionnaire) => api(`cuestionarios/${questionnaire.id}/completo/`)));
    const byId = {};
    details.forEach((detail, index) => {
      if (detail.status === "fulfilled") byId[active[index].id] = detail.value;
    });
    return { rows, details: byId };
  }

  async function loadData() {
    const tasks = [
      ["estudiantes/", () => api("estudiantes/"), (value) => { state.students = value; }, true],
      ["cuestionarios/", fetchQuestionnaires, (value) => { state.questionnaires = value.rows; state.details = value.details; }, true],
      ["auth/me/", () => api("auth/me/"), (value) => { state.user = value.user; }, false],
      ["grupos/", () => api("grupos/"), (value) => { state.groups = value; }, false],
    ];
    const results = await Promise.allSettled(tasks.map(([, run]) => run()));
    const failed = [];
    results.forEach((result, index) => {
      const [path, , apply, required] = tasks[index];
      if (result.status === "fulfilled") apply(result.value);
      else if (required || String(result.reason?.message || result.reason).includes("(500)")) failed.push(path);
    });
    state.loaded = true;
    updateQuestionnaires();
    updateSessionUI();
    $("#connectionStatus").textContent = failed.length ? "Conexión parcial" : "Sistema conectado";
    if (failed.length) showNotice(`No se pudieron cargar algunos datos (${failed.join(", ")}). Recarga la página o intenta más tarde.`);
  }

  // Recarga silenciosa de la lista (al entrar a Instrumentos); si falla, se conserva la anterior.
  async function refreshQuestionnaires() {
    try {
      const { rows, details } = await fetchQuestionnaires();
      state.questionnaires = rows;
      state.details = details;
      updateQuestionnaires();
    } catch (_) {
      // Se mantiene la lista ya cargada.
    }
  }

  function updateSessionUI() {
    const user = state.user;
    const displayName = user && (user.first_name || user.last_name)
      ? `${user.first_name || ""} ${user.last_name || ""}`.trim()
      : user?.username;
    $("#userName").textContent = displayName || "Tu espacio";
    $("#userRole").textContent = user ? (user.is_staff ? "Sesión de administrador" : "Sesión activa") : "Aprendizaje personal";
    $("#userAvatar").textContent = (displayName || "B").charAt(0).toUpperCase();
    $("#logoutButton").hidden = !user;
    updateGroupOptions();
    updateStudentOptions();
  }

  // La evaluación se puede aplicar a un grupo: se elige el grupo y luego a cada estudiante de ese grupo.
  function updateGroupOptions() {
    const select = $("#groupSelect");
    const previous = select.value;
    const withStudents = new Set(state.students.filter((student) => student.activo).map((student) => student.grupo));
    const groups = state.groups.filter((group) => group.activo && withStudents.has(group.id));
    select.replaceChildren(new Option("Todos los grupos", ""));
    groups.forEach((group) => select.add(new Option(`${group.nombre} · ${group.clave}`, group.id)));
    select.value = groups.some((group) => String(group.id) === previous) ? previous : "";
  }

  function updateStudentOptions() {
    const group = $("#groupSelect").value;
    const students = state.students.filter((student) => student.activo && (!group || String(student.grupo) === group));
    setOptions($("#studentSelect"), students, group ? "No hay estudiantes en este grupo" : "No hay estudiantes disponibles",
      (student) => `${student.nombres} ${student.apellidos} · ${student.matricula}`);
    $("#assessmentSetup").querySelector('button[type="submit"]').disabled = !students.length;
  }

  // ---------------------------------------------------------------- cuestionarios

  function questionCount(questionnaire) {
    const detail = state.details[questionnaire.id];
    return detail ? detail.preguntas.length : null;
  }

  function availableQuestionnaires(kind) {
    return state.questionnaires.filter((q) => q.activo && q.tipo === kind);
  }

  function plural(count, singular, pluralForm) {
    return `${count} ${count === 1 ? singular : pluralForm}`;
  }

  function updateCounts() {
    ["VARK", "PERSONALIDAD"].forEach((kind) => {
      const ready = availableQuestionnaires(kind).filter((q) => questionCount(q) !== 0).length;
      const text = ready ? `${plural(ready, "cuestionario disponible", "cuestionarios disponibles")}` : "Aún no hay cuestionarios";
      $$(`[data-count="${kind}"]`).forEach((element) => {
        element.textContent = text;
        element.classList.toggle("is-empty", !ready);
      });
    });
  }

  function updateQuestionnaires() {
    const select = $("#questionnaireSelect");
    const active = availableQuestionnaires(state.kind);
    setOptions(select, active, "No hay cuestionarios activos", (questionnaire) =>
      questionCount(questionnaire) === 0 ? `${questionnaire.titulo} · sin preguntas` : questionnaire.titulo);
    // Un cuestionario sin preguntas todavía no se puede contestar.
    [...select.options].forEach((option) => {
      const questionnaire = active.find((item) => String(item.id) === option.value);
      option.disabled = Boolean(questionnaire) && questionCount(questionnaire) === 0;
    });
    if (select.selectedOptions[0]?.disabled) select.value = "";
    // Si solo hay uno disponible, se deja elegido.
    const enabled = [...select.options].filter((option) => option.value && !option.disabled);
    if (!select.value && enabled.length === 1) select.value = enabled[0].value;
    $("#assessmentTitle").textContent = state.kind === "VARK" ? "Estilo de aprendizaje VARK" : "Personalidad · Jung / Myers-Briggs";
    $("#assessmentDescription").textContent = state.kind === "VARK"
      ? "Cuéntanos quién eres para asociar tus respuestas a tu perfil."
      : "Reflexiona sobre tus preferencias personales. No existen respuestas correctas o incorrectas.";
    updateCounts();
    updatePreview();
  }

  function updatePreview() {
    const id = Number($("#questionnaireSelect").value);
    const questionnaire = state.details[id] || state.questionnaires.find((item) => item.id === id);
    const preview = $("#questionnairePreview");
    preview.hidden = !questionnaire;
    if (!questionnaire) return;
    const count = questionCount(questionnaire);
    $("#previewTitle").textContent = questionnaire.titulo;
    $("#previewCount").textContent = count === null ? questionnaire.tipo : plural(count, "pregunta", "preguntas");
    $("#previewDescription").textContent = questionnaire.descripcion || "Sin descripción.";
    $("#previewInstructions").textContent = questionnaire.instrucciones || "";
    $("#previewInstructions").hidden = !questionnaire.instrucciones;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function showSetup() {
    $("#assessmentSetup").hidden = false;
    $("#questionMount").hidden = true;
    $("#assessmentResult").hidden = true;
  }

  function chooseKind(kind) {
    state.kind = kind;
    $$(".assessment-choice").forEach((button) => {
      const selected = button.dataset.choice === kind;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    showSetup();
    updateQuestionnaires();
  }

  // ---------------------------------------------------------------- evaluación

  async function beginAssessment(event) {
    event.preventDefault();
    clearNotice();
    const form = event.currentTarget;
    const questionnaireId = Number(form.elements.cuestionario.value);
    const studentId = Number(form.elements.estudiante.value);
    const questionnaire = state.questionnaires.find((item) => item.id === questionnaireId);
    if (!questionnaire || !studentId) {
      showNotice("Selecciona un estudiante y un cuestionario activo antes de continuar.");
      return;
    }
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Preparando evaluación…";
    try {
      const payload = await api("evaluaciones/iniciar/", {
        method: "POST",
        body: JSON.stringify({ estudiante: studentId, cuestionario: questionnaireId }),
      });
      state.questions = payload.cuestionario.preguntas || [];
      if (!state.questions.length) throw new Error("Este cuestionario todavía no tiene preguntas disponibles.");
      if (state.questions.some((question) => !question.opciones.length)) throw new Error("Una o más preguntas no tienen opciones configuradas. Solicita apoyo al administrador.");
      if (state.kind === "PERSONALIDAD" && state.questions.some((question) =>
        question.opciones.length !== 2 ||
        !personalityPairs.some((pair) => question.opciones.every((option) =>
          typeof option.dimension === "string" && option.dimension.length === 1 && pair.includes(option.dimension)) &&
          question.opciones[0].dimension !== question.opciones[1].dimension)
      )) throw new Error("Cada pregunta de personalidad debe tener dos opciones de dimensiones opuestas. Solicita apoyo al administrador.");
      state.evaluationId = payload.evaluacion.id;
      state.active = {
        student: state.students.find((item) => item.id === studentId),
        questionnaire: { ...questionnaire, ...payload.cuestionario },
      };
      state.answers = Array(state.questions.length).fill(null);
      state.currentQuestion = 0;
      $("#assessmentResult").hidden = true;
      form.hidden = true;
      $("#questionMount").hidden = false;
      renderQuestion();
    } catch (error) {
      showNotice(error.message);
    } finally {
      submit.disabled = !state.students.some((student) => student.activo);
      submit.innerHTML = 'Comenzar evaluación <span>→</span>';
    }
  }

  function renderQuestion() {
    const question = state.questions[state.currentQuestion];
    const mount = $("#questionMount");
    const multi = state.kind === "VARK";
    const answer = state.answers[state.currentQuestion];
    const selected = Array.isArray(answer) ? answer : [];
    const percent = Math.round(((state.currentQuestion + 1) / state.questions.length) * 100);
    const questionnaire = state.active?.questionnaire;
    const answerFields = multi
      ? `<div class="answer-list">${question.opciones.map((option) => `
        <label class="answer-option"><input type="checkbox" name="answer" value="${option.id}" ${selected.includes(option.id) ? "checked" : ""}><span>${escapeHtml(option.texto)}</span></label>
      `).join("")}</div>`
      : `<div class="points-poles">
          <span class="pole-card"><small>OPCIÓN A</small>${escapeHtml(question.opciones[0].texto)}</span>
          <span class="pole-card"><small>OPCIÓN B</small>${escapeHtml(question.opciones[1].texto)}</span>
        </div>
        <label for="personalityPoints">Puntos para: ${escapeHtml(question.opciones[0].texto)}</label>
        <select id="personalityPoints">
          <option value="">Selecciona los puntos</option>
          ${[0, 1, 2, 3, 4, 6, 7, 8, 9, 10].map((points) =>
            `<option value="${points}" ${selected.length && selected[0].puntos === points ? "selected" : ""}>${points}</option>`
          ).join("")}
        </select>
        <div class="points-split" aria-hidden="true"><span class="split-a"></span><span class="split-b"></span></div>
        <p id="personalityOtherPoints" class="form-help"></p>`;
    mount.innerHTML = `
      ${questionnaire ? `<div class="question-context"><strong>${escapeHtml(questionnaire.titulo)}</strong>${questionnaire.instrucciones ? `<span>${escapeHtml(questionnaire.instrucciones)}</span>` : ""}</div>` : ""}
      <div class="question-progress"><span>Pregunta ${state.currentQuestion + 1} de ${state.questions.length}</span><span>${percent}%</span></div>
      <div class="progress-track"><div class="progress-fill" style="width:${percent}%"></div></div>
      <h3 class="question-text">${escapeHtml(question.texto)}</h3>
      <p class="form-help">${multi ? "Puedes elegir más de una opción." : "Distribuye 10 puntos entre las dos opciones. No se permite el reparto 5 y 5."}</p>
      ${answerFields}
      <div class="question-actions"><button type="button" data-action="previous" ${state.currentQuestion === 0 ? "disabled" : ""}>← Anterior</button>${
        multi ? '<button type="button" class="skip-button" data-action="skip" title="Deja esta pregunta sin contestar">Omitir</button>' : ""
      }<button type="button" data-action="next">${state.currentQuestion === state.questions.length - 1 ? "Finalizar" : "Siguiente →"}</button></div>
      ${multi && state.answers.some((answer, index) => index !== state.currentQuestion && answer === SKIPPED)
        ? `<p class="form-help skipped-help">${plural(state.answers.filter((answer) => answer === SKIPPED).length, "pregunta omitida", "preguntas omitidas")}; puedes regresar a contestarlas.</p>`
        : ""}`;
    if (!multi) {
      const points = $("#personalityPoints", mount);
      const updateOtherPoints = () => {
        const chosen = points.value === "" ? null : Number(points.value);
        $("#personalityOtherPoints", mount).textContent = chosen === null
          ? `Puntos para ${question.opciones[1].texto}: pendientes.`
          : `Puntos para ${question.opciones[1].texto}: ${10 - chosen}.`;
        const a = $(".split-a", mount);
        const b = $(".split-b", mount);
        a.style.width = chosen === null ? "50%" : `${chosen * 10}%`;
        b.style.width = chosen === null ? "50%" : `${(10 - chosen) * 10}%`;
        a.textContent = chosen === null ? "A" : `A · ${chosen}`;
        b.textContent = chosen === null ? "B" : `B · ${10 - chosen}`;
        $(".points-split", mount).classList.toggle("is-pending", chosen === null);
      };
      points.addEventListener("change", updateOtherPoints);
      updateOtherPoints();
    }
    mount.querySelector('[data-action="previous"]').addEventListener("click", () => moveQuestion(-1));
    mount.querySelector('[data-action="next"]').addEventListener("click", () => moveQuestion(1));
    mount.querySelector('[data-action="skip"]')?.addEventListener("click", () => moveQuestion(1, { skip: true }));
  }

  function moveQuestion(direction, { skip = false } = {}) {
    const mount = $("#questionMount");
    const question = state.questions[state.currentQuestion];
    let selected;
    if (state.kind === "VARK") {
      selected = $$('input[name="answer"]:checked', mount).map((input) => Number(input.value));
    } else {
      const value = $("#personalityPoints", mount).value;
      selected = value === "" ? [] : [
        { opcion: question.opciones[0].id, puntos: Number(value) },
        { opcion: question.opciones[1].id, puntos: 10 - Number(value) },
      ];
    }
    const previous = state.answers[state.currentQuestion];
    if (skip) {
      // VARK admite preguntas omitidas: se envían sin opciones y el resultado las cuenta aparte.
      state.answers[state.currentQuestion] = SKIPPED;
      selected = [SKIPPED];
    } else if (selected.length) {
      state.answers[state.currentQuestion] = selected;
    } else {
      state.answers[state.currentQuestion] = previous === SKIPPED && direction < 0 ? SKIPPED : null;
    }
    if (!selected.length && direction > 0) {
      showNotice(state.kind === "VARK"
        ? "Selecciona al menos una respuesta o pulsa «Omitir» para continuar."
        : "Selecciona una distribución de puntos para continuar.");
      return;
    }
    clearNotice();
    const next = state.currentQuestion + direction;
    if (next < 0) return;
    if (next === state.questions.length) {
      if (state.answers.every((answer) => answer === SKIPPED)) {
        showNotice("Contesta al menos una pregunta para poder calcular tu resultado.");
        return;
      }
      finishAssessment();
      return;
    }
    state.currentQuestion = next;
    renderQuestion();
  }

  // ---------------------------------------------------------------- resultado

  function varkTop(scores) {
    const values = ["V", "A", "R", "K"].map((key) => ({ key, score: scores[key] || 0 }));
    const max = Math.max(...values.map((item) => item.score));
    return max ? values.filter((item) => item.score === max).map((item) => labels[item.key]) : [];
  }

  // Tipo observado; en un empate se muestran ambos polos (p. ej. «S/N»).
  function personalityType(scores) {
    return personalityAxes.map(([first, second]) => {
      const a = scores[first] || 0;
      const b = scores[second] || 0;
      return a === b ? `${first}/${second}` : a > b ? first : second;
    }).join("");
  }

  function getInterpretation(scores) {
    if (state.kind === "VARK") {
      const top = varkTop(scores);
      return `Preferencia${top.length > 1 ? "s" : ""} más alta${top.length > 1 ? "s" : ""}: ${top.join(" y ") || "sin datos"}. Este resultado es una guía de reflexión, no una etiqueta fija.`;
    }
    const type = personalityType(scores);
    const tie = type.includes("/")
      ? " En los ejes marcados con «/» obtuviste los mismos puntos en ambos polos."
      : "";
    return `Tendencia observada: ${type}.${tie} Es una síntesis orientativa de tus respuestas, no una evaluación clínica ni una descripción completa de tu personalidad.`;
  }

  function scoresHtml(scores) {
    if (state.kind === "VARK") {
      const total = ["V", "A", "R", "K"].reduce((sum, key) => sum + (scores[key] || 0), 0);
      const max = Math.max(...["V", "A", "R", "K"].map((key) => scores[key] || 0));
      return ["V", "A", "R", "K"].map((key) => {
        const value = scores[key] || 0;
        const percent = total ? Math.round((value / total) * 100) : 0;
        return `<li class="score-row${value && value === max ? " is-top" : ""}" data-dimension="${key}">
          <span class="score-name">${labels[key]}</span>
          <span class="score-bar"><i style="width:${percent}%;background:${varkColors[key]}"></i></span>
          <b class="score-value">${value}</b><small class="score-percent">${percent}%</small></li>`;
      }).join("");
    }
    return personalityAxes.map(([left, right, axis]) => {
      const a = scores[left] || 0;
      const b = scores[right] || 0;
      const leftPercent = a + b ? Math.round((a / (a + b)) * 100) : 50;
      return `<li class="axis-row" data-axis="${left}${right}">
        <small class="axis-name">${axis}</small>
        <span class="axis-pole${a > b ? " is-win" : ""}">${labels[left]} <b>${a}</b></span>
        <span class="axis-split"><i style="width:${leftPercent}%"></i></span>
        <span class="axis-pole is-right${b > a ? " is-win" : ""}"><b>${b}</b> ${labels[right]}</span></li>`;
    }).join("");
  }

  function renderResult(data) {
    const { result, student, questionnaire, points } = data;
    const name = student ? `${student.nombres} ${student.apellidos}` : "Estudiante";
    const omitted = Number(result.preguntas_omitidas || 0);
    $("#assessmentResultMeta").textContent = `${name} · ${questionnaire?.titulo || "Cuestionario"}` +
      (omitted ? ` · ${plural(omitted, "pregunta omitida", "preguntas omitidas")}` : "");
    if (state.kind === "VARK") {
      const top = varkTop(points);
      $("#resultHighlightLabel").textContent = top.length > 1 ? "PREFERENCIAS MÁS ALTAS" : "PREFERENCIA MÁS ALTA";
      $("#resultHighlight").textContent = top.join(" y ") || "Sin datos";
    } else {
      $("#resultHighlightLabel").textContent = "TENDENCIA OBSERVADA";
      $("#resultHighlight").textContent = personalityType(points);
    }
    $("#assessmentInterpretation").textContent = data.interpretation;
    $("#assessmentScores").innerHTML = scoresHtml(points);
    $("#assessmentScores").className = `result-scores ${state.kind === "VARK" ? "is-vark" : "is-personality"}`;
  }

  async function finishAssessment() {
    const button = $('[data-action="next"]', $("#questionMount"));
    button.disabled = true;
    button.textContent = "Guardando…";
    try {
      const response = await api(`evaluaciones/${state.evaluationId}/responder/`, {
        method: "POST",
        body: JSON.stringify({
          respuestas: state.questions.map((question, index) => state.kind === "VARK"
            ? { pregunta: question.id, opciones: Array.isArray(state.answers[index]) ? state.answers[index] : [] }
            : { pregunta: question.id, selecciones: state.answers[index] || [] }),
          calcular: true,
        }),
      });
      const result = response.resultado;
      if (!result) throw new Error("La evaluación se guardó, pero el resultado no pudo calcularse.");
      const points = Object.fromEntries(result.puntajes.map((score) => [score.dimension, Number(score.puntaje || 0)]));
      const student = state.active?.student;
      state.lastResult = {
        result,
        evaluation: response.evaluacion,
        student,
        group: student && state.groups.find((group) => group.id === student.grupo),
        questionnaire: state.active?.questionnaire,
        points,
        interpretation: getInterpretation(points),
      };
      renderResult(state.lastResult);
      // Se conserva el grupo para seguir aplicando la evaluación al resto del grupo.
      const group = $("#groupSelect").value;
      $("#assessmentSetup").reset();
      $("#groupSelect").value = group;
      $("#assessmentSetup").hidden = true;
      $("#questionMount").hidden = true;
      $("#assessmentResult").hidden = false;
      showNotice("Tu evaluación quedó registrada.", "success");
      $("#assessmentResult").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showNotice(`No se pudo completar el guardado: ${error.message} Si la conexión se interrumpió, contacta al administrador antes de volver a enviar para evitar duplicados.`);
      button.disabled = false;
      button.textContent = "Reintentar guardado";
    }
  }

  function newAssessment() {
    clearNotice();
    showSetup();
    updateQuestionnaires();
    updateStudentOptions();
    $("#studentSelect").focus();
  }

  // ---------------------------------------------------------------- contacto y video

  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  const contactFields = { nombre: "#contactName", correo: "#contactEmail", asunto: "#contactTopic", mensaje: "#contactMessage" };

  function markContactErrors(form, fields, message) {
    const error = $("#contactError");
    $$("input, select, textarea", form).forEach((field) => field.removeAttribute("aria-invalid"));
    const inputs = fields.map((name) => $(contactFields[name])).filter(Boolean);
    inputs.forEach((field) => field.setAttribute("aria-invalid", "true"));
    error.textContent = message;
    error.hidden = false;
    inputs[0]?.focus();
  }

  // Envía el mensaje a la API de contacto (POST /api/contacto/), que lo reenvía por correo.
  async function sendContact(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    Object.keys(data).forEach((key) => { data[key] = String(data[key]).trim(); });
    const problems = [];
    if (!data.nombre) problems.push(["nombre", "tu nombre"]);
    if (!EMAIL.test(data.correo || "")) problems.push(["correo", "un correo válido"]);
    if (!data.asunto) problems.push(["asunto", "el asunto"]);
    if ((data.mensaje || "").length < 10) problems.push(["mensaje", "un mensaje de al menos 10 caracteres"]);
    if (problems.length) {
      markContactErrors(form, problems.map(([field]) => field),
        `Revisa el formulario: falta ${problems.map(([, text]) => text).join(", ")}.`);
      return;
    }
    $("#contactError").hidden = true;
    $$("input, select, textarea", form).forEach((field) => field.removeAttribute("aria-invalid"));
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = "Enviando…";
    try {
      const response = await fetch(`${API}contacto/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        // La API responde {detail: {campo: [mensajes]}} cuando un campo no es válido.
        if (body.detail && typeof body.detail === "object") {
          const fields = Object.keys(body.detail).filter((name) => name in contactFields);
          markContactErrors(form, fields, Object.values(body.detail).flat().join(" "));
          return;
        }
        throw new Error(typeof body.detail === "string" ? body.detail : `Error ${response.status}.`);
      }
      form.reset();
      showNotice("¡Gracias! Tu mensaje se envió correctamente. Te responderemos al correo que indicaste.", "success");
    } catch (error) {
      markContactErrors(form, [], `No se pudo enviar el mensaje. ${error.message} Intenta de nuevo más tarde.`);
    } finally {
      button.disabled = false;
      button.innerHTML = "Enviar mensaje <span>→</span>";
    }
  }

  function setupVideo() {
    const video = $("#introVideo");
    const source = $("source", video);
    const showPlaceholder = () => {
      video.hidden = true;
      $("#videoPlaceholder").hidden = false;
    };
    // El error de carga lo emite <source>, no <video>.
    source.addEventListener("error", showPlaceholder);
    video.addEventListener("error", showPlaceholder);
    if (video.networkState === HTMLMediaElement.NETWORK_NO_SOURCE) showPlaceholder();
  }

  function fichaPdf(accion) {
    if (!state.lastResult) return;
    try {
      window.BrujulaFicha[accion](state.lastResult);
    } catch (error) {
      showNotice(`No se pudo generar la ficha en PDF. ${error.message}`);
    }
  }

  // ---------------------------------------------------------------- eventos

  function bindEvents() {
    $("#logoutButton").addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await api("auth/logout/", { method: "POST" });
        window.location.assign("/#inicio");
      } catch (error) {
        showNotice(error.message);
        button.disabled = false;
      }
    });
    $$("[data-route]").forEach((link) => link.addEventListener("click", (event) => {
      if (link.dataset.focus) chooseKind(link.dataset.focus);
      const target = link.dataset.route || link.getAttribute("href").slice(1);
      if (target) {
        event.preventDefault();
        history.pushState(null, "", `#${target}`);
        routeTo(target);
        const destino = link.dataset.scroll && document.getElementById(link.dataset.scroll);
        if (destino) setTimeout(() => destino.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
      }
    }));
    window.addEventListener("popstate", () => routeTo(location.hash.slice(1)));
    window.addEventListener("hashchange", () => routeTo(location.hash.slice(1)));
    $("#menuToggle").addEventListener("click", () => {
      const open = $("#sidebar").classList.toggle("open");
      $("#mobileScrim").classList.toggle("visible", open);
      $("#menuToggle").setAttribute("aria-expanded", String(open));
    });
    $("#mobileScrim").addEventListener("click", () => {
      $("#sidebar").classList.remove("open");
      $("#mobileScrim").classList.remove("visible");
      $("#menuToggle").setAttribute("aria-expanded", "false");
    });
    $$(".assessment-choice").forEach((button) => button.addEventListener("click", () => chooseKind(button.dataset.choice)));
    $("#assessmentSetup").addEventListener("submit", beginAssessment);
    $("#questionnaireSelect").addEventListener("change", updatePreview);
    $("#groupSelect").addEventListener("change", updateStudentOptions);
    $("#contactForm").addEventListener("submit", sendContact);
    $("#newAssessment").addEventListener("click", newAssessment);
    $("#viewFicha").addEventListener("click", () => fichaPdf("vistaPrevia"));
    $("#downloadPdf").addEventListener("click", () => fichaPdf("descargar"));
  }

  bindEvents();
  setupVideo();
  routeTo(location.hash.slice(1) || "inicio");
  loadData().catch((error) => {
    $("#connectionStatus").textContent = "Sin conexión";
    showNotice(`No fue posible conectar con la API. ${error.message}`);
  });
})();
