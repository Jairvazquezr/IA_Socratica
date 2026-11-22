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

    // --- 1. CRONÓMETRO Y LÓGICA PARA FINALIZAR REACTIVO ---
    const btnFinalizar = document.getElementById("btn-enviar-codigo");
    if (btnFinalizar) {
        const tiempoInicio = Date.now();

        btnFinalizar.addEventListener("click", () => {
            try {
                // Si quedaron borrados pendientes por registrar, los enviamos antes de cerrar
                if (contadorBackspace > 0) {
                    registrarEventoEditor("BACKSPACE", contadorBackspace);
                    contadorBackspace = 0;
                }

                let codigoFinal = "";
                if (typeof tipoPregunta !== 'undefined') {
                    if (tipoPregunta === 1) {
                        const seleccion = document.querySelector('input[name="respuesta_t1"]:checked');
                        codigoFinal = seleccion ? seleccion.value : "Sin responder";
                    } else if (tipoPregunta === 2) {
                        const editor = document.getElementById("editor-codigo");
                        codigoFinal = editor ? editor.value : "";
                    } else if (tipoPregunta === 3) {
                        const bloques = document.querySelectorAll("#parsons-container .linea-codigo");
                        codigoFinal = Array.from(bloques).map(b => b.textContent.trim()).join("\n");
                    }
                }

                const inputJustificacion = document.getElementById("justificacion-alumno");
                const justificacion = inputJustificacion ? inputJustificacion.value.trim() : "";

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
                    alert("Ocurrió un error de red al intentar guardar.");
                });

            } catch (error) {
                console.error("Error general al finalizar:", error);
            }
        });
    }

    // --- 2. CHAT SOCRÁTICO CON CONTEXTO DEL REACTIVO ---
    const btnEnviarChat = document.getElementById("btn-enviar-chat");
    const promptAlumno = document.getElementById("prompt-alumno");
    const chatCaja = document.getElementById("chat-caja");

    if (btnEnviarChat && promptAlumno && chatCaja) {
        let historialChat = [];
        let tiempoUltimaInteraccion = Date.now();
        let contextoEnviado = false;

        btnEnviarChat.addEventListener("click", () => {
            const texto = promptAlumno.value.trim();
            if (!texto) return;

            const ahora = Date.now();
            const latenciaMs = ahora - tiempoUltimaInteraccion;
            tiempoUltimaInteraccion = ahora;

            const divAlumno = document.createElement("div");
            divAlumno.className = "mensaje-alumno";
            divAlumno.textContent = texto;
            chatCaja.appendChild(divAlumno);
            promptAlumno.value = "";
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
                    divError.style.color = "red";
                    divError.textContent = data.error;
                    chatCaja.appendChild(divError);
                }
            })
            .catch(err => console.error("Error en chat:", err));
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
});