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

  function updateHeadings() {
    questions.querySelectorAll(".bru-builder-question").forEach((question, index) => {
      question.querySelector("[data-question-heading]").textContent = `Pregunta ${index + 1}`;
      question.querySelector('[data-builder-action="remove-question"]').setAttribute("aria-label", `Eliminar pregunta ${index + 1}`);
      question.querySelectorAll(".bru-builder-option").forEach((option, optionIndex) => {
        option.querySelector('[data-builder-action="remove-option"]').setAttribute("aria-label", `Eliminar opción ${optionIndex + 1} de la pregunta ${index + 1}`);
      });
    });
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

  function showPreview(draft) {
    previewContent.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = draft.titulo;
    previewContent.append(title);
    if (draft.instrucciones) {
      const instructions = document.createElement("p");
      instructions.textContent = draft.instrucciones;
      previewContent.append(instructions);
    }
    const list = document.createElement("ol");
    draft.preguntas.forEach((question) => {
      const item = document.createElement("li");
      const text = document.createElement("strong");
      text.textContent = question.texto;
      const options = document.createElement("ul");
      question.opciones.forEach((option) => {
        const row = document.createElement("li");
        row.textContent = option.texto;
        options.append(row);
      });
      item.append(text, options);
      list.append(item);
    });
    previewContent.append(list);
    preview.hidden = false;
    status.textContent = "Vista previa lista. El borrador todavía no está guardado en la base de datos.";
    preview.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  builder.addEventListener("input", () => {
    preview.hidden = true;
    status.textContent = "";
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
