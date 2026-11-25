document.addEventListener("DOMContentLoaded", () => {
    let contadorBackspace = 0;

    // Función auxiliar para enviar eventos de teclado al servidor
    function registrarEventoEditor(tipoEvento, cantidad) {
        fetch('/api/telemetria', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_pregunta: typeof idPreguntaActual !== 'undefined' ? idPreguntaActual : 1,
                tipo_evento: tipoEvento,
                cantidad_caracteres: cantidad
            })
        }).catch(err => console.error("Error telemetría:", err));
    }

    // --- 1. CRONÓMETRO, VALIDACIÓN Y LÓGICA PARA FINALIZAR REACTIVO ---
    const btnFinalizar = document.getElementById("btn-enviar-codigo");
    if (btnFinalizar) {
        const tiempoInicio = Date.now();
        let enviandoFinal = false;

        btnFinalizar.addEventListener("click", () => {
            if (enviandoFinal) return;

            try {
                let codigoFinal = "";
                if (typeof tipoPregunta !== 'undefined') {
                    if (tipoPregunta === 1) {
                        const seleccion = document.querySelector('input[name="respuesta_t1"]:checked');
                        if (!seleccion) {
                            alert("Selecciona una opción antes de finalizar este reactivo.");
                            return;
                        }
                        codigoFinal = seleccion.value;
                    } else if (tipoPregunta === 2) {
                        const editor = document.getElementById("editor-codigo");
                        codigoFinal = editor ? editor.value : "";
                        if (codigoFinal.trim() === "") {
                            alert("Escribe tu solución antes de finalizar este reactivo.");
                            return;
                        }
                    } else if (tipoPregunta === 3) {
                        const bloques = document.querySelectorAll("#parsons-container .linea-codigo");
                        codigoFinal = Array.from(bloques).map(b => b.textContent.trim()).join("\n");
                    }
                }

                const inputJustificacion = document.getElementById("justificacion-alumno");
                const justificacion = inputJustificacion ? inputJustificacion.value.trim() : "";

                if (justificacion.length < 5) {
                    alert("Escribe tu justificación lógica antes de finalizar este reactivo.");
                    if (inputJustificacion) inputJustificacion.focus();
                    return;
                }

                const confirmarEnvio = confirm("¿Confirmas enviar este reactivo? Después ya no podrás cambiarlo.");
                if (!confirmarEnvio) return;

                enviandoFinal = true;
                btnFinalizar.disabled = true;
                btnFinalizar.textContent = "Guardando respuesta...";

                // Si quedaron borrados pendientes por registrar, los enviamos antes de cerrar
                if (contadorBackspace > 0) {
                    registrarEventoEditor("BACKSPACE", contadorBackspace);
                    contadorBackspace = 0;
                }

                const tiempoTranscurridoMs = Date.now() - tiempoInicio;
                const tiempoTotalSeg = Math.floor(tiempoTranscurridoMs / 1000);

                fetch('/api/finalizar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_pregunta: typeof idPreguntaActual !== 'undefined' ? idPreguntaActual : 1,
                        codigo_final: codigoFinal,
                        justificacion: justificacion,
                        tiempo_total: tiempoTotalSeg
                    })
                })
                .then(response => response.json())
                .then(() => {
                    window.location.href = "/"; 
                })
                .catch(err => {
                    console.error("Error al guardar:", err);
                    alert("No se pudo guardar la respuesta por un problema de red. Intenta de nuevo.");
                    enviandoFinal = false;
                    btnFinalizar.disabled = false;
                    btnFinalizar.textContent = "Finalizar Reactivo";
                });

            } catch (error) {
                console.error("Error general al finalizar:", error);
                enviandoFinal = false;
                btnFinalizar.disabled = false;
                btnFinalizar.textContent = "Finalizar Reactivo";
            }
        });
    }

    // --- 2. CHAT SOCRÁTICO CON CONTEXTO DEL REACTIVO E INDICADOR DE CARGA ---
    const btnEnviarChat = document.getElementById("btn-enviar-chat");
    const promptAlumno = document.getElementById("prompt-alumno");
    const chatCaja = document.getElementById("chat-caja");

    if (btnEnviarChat && promptAlumno && chatCaja) {
        let historialChat = [];
        let tiempoUltimaInteraccion = Date.now();
        let contextoEnviado = false;
        let enviandoConsulta = false;

        function enviarConsultaChat() {
            if (enviandoConsulta) return;

            const texto = promptAlumno.value.trim();
            if (!texto) return;

            enviandoConsulta = true;
            btnEnviarChat.disabled = true;
            btnEnviarChat.textContent = "Enviando...";

            const ahora = Date.now();
            const latenciaMs = ahora - tiempoUltimaInteraccion;
            tiempoUltimaInteraccion = ahora;

            const divAlumno = document.createElement("div");
            divAlumno.className = "mensaje-alumno";
            divAlumno.textContent = texto;
            chatCaja.appendChild(divAlumno);
            promptAlumno.value = "";
            chatCaja.scrollTop = chatCaja.scrollHeight;

            // Burbuja temporal mientras responde el tutor
            const divPensando = document.createElement("div");
            divPensando.className = "mensaje-ia";
            divPensando.style.fontStyle = "italic";
            divPensando.style.opacity = "0.75";
            divPensando.textContent = "El tutor está analizando tu consulta...";
            chatCaja.appendChild(divPensando);
            chatCaja.scrollTop = chatCaja.scrollHeight;

            if (!contextoEnviado && typeof contextoPregunta !== 'undefined') {
                historialChat.push({ 
                    role: "user", 
                    content: `[Contexto para ti como tutor]: El alumno está resolviendo este problema: ${contextoPregunta}. Guíalo socráticamente sin darle la respuesta.` 
                });
                contextoEnviado = true;
            }

            historialChat.push({ role: "user", content: texto });

            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: texto,
                    historial: historialChat,
                    id_pregunta: typeof idPreguntaActual !== 'undefined' ? idPreguntaActual : 1,
                    latencia_ms: latenciaMs
                })
            })
            .then(res => res.json())
            .then(data => {
                if (divPensando.parentNode) divPensando.remove();

                if (data.respuesta) {
                    const divIa = document.createElement("div");
                    divIa.className = "mensaje-ia";
                    divIa.textContent = data.respuesta;
                    chatCaja.appendChild(divIa);
                    chatCaja.scrollTop = chatCaja.scrollHeight;

                    historialChat.push({ role: "model", content: data.respuesta });
                } else if (data.error) {
                    const divError = document.createElement("div");
                    divError.className = "mensaje-ia";
                    divError.style.color = "#b91c1c";
                    divError.textContent = data.error;
                    chatCaja.appendChild(divError);
                    chatCaja.scrollTop = chatCaja.scrollHeight;
                }
            })
            .catch(err => {
                if (divPensando.parentNode) divPensando.remove();
                console.error("Error en chat:", err);
                const divError = document.createElement("div");
                divError.className = "mensaje-ia";
                divError.style.color = "#b91c1c";
                divError.textContent = "Error de conexión con el tutor. Intenta de nuevo.";
                chatCaja.appendChild(divError);
            })
            .finally(() => {
                enviandoConsulta = false;
                btnEnviarChat.disabled = false;
                btnEnviarChat.textContent = "Consultar";
                promptAlumno.focus();
            });
        }

        btnEnviarChat.addEventListener("click", enviarConsultaChat);

        // Permitir enviar con Enter (Shift + Enter hace salto de línea)
        promptAlumno.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviarConsultaChat();
            }
        });
    }

    // --- 3. DRAG & DROP PARA PROBLEMAS DE PARSONS (TIPO 3) ---
    const parsonsContainer = document.getElementById("parsons-container");
    if (parsonsContainer) {
        let elementoArrastrado = null;

        parsonsContainer.addEventListener("dragstart", (e) => {
            if (e.target.classList.contains("linea-codigo")) {
                elementoArrastrado = e.target;
                e.target.style.opacity = "0.5";
            }
        });

        parsonsContainer.addEventListener("dragend", (e) => {
            if (e.target.classList.contains("linea-codigo")) {
                e.target.style.opacity = "1";
                elementoArrastrado = null;
            }
        });

        parsonsContainer.addEventListener("dragover", (e) => {
            e.preventDefault();
            const objetivo = e.target.closest(".linea-codigo");
            if (objetivo && objetivo !== elementoArrastrado) {
                const rect = objetivo.getBoundingClientRect();
                const mitad = rect.top + rect.height / 2;
                if (e.clientY < mitad) {
                    parsonsContainer.insertBefore(elementoArrastrado, objetivo);
                } else {
                    parsonsContainer.insertBefore(elementoArrastrado, objetivo.nextSibling);
                }
            }
        });

        // --- SOPORTE TÁCTIL PARA CELULARES ---
        let bloqueTocado = null;

        parsonsContainer.addEventListener("touchstart", (e) => {
            const item = e.target.closest(".linea-codigo");
            if (item) {
                bloqueTocado = item;
                item.style.opacity = "0.6";
            }
        }, { passive: true });

        parsonsContainer.addEventListener("touchmove", (e) => {
            if (!bloqueTocado) return;
            e.preventDefault();
            const toque = e.touches[0];
            const objetivoElemento = document.elementFromPoint(toque.clientX, toque.clientY);
            const objetivo = objetivoElemento ? objetivoElemento.closest(".linea-codigo") : null;

            if (objetivo && objetivo !== bloqueTocado && parsonsContainer.contains(objetivo)) {
                const rect = objetivo.getBoundingClientRect();
                const mitad = rect.top + rect.height / 2;
                if (toque.clientY < mitad) {
                    parsonsContainer.insertBefore(bloqueTocado, objetivo);
                } else {
                    parsonsContainer.insertBefore(bloqueTocado, objetivo.nextSibling);
                }
            }
        }, { passive: false });

        const finalizarToque = () => {
            if (bloqueTocado) {
                bloqueTocado.style.opacity = "1";
                bloqueTocado = null;
            }
        };

        parsonsContainer.addEventListener("touchend", finalizarToque);
        parsonsContainer.addEventListener("touchcancel", finalizarToque);
    }

    // --- 4. AUDITORÍA SILENCIOSA DEL EDITOR (BACKSPACE Y COPY/PASTE) ---
    const editorCodigo = document.getElementById("editor-codigo");
    if (editorCodigo) {
        editorCodigo.addEventListener("keydown", (e) => {
            if (e.key === "Backspace") {
                contadorBackspace++;
                // Enviamos en bloques de 5 para no saturar la red con 20 alumnos simultáneos
                if (contadorBackspace >= 5) {
                    registrarEventoEditor("BACKSPACE", contadorBackspace);
                    contadorBackspace = 0;
                }
            }
        });

        editorCodigo.addEventListener("paste", (e) => {
            const textoPegado = (e.clipboardData || window.clipboardData).getData("text");
            if (textoPegado.length > 0) {
                registrarEventoEditor("PASTE", textoPegado.length);
            }
        });
    }

// --- CONFIRMACIÓN VISUAL DE JUSTIFICACIÓN (ÚTIL EN MÓVIL) ---
    const btnConfirmarJust = document.getElementById("btn-confirmar-justificacion");
    const inputJust = document.getElementById("justificacion-alumno");
    const estadoJust = document.getElementById("estado-justificacion");

    if (btnConfirmarJust && inputJust && estadoJust) {
        btnConfirmarJust.addEventListener("click", () => {
            const textoJust = inputJust.value.trim();
            if (textoJust.length < 5) {
                estadoJust.style.color = "#b91c1c";
                estadoJust.textContent = "Escribe al menos 5 caracteres en tu justificación.";
                inputJust.focus();
                return;
            }
            estadoJust.style.color = "#2a9d8f";
            estadoJust.textContent = "✓ Justificación lista para enviar al finalizar el reactivo.";
        });

        inputJust.addEventListener("input", () => {
            if (estadoJust.textContent !== "") {
                estadoJust.textContent = "";
            }
        });
    }

});