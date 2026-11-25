(() => {
  const root = document.getElementById("bru-evaluation");
  if (!root) return;

  const exampleSelect = document.getElementById("bru-evaluation-example");
  const fileInput = document.getElementById("bru-evaluation-file");
  const status = document.getElementById("bru-evaluation-status");
  const form = document.getElementById("bru-evaluation-form");
  const title = document.getElementById("bru-evaluation-title");
  const instructions = document.getElementById("bru-evaluation-instructions");
  const questions = document.getElementById("bru-evaluation-questions");
  const result = document.getElementById("bru-evaluation-result");
  const resultContent = document.getElementById("bru-evaluation-result-content");
  const progressLabel = document.getElementById("bru-evaluation-progress-label");
  const progressBar = root.querySelector('[role="progressbar"]');
  const progressFill = document.getElementById("bru-evaluation-progress-fill");
  const labels = {
    V: "Visual", A: "Auditivo", R: "Lectura/Escritura", K: "Kinestésico",
    E: "Extroversión", I: "Introversión", S: "Sensación", N: "Intuición",
    T: "Pensamiento", F: "Sentimiento", J: "Juicio", P: "Percepción",
  };
  const validDimensions = { VARK: "VARK", PERSONALIDAD: "EISNTFJP" };
  let draft = null;
  let loadVersion = 0;

  function updateProgress() {
    const total = questions.children.length;
    const answered = Array.from(questions.children).filter((question) => question.querySelector("input:checked")).length;
    const percent = total ? Math.round((answered / total) * 100) : 0;
    progressLabel.textContent = `${answered} de ${total} preguntas respondidas`;
    progressBar.setAttribute("aria-valuenow", String(percent));
    progressBar.setAttribute("aria-valuetext", progressLabel.textContent);
    progressFill.style.width = `${percent}%`;
  }

  function validate(data) {
    if (!data || typeof data !== "object" || typeof data.titulo !== "string" ||
        !data.titulo.trim() || typeof data.tipo !== "string" || !Object.hasOwn(validDimensions, data.tipo) ||
        !Array.isArray(data.preguntas) || !data.preguntas.length) {
      return "El archivo debe contener un título, un tipo válido y al menos una pregunta.";
    }
    if (data.instrucciones !== undefined && typeof data.instrucciones !== "string") {
      return "Las instrucciones del cuestionario deben ser texto.";
    }
    for (const [index, question] of data.preguntas.entries()) {
      if (!question || typeof question.texto !== "string" || !question.texto.trim() ||
          !Array.isArray(question.opciones) || question.opciones.length < 2) {
        return `Completa el texto y al menos dos opciones de la pregunta ${index + 1}.`;
      }
      if (question.opciones.some((option) => !option || typeof option.texto !== "string" ||
          !option.texto.trim() || typeof option.dimension !== "string" ||
          option.dimension.length !== 1 || !validDimensions[data.tipo].includes(option.dimension))) {
        return `Revisa el texto y las dimensiones de la pregunta ${index + 1}.`;
      }
    }
    return "";
  }

  function loadQuestionnaire(data) {
    const error = validate(data);
    if (error) {
      status.textContent = error;
      return;
    }
    if (form.querySelector("input:checked") &&
        !window.confirm("Se reemplazarán las respuestas de esta prueba. ¿Deseas continuar?")) return;
    draft = data;
    title.textContent = data.titulo;
    instructions.textContent = data.instrucciones || (
      data.tipo === "VARK" ? "Puedes elegir más de una opción en cada pregunta." : "Elige una opción por pregunta."
    );
    questions.replaceChildren();
    data.preguntas.forEach((question, index) => {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "bru-evaluation-question";
      const legend = document.createElement("legend");
      legend.textContent = `${index + 1}. ${question.texto}`;
      fieldset.append(legend);
      question.opciones.forEach((option) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = data.tipo === "VARK" ? "checkbox" : "radio";
        input.name = `respuesta-${index}`;
        input.value = option.dimension;
        const text = document.createElement("span");
        text.textContent = option.texto;
        label.append(input, text);
        fieldset.append(label);
      });
      questions.append(fieldset);
    });
    result.hidden = true;
    form.hidden = false;
    updateProgress();
    status.textContent = "Cuestionario listo. Responde todas las preguntas para ver el perfil.";
  }

  document.getElementById("bru-evaluation-load").addEventListener("click", () => {
    loadVersion += 1;
    const examples = window.bruQuestionnaireExamples;
    if (!examples || !examples[exampleSelect.value]) {
      status.textContent = "No se pudo cargar el ejemplo. Recarga la página para intentarlo de nuevo.";
      return;
    }
    const example = examples[exampleSelect.value];
    loadQuestionnaire({
      titulo: example.title,
      tipo: exampleSelect.value,
      preguntas: example.questions.map((question) => ({
        texto: question.text,
        opciones: question.options.map(([texto, dimension]) => ({ texto, dimension })),
      })),
    });
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    const version = ++loadVersion;
    if (file.size > 2 * 1024 * 1024) {
      status.textContent = "El archivo es demasiado grande; usa un borrador de hasta 2 MB.";
      fileInput.value = "";
      return;
    }
    let text;
    try {
      text = await file.text();
    } catch (error) {
      if (version === loadVersion) status.textContent = `No se pudo leer el archivo: ${error.message}`;
      return;
    } finally {
      if (version === loadVersion) fileInput.value = "";
    }
    if (version !== loadVersion) return;
    let data;
    try {
      data = JSON.parse(text);
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      status.textContent = "El archivo no contiene un JSON válido.";
      return;
    }
    loadQuestionnaire(data);
  });

  form.addEventListener("change", () => {
    result.hidden = true;
    status.textContent = "";
    updateProgress();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!draft) return;
    const answers = new FormData(form);
    const counts = {};
    for (const [index] of draft.preguntas.entries()) {
      const selected = answers.getAll(`respuesta-${index}`);
      if (!selected.length) {
        status.textContent = `Responde la pregunta ${index + 1} para continuar.`;
        questions.children[index].querySelector("input").focus();
        result.hidden = true;
        return;
      }
      selected.forEach((dimension) => { counts[dimension] = (counts[dimension] || 0) + 1; });
    }
    resultContent.replaceChildren();
    if (draft.tipo === "VARK") {
      const highest = Math.max(...["V", "A", "R", "K"].map((key) => counts[key] || 0));
      const preferences = ["V", "A", "R", "K"].filter((key) => counts[key] === highest);
      const text = document.createElement("p");
      text.textContent = `Preferencia${preferences.length > 1 ? "s" : ""} más frecuente${preferences.length > 1 ? "s" : ""}: ${preferences.map((key) => labels[key]).join(", ")}.`;
      resultContent.append(text);
    } else {
      const list = document.createElement("ul");
      [["E", "I"], ["S", "N"], ["T", "F"], ["J", "P"]].forEach(([first, second]) => {
        const item = document.createElement("li");
        const a = counts[first] || 0;
        const b = counts[second] || 0;
        let preference;
        if (!a && !b) preference = "sin datos suficientes";
        else if (a === b) preference = "sin preferencia definida";
        else preference = labels[a > b ? first : second];
        item.textContent = `${labels[first]} / ${labels[second]}: ${preference}.`;
        list.append(item);
      });
      resultContent.append(list);
    }
    status.textContent = "Perfil calculado para el cuestionario completo. Esta prueba no se ha guardado.";
    result.hidden = false;
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
})();
