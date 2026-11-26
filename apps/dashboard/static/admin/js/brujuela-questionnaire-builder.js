(() => {
  const builder = document.getElementById("bru-questionnaire-builder");
  const legacy = document.getElementById("bru-questionnaire-legacy");
  if (!builder || !legacy) return;

  const fields = {
    title: builder.querySelector('[data-builder-field="title"]'),
    type: builder.querySelector('[data-builder-field="type"]'),
    description: builder.querySelector('[data-builder-field="description"]'),
    instructions: builder.querySelector('[data-builder-field="instructions"]'),
  };
  const questions = builder.querySelector("[data-builder-questions]");
  const questionTemplate = document.getElementById("bru-question-template");
  const optionTemplate = document.getElementById("bru-option-template");
  const status = builder.querySelector("[data-builder-status]");
  const preview = builder.querySelector("[data-builder-preview]");
  const previewContent = builder.querySelector("[data-builder-preview-content]");
  const dimensions = { VARK: "VARK", PERSONALIDAD: "EISNTFJP" };
  const examples = window.bruQuestionnaireExamples;

  const summary = builder.querySelector("[data-builder-summary]");
  const typeHint = builder.querySelector("[data-builder-type-hint]");
  const hints = {
    VARK: "Asigna una dimensión VARK a cada opción. El estudiante podrá elegir varias.",
    PERSONALIDAD: "Usa exactamente dos opciones de polos opuestos (por ejemplo, Extroversión e Introversión). El estudiante repartirá 10 puntos entre ellas.",
  };

  // Numeración, contadores, ayudas y dimensiones según el tipo de cuestionario.
  function updateHeadings() {
    const type = fields.type.value;
    const isPersonality = type === "PERSONALIDAD";
    let totalOptions = 0;
    builder.dataset.type = type;  // Casilla cuadrada (VARK) o redonda (personalidad).
    if (typeHint) typeHint.textContent = hints[type] || "";
    const allQuestions = questions.querySelectorAll(".bru-builder-question");
    allQuestions.forEach((question, index) => {
      const options = question.querySelectorAll(".bru-builder-option");
      totalOptions += options.length;
      question.querySelector("[data-question-heading]").textContent = `Pregunta ${index + 1}`;
      question.querySelector("[data-question-number]").textContent = index + 1;
      question.querySelector("[data-question-count]").textContent =
        `${options.length} ${options.length === 1 ? "opción" : "opciones"}`;
      question.querySelector("[data-options-hint]").textContent = isPersonality
        ? "Dos opciones de polos opuestos"
        : "El estudiante puede elegir varias";
      question.querySelector('[data-builder-action="remove-question"]').setAttribute("aria-label", `Eliminar pregunta ${index + 1}`);
      // En personalidad cada pregunta lleva solo dos opciones.
      question.querySelector('[data-builder-action="add-option"]').hidden = isPersonality && options.length >= 2;
      options.forEach((option, optionIndex) => {
        option.querySelector("[data-option-text]").placeholder = `Opción ${optionIndex + 1}`;
        option.querySelector('[data-builder-action="remove-option"]').setAttribute("aria-label", `Eliminar opción ${optionIndex + 1} de la pregunta ${index + 1}`);
        option.querySelector("[data-option-text]").setAttribute("aria-label", `Texto de la opción ${optionIndex + 1} de la pregunta ${index + 1}`);
        const select = option.querySelector("[data-option-dimension]");
        select.querySelectorAll("optgroup").forEach((group) => {
          const other = group.dataset.type !== type;
          group.hidden = other;
          group.disabled = other && !group.querySelector(`option[value="${select.value}"]`);
        });
        option.dataset.dimension = select.value;
      });
    });
    questions.querySelectorAll("[data-question-text]").forEach(autosize);
    if (summary) {
      summary.textContent = `${allQuestions.length} ${allQuestions.length === 1 ? "pregunta" : "preguntas"} · ${totalOptions} ${totalOptions === 1 ? "opción" : "opciones"}`;
    }
  }

  function addOption(question, text = "", dimension = "") {
    const option = optionTemplate.content.firstElementChild.cloneNode(true);
    option.querySelector("[data-option-text]").value = text;
    option.querySelector("[data-option-dimension]").value = dimension;
    question.querySelector("[data-question-options]").append(option);
    updateHeadings();
  }

  function addQuestion(data = null) {
    const question = questionTemplate.content.firstElementChild.cloneNode(true);
    question.querySelector("[data-question-text]").value = data ? data.text : "";
    questions.append(question);
    if (data) {
      data.options.forEach(([text, dimension]) => addOption(question, text, dimension));
    } else {
      addOption(question);
      addOption(question);
    }
    updateHeadings();
    return question;
  }

  function readDraft() {
    return {
      titulo: fields.title.value.trim(),
      tipo: fields.type.value,
      descripcion: fields.description.value.trim(),
      instrucciones: fields.instructions.value.trim(),
      preguntas: Array.from(questions.querySelectorAll(".bru-builder-question"), (question) => ({
        texto: question.querySelector("[data-question-text]").value.trim(),
        opciones: Array.from(question.querySelectorAll(".bru-builder-option"), (option) => ({
          texto: option.querySelector("[data-option-text]").value.trim(),
          dimension: option.querySelector("[data-option-dimension]").value,
        })),
      })),
    };
  }

  function validate(draft) {
    if (!draft.titulo) return "Escribe un título para el cuestionario.";
    if (!draft.preguntas.length) return "Agrega al menos una pregunta.";
    for (const [index, question] of draft.preguntas.entries()) {
      if (!question.texto) return `Escribe el texto de la pregunta ${index + 1}.`;
      if (question.opciones.length < 2) return `Agrega al menos dos opciones a la pregunta ${index + 1}.`;
      for (const [optionIndex, option] of question.opciones.entries()) {
        if (!option.texto || !option.dimension) {
          return `Completa el texto y la dimensión de la opción ${optionIndex + 1} en la pregunta ${index + 1}.`;
        }
        if (!dimensions[draft.tipo].includes(option.dimension)) {
          return `La dimensión de la opción ${optionIndex + 1} en la pregunta ${index + 1} no corresponde al tipo elegido.`;
        }
      }
    }
    return "";
  }

  function checkedDraft() {
    const draft = readDraft();
    const error = validate(draft);
    if (error) {
      status.textContent = error;
      preview.hidden = true;
      return null;
    }
    return draft;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Vista previa con el aspecto del formulario que contesta el estudiante (no guarda nada).
  function showPreview(draft) {
    previewContent.replaceChildren();
    const isPersonality = draft.tipo === "PERSONALIDAD";
    const form = element("form", "bru-preview-form");
    form.addEventListener("submit", (event) => event.preventDefault());

    const header = element("header", "bru-preview-header");
    header.append(
      element("span", "bru-preview-type", isPersonality ? "Personalidad" : "VARK · Estilos de aprendizaje"),
      element("h3", "", draft.titulo),
    );
    if (draft.descripcion) header.append(element("p", "", draft.descripcion));
    if (draft.instrucciones) header.append(element("p", "bru-preview-instructions", draft.instrucciones));
    header.append(element("small", "", `${draft.preguntas.length} ${draft.preguntas.length === 1 ? "pregunta" : "preguntas"}`));
    form.append(header);

    draft.preguntas.forEach((question, index) => {
      const card = element("fieldset", "bru-preview-question");
      card.append(element("legend", "", `${index + 1}. ${question.texto}`));
      if (isPersonality && question.opciones.length === 2) {
        card.append(element("p", "bru-preview-help", "Reparte 10 puntos entre las dos opciones (no se permite 5 y 5)."));
        const row = element("div", "bru-preview-points");
        const label = element("label", "", `Puntos para «${question.opciones[0].texto}»`);
        const select = element("select");
        select.append(new Option("Selecciona", ""));
        [0, 1, 2, 3, 4, 6, 7, 8, 9, 10].forEach((points) => select.append(new Option(String(points), String(points))));
        const other = element("p", "bru-preview-help", `Puntos para «${question.opciones[1].texto}»: pendientes.`);
        select.addEventListener("change", () => {
          other.textContent = select.value === ""
            ? `Puntos para «${question.opciones[1].texto}»: pendientes.`
            : `Puntos para «${question.opciones[1].texto}»: ${10 - Number(select.value)}.`;
        });
        label.append(select);
        row.append(label, other);
        card.append(row);
      } else {
        card.append(element("p", "bru-preview-help", "Puedes elegir más de una opción."));
        question.opciones.forEach((option) => {
          const label = element("label", "bru-preview-option");
          const input = element("input");
          input.type = "checkbox";
          input.name = `preview-${index}`;
          label.append(input, element("span", "", option.texto));
          card.append(label);
        });
      }
      form.append(card);
    });
    const submit = element("button", "bru-builder-primary", "Finalizar");
    submit.type = "submit";
    submit.disabled = true;
    submit.title = "Solo vista previa";
    form.append(submit);
    previewContent.append(form);
    preview.hidden = false;
    status.textContent = "Vista previa lista. Así lo verá el estudiante; el borrador todavía no está guardado.";
    preview.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // El texto de la pregunta crece con lo que se escribe, como en un formulario.
  function autosize(textarea) {
    if (textarea.offsetParent === null) return;  // Aún oculto: se mide al mostrarse.
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }
  builder.addEventListener("input", (event) => {
    if (preview.contains(event.target)) return;  // Contestar la vista previa no cambia el borrador.
    if (event.target.matches("[data-question-text]")) autosize(event.target);
    preview.hidden = true;
    status.textContent = "";
  });
  builder.addEventListener("change", (event) => {
    if (event.target === fields.type || event.target.matches("[data-option-dimension]")) updateHeadings();
  });
  builder.addEventListener("click", (event) => {
    const button = event.target.closest("[data-builder-action]");
    if (!button) return;
    const action = button.dataset.builderAction;
    const question = button.closest(".bru-builder-question");
    if (action === "add-question") {
      addQuestion().querySelector("[data-question-text]").focus();
      preview.hidden = true;
      status.textContent = "";
    } else if (action === "add-option") {
      addOption(question);
      question.querySelector("[data-question-options] .bru-builder-option:last-child input").focus();
      preview.hidden = true;
      status.textContent = "";
    } else if (action === "remove-question") {
      if (questions.children.length === 1) {
        status.textContent = "Mantén al menos una pregunta.";
      } else if (window.confirm("¿Eliminar esta pregunta y sus opciones del borrador?")) {
        question.remove();
        updateHeadings();
        preview.hidden = true;
        status.textContent = "Pregunta eliminada del borrador.";
      }
    } else if (action === "remove-option") {
      const options = question.querySelectorAll(".bru-builder-option");
      if (options.length <= 2) {
        status.textContent = "Mantén al menos dos opciones por pregunta.";
      } else if (window.confirm("¿Eliminar esta opción del borrador?")) {
        button.closest(".bru-builder-option").remove();
        updateHeadings();
        preview.hidden = true;
        status.textContent = "Opción eliminada del borrador.";
      }
    } else if (action === "example") {
      if (!examples) {
        status.textContent = "No se pudieron cargar los ejemplos. Recarga la página para intentarlo de nuevo.";
        return;
      }
      const draft = readDraft();
      const hasContent = draft.titulo || draft.descripcion || draft.instrucciones ||
        draft.preguntas.some((item) => item.texto || item.opciones.some((option) => option.texto || option.dimension));
      if (hasContent && !window.confirm("El ejemplo reemplazará el borrador actual. ¿Deseas continuar?")) return;
      const example = examples[fields.type.value];
      fields.title.value = example.title;
      fields.description.value = "Ejemplo ficticio para mostrar la interfaz; no es un instrumento validado.";
      fields.instructions.value = "Selecciona la opción que mejor describa tu preferencia.";
      questions.replaceChildren();
      example.questions.forEach(addQuestion);
      updateHeadings();
      preview.hidden = true;
      status.textContent = "Ejemplo ficticio cargado. Puedes modificarlo antes de revisarlo.";
    } else if (action === "preview") {
      const draft = checkedDraft();
      if (!draft) return;
      showPreview(draft);
    }
  });
  addQuestion();
  if (builder.dataset.hasErrors !== "true") {
    legacy.hidden = true;
    builder.hidden = false;
  }
})();
