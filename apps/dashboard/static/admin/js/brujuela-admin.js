(() => {
  const isUserAdmin = document.body.classList.contains("app-auth") &&
    document.body.classList.contains("model-user");
  if (isUserAdmin) {
    const appLink = document.querySelector(".breadcrumbs a[href$='/auth/']");
    if (appLink) appLink.textContent = "Usuarios y acceso";
  }

  const sidebar = document.getElementById("nav-sidebar");
  if (sidebar) {
    const menuButton = document.createElement("button");
    menuButton.type = "button";
    menuButton.className = "bru-mobile-nav-toggle";
    menuButton.textContent = "☰  Menú de gestión";
    menuButton.setAttribute("aria-controls", "nav-sidebar");
    menuButton.setAttribute("aria-expanded", "false");
    sidebar.before(menuButton);
    sidebar.parentElement.classList.add("bru-mobile-nav-ready");
    menuButton.addEventListener("click", () => {
      const open = sidebar.parentElement.classList.toggle("bru-mobile-nav-open");
      menuButton.setAttribute("aria-expanded", String(open));
      menuButton.textContent = open ? "✕  Cerrar menú" : "☰  Menú de gestión";
    });
  }

  const search = document.getElementById("searchbar");
  if (search) {
    search.placeholder = "Buscar registros";
    search.setAttribute("aria-label", "Buscar registros");
  }
  const selectionDetails = document.getElementById("bru-selection-details");
  if (selectionDetails) {
    if (search) {
      search.placeholder = "Nombre del estudiante u opción";
      search.setAttribute("aria-label", "Buscar por nombre del estudiante u opción");
    }
    const rows = document.querySelectorAll("#result_list tbody tr");
    const details = selectionDetails.content.children;
    if (rows.length === details.length) {
      rows.forEach((row, index) => {
        details[index].querySelectorAll("[data-column]").forEach((detail) => {
          const cell = row.querySelector(`.field-${detail.dataset.column}`);
          if (cell) cell.append(detail.cloneNode(true));
        });
      });
    }
  }
  const filterMenus = document.querySelectorAll("#changelist-filter details");
  function closeFilterMenus(except = null) {
    filterMenus.forEach((menu) => {
      if (menu !== except) menu.open = false;
    });
  }
  window.addEventListener("pageshow", () => closeFilterMenus());
  document.addEventListener("click", (event) => {
    closeFilterMenus(event.target.closest("#changelist-filter details"));
  });
  const listForm = document.querySelector(".change-list .changelist-form-container");
  if (listForm && !listForm.querySelector("#result_list")) {
    const emptyMessage = document.createElement("p");
    emptyMessage.className = "bru-empty-results";
    emptyMessage.textContent = "No hay registros para mostrar. Prueba otra búsqueda o cambia los filtros.";
    const paginator = listForm.querySelector(".paginator");
    if (paginator) paginator.before(emptyMessage);
  }

  const userSelect = document.getElementById("id_usuario");
  if (userSelect) {
    const container = document.createElement("div");
    container.className = "bru-user-picker";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Buscar por nombre o usuario";
    input.setAttribute("aria-label", "Buscar usuario por nombre o nombre de usuario");
    const status = document.createElement("span");
    status.className = "bru-user-search-status";
    status.setAttribute("role", "status");
    userSelect.before(container);
    container.append(input, userSelect, status);
    const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    input.addEventListener("input", () => {
      const query = normalize(input.value.trim());
      let matches = 0;
      Array.from(userSelect.options).forEach((option) => {
        if (!option.value) return;
        const match = normalize(option.textContent).includes(query);
        if (match) matches += 1;
        option.hidden = !match && !option.selected;
      });
      status.textContent = query ? `${matches} usuario(s) encontrado(s).` : "";
    });
  }

  const permissionModels = {
    "entrada de registro|log entry": "registro de actividad",
    "evaluación|evaluación": "evaluaciones",
    "respuesta|respuesta": "respuestas",
    "seleccion respuesta|seleccion respuesta": "opciones seleccionadas",
    "grupo|group": "roles",
    "permiso|permission": "permisos",
    "usuario|user": "usuarios",
    "tipo de contenido|content type": "tipos de contenido",
    "cuestionario|cuestionario": "cuestionarios",
    "opcion|opcion": "opciones",
    "pregunta|pregunta": "preguntas",
    "puntaje dimension|puntaje dimension": "puntajes por dimensión",
    "resultado|resultado": "resultados",
    "período de sesiones|session": "sesiones",
    "estudiante|estudiante": "estudiantes",
    "grupo|grupo": "grupos escolares",
  };
  const permissionActions = {
    add: "Agregar",
    change: "Modificar",
    delete: "Eliminar",
    view: "Ver",
  };
  function describePermission(text) {
    const parts = text.split(" | ");
    if (parts.length !== 3) return text;
    const match = /^Can (add|change|delete|view) (.+)$/.exec(parts[2]);
    if (!match) return text;
    const model = permissionModels[`${parts[1].toLowerCase()}|${match[2].toLowerCase()}`];
    if (!model) return text;
    const app = isUserAdmin && parts[0] === "Autenticación y Autorización"
      ? "Usuarios y acceso" : parts[0];
    return `${permissionActions[match[1]]} ${model} — ${app}`;
  }

  document.querySelectorAll("#id_permissions option, #id_user_permissions option").forEach((option) => {
    option.textContent = describePermission(option.textContent);
  });

  const templatePanel = document.getElementById("bru-user-template-preview");
  if (templatePanel) {
    const templates = JSON.parse(document.getElementById("bru-user-templates-data").textContent);
    const select = document.getElementById("id_rol");
    const description = document.getElementById("bru-user-template-description");
    const access = document.getElementById("bru-user-template-access");
    const status = document.getElementById("bru-user-template-status");
    const list = document.getElementById("bru-user-template-permissions");
    if (select) {
      templatePanel.hidden = false;
      // Coloca el panel justo debajo de la lista desplegable del rol.
      const row = select.closest(".form-row");
      if (row) row.after(templatePanel);
    }

    const render = () => {
      const template = select && templates.find((item) => item.key === select.value);
      list.replaceChildren();
      if (!template) {
        description.textContent = "Elige un rol para ver sus permisos.";
        access.textContent = "";
        status.textContent = "";
        return;
      }
      description.textContent = `${template.name}: ${template.description}` +
        (template.exists ? "" : " El rol se creará al guardar.");
      access.textContent = template.staff
        ? "Podrá entrar al panel administrativo."
        : "No tendrá acceso al panel administrativo.";
      if (template.all_permissions) {
        status.textContent = "Incluye todos los permisos de administración.";
      } else if (!template.permissions.length) {
        status.textContent = "Este rol no tiene permisos de administración.";
      } else {
        status.textContent = `${template.permissions.length} permiso(s) del rol:`;
        template.permissions.forEach((permission) => {
          const item = document.createElement("li");
          item.textContent = describePermission(permission);
          list.append(item);
        });
      }
    };
    if (select) select.addEventListener("change", render);
    render();
  }

  // Tablas de preguntas y opciones dentro de un cuestionario o una pregunta.
  function improveInlineTables() {
    const inlineTexts = {
      // Las preguntas del cuestionario usan tarjetas propias (brujuela-preguntas.js).
      opciones: { link: "Editar", add: "Agregar opción" },
    };
    Object.entries(inlineTexts).forEach(([prefix, texts]) => {
      const group = document.getElementById(`${prefix}-group`);
      if (!group) return;
      group.classList.add("bru-inline-questions");
      group.querySelectorAll("td.original p").forEach((paragraph) => {
        // Quita el texto técnico («Pregunta 1 - …») y deja solo el enlace.
        paragraph.childNodes.forEach((node) => {
          if (node.nodeType === Node.TEXT_NODE) node.textContent = "";
        });
        const link = paragraph.querySelector("a.inlinechangelink");
        if (link) {
          link.textContent = texts.link;
          link.classList.add("bru-inline-edit");
        }
      });
      // Django crea el enlace «Agregar otro/a …» al cargar; se renombra cuando aparece.
      const renameAddLink = () => {
        const addLink = group.querySelector(".add-row a");
        if (addLink && addLink.textContent !== texts.add) addLink.textContent = texts.add;
        return Boolean(addLink);
      };
      if (!renameAddLink()) {
        const observer = new MutationObserver(() => {
          if (renameAddLink()) observer.disconnect();
        });
        observer.observe(group, { childList: true, subtree: true });
      }
    });
  }

  window.addEventListener("load", () => {
    improveInlineTables();
    ["id_permissions", "id_user_permissions"].forEach((id) => {
      const available = document.querySelector(`#${id}_from_title label`);
      const selected = document.querySelector(`#${id}_to_title label`);
      if (available) available.textContent = "Permisos disponibles";
      if (selected) selected.textContent = "Permisos asignados";
    });

    const presetPanel = document.querySelector(".bru-role-presets");
    if (!presetPanel) return;

    const roleSelect = document.getElementById("bru-role-preset");
    const status = document.getElementById("bru-role-preset-status");
    const reviewStatus = document.getElementById("bru-role-review-status");
    const permissionList = document.getElementById("bru-role-permission-list");
    const from = document.getElementById("id_permissions_from");
    const to = document.getElementById("id_permissions_to");
    if (!from || !to || !window.SelectBox || !window.SelectFilter) {
      presetPanel.hidden = false;
      roleSelect.disabled = true;
      status.textContent = "No se pudieron cargar las plantillas. Recarga la página o utiliza el formulario de permisos.";
      return;
    }

    const presetData = document.getElementById("bru-role-templates-data");
    const presets = Object.fromEntries(
      (presetData ? JSON.parse(presetData.textContent) : []).map((item) => [item.key, {
        name: item.name, all: item.all, permissions: item.permission_ids,
      }])
    );
    const availableIds = new Set(
      [...window.SelectBox.cache[from.id], ...window.SelectBox.cache[to.id]].map((option) => option.value)
    );
    const isAdd = presetPanel.dataset.add === "true";
    const name = document.getElementById("id_name");
    const nameRow = name && name.closest(".form-row");
    const permissionsRow = to.closest(".form-row");
    const form = presetPanel.closest("form");
    const originalPermissions = window.SelectBox.cache[to.id].map((option) => option.value);
    const originalName = name ? name.value : "";
    let appliedRole = "";

    function updatePermissionReview() {
      const permissions = window.SelectBox.cache[to.id];
      permissionList.replaceChildren();
      if (!permissions.length) {
        reviewStatus.textContent = isAdd && !appliedRole
          ? "Elige una plantilla para ver sus permisos."
          : "Este rol no tiene permisos de administración.";
        return;
      }
      reviewStatus.textContent = `${permissions.length} permiso(s) del rol:`;
      permissions.forEach((permission) => {
        const item = document.createElement("li");
        item.textContent = permission.text;
        permissionList.append(item);
      });
    }

    function selectPermissions(ids, all = false) {
      document.getElementById("id_permissions_input").value = "";
      document.getElementById("id_permissions_selected_input").value = "";
      window.SelectBox.filter(from.id, "");
      window.SelectBox.filter(to.id, "");
      window.SelectBox.move_all(to.id, from.id);
      if (all) {
        window.SelectBox.move_all(from.id, to.id);
      } else {
        const desiredIds = new Set(ids);
        for (const option of from.options) option.selected = desiredIds.has(option.value);
        window.SelectBox.move(from.id, to.id);
      }
      window.SelectFilter.refresh_icons("id_permissions");
      window.SelectFilter.refresh_filtered_warning("id_permissions");
    }

    presetPanel.hidden = false;
    if (permissionsRow && !permissionsRow.querySelector(".errorlist")) {
      permissionsRow.classList.add("bru-role-fields-hidden");
    }
    if (isAdd && nameRow && !nameRow.querySelector(".errorlist")) {
      nameRow.classList.add("bru-role-fields-hidden");
    }
    updatePermissionReview();
    roleSelect.addEventListener("change", () => {
      const preset = presets[roleSelect.value];
      if (!preset) {
        if (appliedRole) {
          selectPermissions(originalPermissions);
          if (isAdd && name) name.value = originalName;
          appliedRole = "";
          status.textContent = isAdd
            ? "Selecciona una plantilla antes de guardar."
            : "Se conservarán los permisos originales al guardar.";
          updatePermissionReview();
        }
        return;
      }

      const desired = [];
      if (!preset.all) {
        for (const id of preset.permissions) {
          if (!availableIds.has(id)) {
            status.textContent = "No se encontró un permiso requerido por la plantilla. No se modificó la selección.";
            roleSelect.value = appliedRole;
            return;
          }
          desired.push(id);
        }
      }

      const selectedCount = window.SelectBox.cache[to.id].length;
      if (selectedCount && !window.confirm("Esta plantilla reemplazará los permisos del rol. Al guardar, el cambio afectará a todas sus cuentas. ¿Deseas continuar?")) {
        roleSelect.value = appliedRole;
        return;
      }

      selectPermissions(desired, preset.all);

      if (isAdd && name && (!name.value.trim() || !nameRow || !nameRow.querySelector(".errorlist"))) {
        name.value = preset.name;
      }
      appliedRole = roleSelect.value;
      const count = window.SelectBox.cache[to.id].length;
      status.textContent = `Plantilla ${preset.name} seleccionada (${count} permisos). Pulsa Guardar para aplicar los cambios.`;
      updatePermissionReview();
    });
    form.addEventListener("submit", (event) => {
      if (isAdd && !appliedRole) {
        event.preventDefault();
        status.textContent = "Selecciona una plantilla antes de guardar.";
        roleSelect.focus();
      }
    });
  });

  let relatedOpener = null;
  const backLink = document.querySelector(".bru-site-link");
  if (backLink) {
    backLink.addEventListener("click", (event) => {
      if (window.history.length > 1) {
        event.preventDefault();
        window.history.back();
      }
    });
  }

  function closeRelatedModal(frame) {
    const modal = document.querySelector(".bru-related-modal");
    if (!modal || (frame && modal.querySelector("iframe") !== frame)) return;
    modal.remove();
    document.body.classList.remove("bru-modal-open");
    if (relatedOpener && relatedOpener.isConnected) relatedOpener.focus();
    relatedOpener = null;
  }

  function wrapPopupCallback(name) {
    const callback = window[name];
    if (typeof callback !== "function" || callback.brujuelaWrapped) return;

    const wrapped = function (popupWindow, ...args) {
      const result = callback.call(this, popupWindow, ...args);
      const modal = document.querySelector(".bru-related-modal");
      if (modal && modal.querySelector("iframe").contentWindow === popupWindow) {
        closeRelatedModal(modal.querySelector("iframe"));
      }
      return result;
    };
    wrapped.brujuelaWrapped = true;
    window[name] = wrapped;
  }

  [
    "dismissAddRelatedObjectPopup",
    "dismissChangeRelatedObjectPopup",
    "dismissDeleteRelatedObjectPopup",
  ].forEach(wrapPopupCallback);

  function openRelatedModal(link) {
    const existing = document.querySelector(".bru-related-modal");
    if (existing) existing.remove();

    const modal = document.createElement("div");
    modal.className = "bru-related-modal";
    modal.setAttribute("role", "presentation");

    const dialog = document.createElement("section");
    dialog.className = "bru-related-modal-dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", link.title || "Agregar registro relacionado");

    const heading = document.createElement("h2");
    heading.textContent = link.title || "Agregar registro relacionado";

    const closeButton = document.createElement("button");
    closeButton.className = "bru-related-modal-close";
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Cerrar formulario");
    closeButton.textContent = "×";

    const header = document.createElement("header");
    header.className = "bru-related-modal-header";
    header.append(heading, closeButton);

    const frame = document.createElement("iframe");
    frame.className = "bru-related-modal-frame";
    frame.title = link.title || "Formulario de registro relacionado";
    frame.name = getPopupName(link);

    dialog.append(header, frame);
    modal.append(dialog);
    document.body.append(modal);
    document.body.classList.add("bru-modal-open");
    relatedOpener = link;

    const close = () => closeRelatedModal(frame);
    closeButton.addEventListener("click", close);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close();
    });

    const target = new URL(link.href, window.location.href);
    target.searchParams.set("_popup", "1");
    frame.src = target.toString();
    closeButton.focus();
  }

  window.addEventListener("message", (event) => {
    const modal = document.querySelector(".bru-related-modal");
    const frame = modal && modal.querySelector("iframe");
    const response = event.data;
    if (
      event.origin !== window.location.origin ||
      !frame ||
      event.source !== frame.contentWindow ||
      !response
    ) return;

    if (response.type === "brujuela-admin-popup-close") {
      closeRelatedModal(frame);
      return;
    }
    if (response.type !== "brujuela-admin-popup-response") return;

    const callbacks = {
      add: "dismissAddRelatedObjectPopup",
      change: "dismissChangeRelatedObjectPopup",
      delete: "dismissDeleteRelatedObjectPopup",
    };
    const callback = window[callbacks[response.action] || ""];
    if (typeof callback !== "function") return;

    const popupWindow = {
      name: response.name,
      location: new URL(frame.src),
      close: () => closeRelatedModal(frame),
    };
    if (response.action === "add") {
      callback(popupWindow, response.value, response.obj);
    } else if (response.action === "change") {
      callback(popupWindow, response.value, response.obj, response.new_value);
    } else if (response.action === "delete") {
      callback(popupWindow, response.value);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (document.querySelector(".bru-related-modal")) {
      closeRelatedModal();
    } else if (window.parent !== window && document.querySelector('input[name="_popup"]')) {
      window.parent.postMessage({ type: "brujuela-admin-popup-close" }, window.location.origin);
    } else {
      const openFilter = document.querySelector("#changelist-filter details[open]");
      if (openFilter) {
        closeFilterMenus();
        openFilter.querySelector("summary").focus();
      }
    }
  });

  function getPopupName(link) {
    const isPopup = document.querySelector('input[name="_popup"]');
    let index = 0;
    if (isPopup) {
      const suffix = window.name.slice(window.name.lastIndexOf("__") + 2);
      const parsed = Number.parseInt(suffix, 10);
      if (Number.isFinite(parsed)) index = parsed;
    }
    return `${link.id.replace(/^(add|change|delete)_/, "")}__${index + 1}`;
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest(".related-widget-wrapper-link.add-related[data-popup='yes']");
    if (!link || !link.href) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openRelatedModal(link);
  }, true);
})();
