(() => {
  const API = "/api/";
  const state = {
    students: [],
    questionnaires: [],
    questions: [],
    answers: [],
    evaluationId: null,
    currentQuestion: 0,
    kind: "VARK",
    user: null,
  };
  const labels = {
    V: "Visual", A: "Auditivo", R: "Lectura/Escritura", K: "Kinestésico",
    E: "Extroversión", I: "Introversión", S: "Sensación", N: "Intuición",
    T: "Pensamiento", F: "Sentimiento", J: "Juicio", P: "Percepción",
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];


  function getCookie(name) {
    const cookies = document.cookie.split(";");

    for (const cookie of cookies) {
      const [key, ...value] = cookie.trim().split("=");

      if (key === name) {
        return decodeURIComponent(value.join("="));
      }
    }

    return null;
  }

  async function api(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
      if (!getCookie("csrftoken")) {
        const csrfResponse = await fetch(`${API}auth/csrf/`, {
          credentials: "same-origin",
        });

        if (!csrfResponse.ok) {
          throw new Error("No se pudo inicializar la protección CSRF.");
        }
      }

      const token = getCookie("csrftoken");

      if (!token) {
        throw new Error("No se encontró el token CSRF.");
      }

      headers["X-CSRFToken"] = token;
    }

    const response = await fetch(`${API}${path}`, {
      ...options,
      method,
      credentials: "same-origin",
      headers,
    });

    if (!response.ok) {
      let detail = `La solicitud falló (${response.status}).`;

      try {
        const body = await response.json();
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail || body);
      } catch (_) {
        // Mantener el código HTTP si la respuesta no es JSON.
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
    $$(".nav-link[data-route]").forEach((link) => link.classList.toggle("active", link.dataset.route === safeName));
    $("#pageName").textContent = $(`#page-${safeName}`).dataset.title;
    document.title = `${$("#pageName").textContent[0]}${$("#pageName").textContent.slice(1).toLowerCase()} | Brújula`;
    $("#sidebar").classList.remove("open");
    $("#mobileScrim").classList.remove("visible");
    $("#menuToggle").setAttribute("aria-expanded", "false");
    clearNotice();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setOptions(select, rows, emptyLabel, getLabel) {
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
  }

  async function loadData() {
    const resources = ["estudiantes/", "cuestionarios/", "auth/me/"];
    const results = await Promise.allSettled(resources.map((path) => api(path)));
    const names = ["students", "questionnaires", "user"];
    const failed = [];
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        state[names[index]] = names[index] === "user" ? result.value.user : result.value;
      } else if (names[index] !== "user" || String(result.reason?.message || result.reason).includes("(500)")) {
        failed.push(resources[index]);
      }
    });
    setOptions($("#studentSelect"), state.students.filter((student) => student.activo), "No hay estudiantes registrados", (student) => `${student.nombres} ${student.apellidos} · ${student.matricula}`);
    updateQuestionnaires();
    updateSessionUI();
    $("#connectionStatus").textContent = failed.length ? "Conexión parcial" : "Sistema conectado";
    if (failed.length) showNotice(`No se pudieron cargar algunos datos (${failed.join(", ")}). Recarga la página o intenta más tarde.`);
  }

  function updateSessionUI() {
    const user = state.user;
    const displayName = user && (user.first_name || user.last_name)
      ? `${user.first_name || ""} ${user.last_name || ""}`.trim()
      : user?.username;
    $("#userName").textContent = displayName || "Tu espacio";
    $("#userRole").textContent = user ? (user.is_staff ? "Sesión de administrador" : "Sesión activa") : "Sesión no iniciada";
    $("#userAvatar").textContent = (displayName || "B").charAt(0).toUpperCase();
    $("#sessionHelp").hidden = Boolean(user);
    $("#assessmentSetup").querySelector('button[type="submit"]').disabled = !user;
  }

  function updateQuestionnaires() {
    const active = state.questionnaires.filter((q) => q.activo && q.tipo === state.kind);
    setOptions($("#questionnaireSelect"), active, "No hay cuestionarios activos", (questionnaire) => questionnaire.titulo);
    $("#assessmentTitle").textContent = state.kind === "VARK" ? "Estilo de aprendizaje VARK" : "Personalidad · Jung / Myers-Briggs";
    $("#assessmentDescription").textContent = state.kind === "VARK"
      ? "Cuéntanos quién eres para asociar tus respuestas a tu perfil."
      : "Reflexiona sobre tus preferencias personales. No existen respuestas correctas o incorrectas.";
    $("#assessmentSetup").hidden = false;
    $("#questionMount").hidden = true;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function chooseKind(kind) {
    state.kind = kind;
    $$(".assessment-choice").forEach((button) => button.classList.toggle("selected", button.dataset.choice === kind));
    updateQuestionnaires();
  }

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
      state.evaluationId = payload.evaluacion.id;
      state.answers = Array(state.questions.length).fill(null);
      state.currentQuestion = 0;
      form.hidden = true;
      $("#questionMount").hidden = false;
      renderQuestion();
    } catch (error) {
      showNotice(error.message);
    } finally {
      submit.disabled = !state.user;
      submit.innerHTML = 'Comenzar evaluación <span>→</span>';
    }
  }
  function renderQuestion() {
    const question = state.questions[state.currentQuestion];
    const mount = $("#questionMount");
    const multi = state.kind === "VARK";
    const selected = state.answers[state.currentQuestion] || [];
    const percent = Math.round(
      ((state.currentQuestion + 1) / state.questions.length) * 100
    );

    const progressHtml = `
      <div class="question-progress">
        <span>Pregunta ${state.currentQuestion + 1} de ${state.questions.length}</span>
        <span>${percent}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${percent}%"></div>
      </div>
      <h3 class="question-text">${escapeHtml(question.texto)}</h3>
    `;

    let answersHtml;

    if (multi) {
      answersHtml = `
        <p class="form-help">Puedes elegir más de una opción.</p>
        <div class="answer-list">
          ${question.opciones.map((option) => `
            <label class="answer-option">
              <input type="checkbox" name="answer" value="${option.id}"
                ${selected.includes(option.id) ? "checked" : ""}>
              <span>${escapeHtml(option.texto)}</span>
            </label>
          `).join("")}
        </div>
      `;
    } else {
      if (question.opciones.length !== 2) {
        showNotice(
          "Las preguntas de personalidad deben tener exactamente dos opciones."
        );
        return;
      }

      const first = question.opciones[0];
      const second = question.opciones[1];

      const savedPoints = Array.isArray(selected)
        ? selected.find((item) => item.opcion === first.id)?.puntos
        : undefined;

      const points = Number.isInteger(savedPoints) ? savedPoints : 7;

      answersHtml = `
        <p class="form-help">
          Distribuye 10 puntos entre las dos opciones.
          No se permite repartir 5 y 5.
        </p>

        <div class="personality-distribution">
          <div class="question-progress">
            <span>${escapeHtml(first.texto)}</span>
            <strong id="firstPoints">${points} puntos</strong>
          </div>

          <input
            type="range"
            id="personalitySlider"
            min="0"
            max="10"
            step="1"
            value="${points}"
            style="width:100%"
          >

          <div class="question-progress">
            <span>${escapeHtml(second.texto)}</span>
            <strong id="secondPoints">${10 - points} puntos</strong>
          </div>
        </div>
      `;
    }

    mount.innerHTML = `
      ${progressHtml}
      ${answersHtml}
      <div class="question-actions">
        <button type="button" data-action="previous"
          ${state.currentQuestion === 0 ? "disabled" : ""}>
          ← Anterior
        </button>
        <button type="button" data-action="next">
          ${state.currentQuestion === state.questions.length - 1
            ? "Finalizar"
            : "Siguiente →"}
        </button>
      </div>
    `;

    if (!multi) {
      const slider = $("#personalitySlider", mount);
      const updatePoints = () => {
        const points = Number(slider.value);
        $("#firstPoints", mount).textContent = `${points} puntos`;
        $("#secondPoints", mount).textContent = `${10 - points} puntos`;
      };

      slider.addEventListener("input", updatePoints);
    }

    mount.querySelector('[data-action="previous"]')
      .addEventListener("click", () => moveQuestion(-1));

    mount.querySelector('[data-action="next"]')
      .addEventListener("click", () => moveQuestion(1));
  }

  function moveQuestion(direction) {
    const mount = $("#questionMount");

    if (state.kind === "VARK") {
      const selected = $$('input[name="answer"]:checked', mount)
        .map((input) => Number(input.value));

      state.answers[state.currentQuestion] =
        selected.length ? selected : null;

      if (!selected.length && direction > 0) {
        showNotice("Selecciona al menos una respuesta para continuar.");
        return;
      }
    } else {
      const question = state.questions[state.currentQuestion];

      if (question.opciones.length !== 2) {
        showNotice(
          "Esta pregunta de personalidad no tiene exactamente dos opciones."
        );
        return;
      }

      const slider = $("#personalitySlider", mount);

      if (!slider) {
        showNotice("No se encontró el control de puntuación.");
        return;
      }

      const firstPoints = Number(slider.value);
      const secondPoints = 10 - firstPoints;

      if (!Number.isInteger(firstPoints) ||
          firstPoints < 0 ||
          firstPoints > 10) {
        showNotice("La distribución de puntos no es válida.");
        return;
      }

      if (firstPoints === 5 && direction > 0) {
        showNotice(
          "No puedes asignar 5 y 5 puntos. Debes inclinarte por una opción."
        );
        return;
      }

      state.answers[state.currentQuestion] = [
        {
          opcion: question.opciones[0].id,
          puntos: firstPoints,
        },
        {
          opcion: question.opciones[1].id,
          puntos: secondPoints,
        },
      ];
    }

    clearNotice();

    const next = state.currentQuestion + direction;

    if (next < 0) return;

    if (next === state.questions.length) {
      finishAssessment();
      return;
    }

    state.currentQuestion = next;
    renderQuestion();
  }


  function getInterpretation(scores) {
    if (state.kind === "VARK") {
      const vark = ["V", "A", "R", "K"].map((key) => ({ key, score: scores[key] || 0 })).sort((a, b) => b.score - a.score);
      const top = vark.filter((item) => item.score === vark[0].score).map((item) => labels[item.key]);
      return `Preferencia${top.length > 1 ? "s" : ""} más alta${top.length > 1 ? "s" : ""}: ${top.join(" y ")}. Este resultado es una guía de reflexión, no una etiqueta fija.`;
    }
    const pairs = [["E", "I"], ["S", "N"], ["T", "F"], ["J", "P"]];
    const type = pairs.map(([first, second]) => (scores[first] || 0) >= (scores[second] || 0) ? first : second).join("");
    return `Tendencia observada: ${type}. Es una síntesis orientativa de tus respuestas, no una evaluación clínica ni una descripción completa de tu personalidad.`;
  }

  async function finishAssessment() {
    const button = $('[data-action="next"]', $("#questionMount"));
    button.disabled = true;
    button.textContent = "Guardando…";
    try {
      const response = await api(`evaluaciones/${state.evaluationId}/responder/`, {
        method: "POST",
        body: JSON.stringify({
          respuestas: state.questions.map((question, index) => {
            if (state.kind === "PERSONALIDAD") {
              return {
                pregunta: question.id,
                selecciones: state.answers[index] || [],
              };
            }
            return {
              pregunta: question.id,
              opciones: state.answers[index] || [],
            };
          }),
          calcular: true,
        }),
      });
      const result = response.resultado;
      if (!result) throw new Error("La evaluación se guardó, pero el resultado no pudo calcularse.");
      showNotice("Tu evaluación quedó registrada. El resultado está disponible para consulta en Administración.", "success");
      $("#assessmentSetup").hidden = false;
      $("#questionMount").hidden = true;
      $("#assessmentSetup").reset();
      updateQuestionnaires();
    } catch (error) {
      showNotice(`No se pudo completar el guardado: ${error.message} Si la conexión se interrumpió, contacta al administrador antes de volver a enviar para evitar duplicados.`);
      button.disabled = false;
      button.textContent = "Reintentar guardado";
    }
  }

  function bindEvents() {
    $$("[data-route]").forEach((link) => link.addEventListener("click", (event) => {
      if (link.dataset.focus) chooseKind(link.dataset.focus);
      const target = link.dataset.route || link.getAttribute("href").slice(1);
      if (target) {
        event.preventDefault();
        history.pushState(null, "", `#${target}`);
        routeTo(target);
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
  }

  bindEvents();
  routeTo(location.hash.slice(1) || "inicio");
  loadData().catch((error) => {
    $("#connectionStatus").textContent = "Sin conexión";
    showNotice(`No fue posible conectar con la API. ${error.message}`);
  });
})();
