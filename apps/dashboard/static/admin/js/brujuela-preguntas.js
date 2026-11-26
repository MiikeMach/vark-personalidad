/*
 * «Editar cuestionario»: convierte la tabla de preguntas en tarjetas tipo formulario.
 * Cada tarjeta muestra la pregunta, debajo sus opciones (editables), «Agregar opción»
 * y «Eliminar pregunta». Las opciones se guardan con el formulario de pregunta que ya
 * existe en el panel (/admin/questionnaires/pregunta/…) justo antes de guardar el
 * cuestionario, por lo que no requiere cambios en el servidor.
 */
(() => {
  const group = document.getElementById("preguntas-group");
  const form = document.getElementById("cuestionario_form");
  const match = /\/questionnaires\/cuestionario\/(\d+)\/change\//.exec(window.location.pathname);
  if (!group || !form || !match) return;

  const questionnaireId = match[1];
  const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
  const typeSelect = document.getElementById("id_tipo");
  const DIMENSIONS = {
    VARK: [["V", "Visual"], ["A", "Auditivo"], ["R", "Lectura/Escritura"], ["K", "Kinestésico"]],
    PERSONALIDAD: [
      ["E", "Extroversión"], ["I", "Introversión"], ["S", "Sensación"], ["N", "Intuición"],
      ["T", "Pensamiento"], ["F", "Sentimiento"], ["J", "Juicio"], ["P", "Percepción"],
    ],
  };
  const PAIRS = ["EI", "SN", "TF", "JP"];
  const cards = new Map();  // fila (tr) -> { questionId, options: [...], snapshot, list, note }
  let optionsByQuestion = new Map();

  const type = () => (typeSelect && typeSelect.value) || "VARK";
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  group.classList.add("bru-question-cards");

  // ---------------------------------------------------------------- opciones
  function optionRow(card, option) {
    const item = el("li", "bru-card-option");
    item.dataset.dimension = option.dimension || "";
    const text = el("input");
    text.type = "text";
    text.value = option.texto || "";
    text.setAttribute("aria-label", "Texto de la opción");
    const select = el("select");
    select.setAttribute("aria-label", "Dimensión que suma la opción");
    select.append(new Option("Dimensión…", ""));
    DIMENSIONS[type()].forEach(([code, name]) => select.append(new Option(name, code)));
    if (option.dimension && !DIMENSIONS[type()].some(([code]) => code === option.dimension)) {
      select.append(new Option(option.dimension, option.dimension));  // Conserva valores de otro tipo.
    }
    select.value = option.dimension || "";
    const remove = el("button", "bru-card-option-remove");
    remove.type = "button";
    remove.innerHTML = '<span aria-hidden="true">×</span>';
    remove.title = "Quitar opción";
    remove.setAttribute("aria-label", "Quitar opción");

    text.addEventListener("input", () => { option.texto = text.value; });
    select.addEventListener("change", () => {
      option.dimension = select.value;
      item.dataset.dimension = select.value;
    });
    remove.addEventListener("click", () => {
      if (option.id) {
        option.deleted = true;
      } else {
        card.options.splice(card.options.indexOf(option), 1);
      }
      renderOptions(card);
    });
    item.append(el("span", "bru-card-choice"), text, select, remove);
    return item;
  }

  function renderOptions(card) {
    group.dataset.type = type();  // Casilla cuadrada (VARK) o redonda (personalidad).
    card.list.replaceChildren();
    const visible = card.options.filter((option) => !option.deleted);
    visible.forEach((option, index) => {
      const row = optionRow(card, option);
      row.querySelector("input").placeholder = `Opción ${index + 1}`;
      card.list.append(row);
    });
    card.add.hidden = type() === "PERSONALIDAD" && visible.length >= 2;
    card.count.textContent = `${visible.length} ${visible.length === 1 ? "opción" : "opciones"}`;
  }

  function addOption(card) {
    card.options.push({ id: "", texto: "", dimension: "" });
    renderOptions(card);
    card.list.querySelector("li:last-child input").focus();
  }

  // ---------------------------------------------------------------- tarjetas
  function setupRow(row) {
    if (cards.has(row) || row.classList.contains("empty-form") || !row.classList.contains("form-row")) return;
    const textCell = row.querySelector("td.field-texto");
    if (!textCell) return;
    const textarea = textCell.querySelector("textarea");
    if (textarea) {
      textarea.placeholder = "Escribe la pregunta";
      textarea.setAttribute("aria-label", "Texto de la pregunta");
    }
    const orderCell = row.querySelector("td.field-orden");
    if (orderCell && !orderCell.querySelector(".bru-card-label")) {
      orderCell.prepend(el("span", "bru-card-label", "Orden"));
    }

    // «Eliminar pregunta» en lugar de la casilla.
    const deleteCell = row.querySelector("td.delete");
    const checkbox = deleteCell && deleteCell.querySelector('input[type="checkbox"]');
    if (checkbox) {
      checkbox.hidden = true;
      const button = el("button", "bru-card-delete", "Eliminar pregunta");
      button.type = "button";
      button.addEventListener("click", () => {
        checkbox.checked = !checkbox.checked;
        row.classList.toggle("is-deleted", checkbox.checked);
        button.textContent = checkbox.checked ? "Deshacer" : "Eliminar pregunta";
      });
      deleteCell.append(button);
    }
    const newDeleteLink = deleteCell && deleteCell.querySelector(".inline-deletelink");
    if (newDeleteLink) newDeleteLink.textContent = "Eliminar pregunta";

    const idInput = row.querySelector('input[name^="preguntas-"][name$="-id"]');
    const questionId = idInput ? idInput.value : "";
    const options = (optionsByQuestion.get(questionId) || []).map((option) => ({ ...option }));
    const area = el("div", "bru-card-options");
    const list = el("ol", "bru-card-option-list");
    const add = el("button", "bru-card-add-option", "Agregar opción");
    add.type = "button";
    const count = el("span", "bru-card-count");
    const note = el("p", "bru-card-note");
    note.setAttribute("role", "status");
    area.append(list, add, note);
    textCell.append(area);
    if (deleteCell) deleteCell.prepend(count);  // Pie de la tarjeta: contador y «Eliminar pregunta».

    const card = { row, questionId, options, list, add, count, note, snapshot: JSON.stringify(options) };
    cards.set(row, card);
    add.addEventListener("click", () => addOption(card));
    if (!questionId && !options.length) {
      // Una pregunta nueva empieza con dos opciones vacías.
      options.push({ id: "", texto: "", dimension: "" }, { id: "", texto: "", dimension: "" });
    }
    renderOptions(card);
  }

  // Django agrega al final una pregunta vacía «extra». Se quita (ajustando el contador del
  // formulario) para que las preguntas nuevas se creen solo con «Agregar pregunta».
  function removeBlankExtraRows() {
    const total = group.querySelector('input[name="preguntas-TOTAL_FORMS"]');
    const initial = Number(group.querySelector('input[name="preguntas-INITIAL_FORMS"]').value);
    const rows = [...group.querySelectorAll("tbody tr.form-row:not(.empty-form):not(.has_original)")];
    rows.reverse().forEach((row) => {
      const index = Number(row.id.replace("preguntas-", ""));
      const blank = [...row.querySelectorAll("textarea, input:not([type=hidden])")].every((input) => !input.value);
      const isLast = index === Number(total.value) - 1;
      if (blank && isLast && index >= initial && !row.querySelector(".errorlist")) {
        row.remove();
        total.value = String(index);
      }
    });
  }

  function setupAll() {
    removeBlankExtraRows();
    group.querySelectorAll("tbody tr.form-row").forEach(setupRow);
  }

  // Las preguntas nuevas («Agregar pregunta») también se vuelven tarjetas, con orden sugerido.
  document.addEventListener("formset:added", (event) => {
    if (event.detail?.formsetName !== "preguntas") return;
    const row = event.target;
    const orders = [...group.querySelectorAll('td.field-orden input')]
      .map((input) => Number(input.value)).filter(Number.isFinite);
    const order = row.querySelector("td.field-orden input");
    if (order && !order.value) order.value = (orders.length ? Math.max(...orders) : 0) + 1;
    setupRow(row);
    row.querySelector("td.field-texto textarea")?.focus();
  });
  document.addEventListener("formset:removed", () => {
    [...cards.keys()].forEach((row) => { if (!row.isConnected) cards.delete(row); });
  });

  typeSelect?.addEventListener("change", () => cards.forEach(renderOptions));

  // ---------------------------------------------------------------- guardado
  function pendingJobs() {
    const jobs = [];
    cards.forEach((card) => {
      if (!card.row.isConnected || card.row.classList.contains("is-deleted")) return;
      const active = card.options.filter((option) => !option.deleted);
      const changed = JSON.stringify(card.options) !== card.snapshot;
      if (card.questionId ? changed : active.some((option) => option.texto.trim())) jobs.push(card);
    });
    return jobs;
  }

  function validate(card) {
    const active = card.options.filter((option) => !option.deleted && (option.texto.trim() || option.dimension || option.id));
    if (!card.questionId && !card.row.querySelector("td.field-texto textarea").value.trim()) {
      return "Escribe el texto de la pregunta.";
    }
    if (active.length < 2) return "Agrega al menos dos opciones.";
    if (active.some((option) => !option.texto.trim() || !option.dimension)) {
      return "Completa el texto y la dimensión de cada opción.";
    }
    const allowed = DIMENSIONS[type()].map(([code]) => code);
    if (active.some((option) => !allowed.includes(option.dimension))) {
      return "Hay opciones con una dimensión que no corresponde al tipo del cuestionario.";
    }
    if (type() === "PERSONALIDAD") {
      const [a, b] = active.map((option) => option.dimension);
      if (active.length !== 2 || a === b || !PAIRS.some((pair) => pair.includes(a) && pair.includes(b))) {
        return "En personalidad cada pregunta lleva dos opciones de polos opuestos (por ejemplo, Extroversión e Introversión).";
      }
    }
    return "";
  }

  function questionFormData(card) {
    const data = new FormData();
    const active = card.options.filter((option) => option.id || option.texto.trim());
    const existing = active.filter((option) => option.id);
    const created = active.filter((option) => !option.id);
    const usedOrders = existing.map((option) => Number(option.orden) || 0);
    let next = usedOrders.length ? Math.max(...usedOrders) : 0;
    data.append("csrfmiddlewaretoken", csrf);
    data.append("cuestionario", questionnaireId);
    data.append("orden", card.row.querySelector("td.field-orden input").value);
    data.append("texto", card.row.querySelector("td.field-texto textarea").value);
    data.append("opciones-TOTAL_FORMS", String(existing.length + created.length));
    data.append("opciones-INITIAL_FORMS", String(existing.length));
    data.append("opciones-MIN_NUM_FORMS", "0");
    data.append("opciones-MAX_NUM_FORMS", "1000");
    [...existing, ...created].forEach((option, index) => {
      const prefix = `opciones-${index}`;
      data.append(`${prefix}-id`, option.id || "");
      data.append(`${prefix}-pregunta`, card.questionId || "");
      // Las opciones existentes conservan su orden; las nuevas van al final (evita choques de orden).
      data.append(`${prefix}-orden`, String(option.id ? option.orden : (next += 1)));
      data.append(`${prefix}-texto`, option.texto);
      data.append(`${prefix}-dimension`, option.dimension);
      if (option.deleted) data.append(`${prefix}-DELETE`, "on");
    });
    data.append("_save", "Guardar");
    return data;
  }

  async function saveCard(card) {
    const url = card.questionId
      ? `/admin/questionnaires/pregunta/${card.questionId}/change/`
      : "/admin/questionnaires/pregunta/add/";
    const response = await fetch(url, {
      method: "POST",
      body: questionFormData(card),
      credentials: "same-origin",
      redirect: "manual",
    });
    if (response.type === "opaqueredirect" || response.status === 302) return "";
    if (response.status === 403) return "Tu cuenta no tiene permiso para modificar las opciones.";
    const html = new DOMParser().parseFromString(await response.text(), "text/html");
    const messages = [...html.querySelectorAll(".errorlist li")].map((item) => item.textContent.trim());
    return messages.length ? [...new Set(messages)].join(" ") : "No se pudieron guardar las opciones.";
  }

  form.addEventListener("submit", async (event) => {
    if (form.dataset.bruOptionsSaved === "true") return;
    const jobs = pendingJobs();
    if (!jobs.length) return;
    event.preventDefault();
    const submitter = event.submitter;
    cards.forEach((card) => { card.note.textContent = ""; card.row.classList.remove("has-error"); });

    let firstError = null;
    jobs.forEach((card) => {
      const error = validate(card);
      if (error) {
        card.note.textContent = error;
        card.row.classList.add("has-error");
        firstError = firstError || card.row;
      }
    });
    if (firstError) {
      firstError.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    const buttons = form.querySelectorAll('.submit-row input[type="submit"], .submit-row button');
    buttons.forEach((button) => { button.disabled = true; });
    for (const card of jobs) {
      card.note.textContent = "Guardando opciones…";
      const error = await saveCard(card);
      if (error) {
        card.note.textContent = error;
        card.row.classList.add("has-error");
        buttons.forEach((button) => { button.disabled = false; });
        card.row.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      card.note.textContent = "Opciones guardadas.";
      card.snapshot = JSON.stringify(card.options);
      // La pregunta nueva ya se creó con sus opciones: se quita del formulario para no duplicarla.
      if (!card.questionId) card.row.querySelector(".inline-deletelink")?.click();
    }
    buttons.forEach((button) => { button.disabled = false; });
    form.dataset.bruOptionsSaved = "true";
    if (submitter && submitter.form === form) form.requestSubmit(submitter);
    else form.requestSubmit();
  });

  // ---------------------------------------------------------------- inicio
  async function init() {
    try {
      const response = await fetch(`/api/cuestionarios/${questionnaireId}/completo/`, { credentials: "same-origin" });
      if (response.ok) {
        const data = await response.json();
        optionsByQuestion = new Map((data.preguntas || []).map((question) => [
          String(question.id),
          (question.opciones || [])
            .slice()
            .sort((a, b) => a.orden - b.orden)
            .map((option) => ({ id: String(option.id), texto: option.texto, dimension: option.dimension, orden: option.orden })),
        ]));
      }
    } catch (_) {
      // Sin la API se muestran las tarjetas sin opciones previas.
    }
    setupAll();
    const renameAdd = () => {
      const link = group.querySelector(".add-row a");
      if (link) link.textContent = "Agregar pregunta";
      return Boolean(link);
    };
    if (!renameAdd()) {
      const observer = new MutationObserver(() => { if (renameAdd()) observer.disconnect(); });
      observer.observe(group, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "complete") init();
  else window.addEventListener("load", init);
})();
