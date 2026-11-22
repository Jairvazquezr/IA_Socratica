from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import random
import time
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = 'itm_socratic_ai_secret_key_2026'

# Cliente oficial de Gemini
client = genai.Client(api_key="AQ.Ab8RN6KJ1ve8UMmx23deGo2FgwP7n317d2Okx-ux3Go42S6-sg")

SYSTEM_PROMPT = """Eres un tutor socrático para estudiantes de Ingeniería en Sistemas Computacionales del ITM. 
Nunca devuelvas código completo. 
Si el alumno pide la respuesta o la solución directa, formúlale una pregunta conceptual sobre su error o dale una pista muy sutil. 
Guíalo paso a paso para que él mismo ejercite su lógica y abstracción."""

def get_db_connection():
    # timeout=30.0 evita el error "database is locked" cuando varios alumnos guardan datos a la vez
    conn = sqlite3.connect('telemetria.db', timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Habilitar modo WAL (Write-Ahead Logging) para permitir lecturas y escrituras concurrentes
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    return conn
def get_db_connection():
    conn = sqlite3.connect('telemetria.db')
    conn.row_factory = sqlite3.Row
    return conn

def cargar_preguntas():
    with open('banco_preguntas.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Ruta de Acceso / Login (Fija las preguntas por matrícula de forma permanente)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matricula = request.form.get('matricula').strip()
        semestre = request.form.get('semestre')
        
        conn = get_db_connection()
        estudiante = conn.execute('SELECT id_estudiante, preguntas_asignadas FROM estudiantes WHERE matricula = ?', (matricula,)).fetchone()
        
        if estudiante:
            id_estudiante = estudiante['id_estudiante']
            preguntas_guardadas = estudiante['preguntas_asignadas']
            
            if preguntas_guardadas:
                # Si ya tenía preguntas asignadas previamente, las recuperamos
                ids_asignados = [int(x) for x in preguntas_guardadas.split(',')]
            else:
                # Si por alguna razón no las tenía, se las generamos y guardamos
                todas = cargar_preguntas()
                muestra = random.sample(todas, min(5, len(todas)))
                ids_asignados = [p['id'] for p in muestra]
                ids_str = ",".join(map(str, ids_asignados))
                conn.execute('UPDATE estudiantes SET preguntas_asignadas = ? WHERE id_estudiante = ?', (ids_str, id_estudiante))
                conn.commit()
        else:
            # Si es un alumno completamente nuevo, seleccionamos 5 al azar y las guardamos
            todas = cargar_preguntas()
            muestra = random.sample(todas, min(5, len(todas)))
            ids_asignados = [p['id'] for p in muestra]
            ids_str = ",".join(map(str, ids_asignados))
            
            cursor = conn.execute('INSERT INTO estudiantes (matricula, semestre, preguntas_asignadas) VALUES (?, ?, ?)', (matricula, semestre, ids_str))
            conn.commit()
            id_estudiante = cursor.lastrowid
            
        conn.close()
        
        # Guardar en la sesión del navegador
        session['id_estudiante'] = id_estudiante
        session['matricula'] = matricula
        session['preguntas_asignadas_ids'] = ids_asignados
        
        return redirect(url_for('index'))
        
    return render_template('login.html')

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Ruta principal (Menú con las 5 preguntas fijas del alumno)
@app.route('/')
def index():
    if 'id_estudiante' not in session:
        return redirect(url_for('login'))
        
    id_estudiante = session['id_estudiante']
    ids_asignados = session.get('preguntas_asignadas_ids', [])
    
    todas = cargar_preguntas()
    # Filtrar estrictamente las 5 preguntas que le pertenecen a este alumno
    preguntas = [p for p in todas if p['id'] in ids_asignados]
    
    # Consultar qué preguntas de sus 5 ya respondió
    conn = get_db_connection()
    respondidas_db = conn.execute('SELECT DISTINCT id_pregunta FROM resultados_evaluacion WHERE id_estudiante = ?', (id_estudiante,)).fetchall()
    conn.close()
    
    preguntas_respondidas = [fila['id_pregunta'] for fila in respondidas_db]
    
    return render_template('index.html', preguntas=preguntas, respondidas=preguntas_respondidas, matricula=session.get('matricula'))

# Ruta para el entorno de evaluación

# Ruta para el entorno de evaluación (Pasa el objeto pregunta completo)
@app.route('/examen/<int:id_pregunta>')
def examen(id_pregunta):
    if 'id_estudiante' not in session:
        return redirect(url_for('login'))
        
    if id_pregunta not in session.get('preguntas_asignadas_ids', []):
        return redirect(url_for('index'))
        
    preguntas = cargar_preguntas()
    pregunta_actual = next((p for p in preguntas if p['id'] == id_pregunta), None)
    
    if not pregunta_actual:
        return "Pregunta no encontrada", 404
        
    return render_template('examen.html', pregunta=pregunta_actual)




# Ruta Proxy Inverso para Gemini con reintentos automáticos ante saturación (503)
@app.route('/api/chat', methods=['POST'])
def chat_socratico():
    if 'id_estudiante' not in session:
        return jsonify({"error": "No autorizado"}), 401
        
    datos = request.json
    prompt_alumno = datos.get('prompt')
    historial = datos.get('historial', [])
    id_estudiante = session['id_estudiante']
    id_pregunta = datos.get('id_pregunta')
    latencia = datos.get('latencia_ms', 0)

    contenidos = []
    for msg in historial:
        rol = "user" if msg["role"] == "user" else "model"
        contenidos.append(types.Content(role=rol, parts=[types.Part.from_text(text=msg["content"])]))
    contenidos.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt_alumno)]))

    texto_ia = None
    ultimo_error = ""

    # Intentar hasta 3 veces si el servidor de Google está saturado (503)
    for intento in range(3):
        try:
            respuesta = client.models.generate_content(
                model="gemini-4-hydrogen",
                contents=contenidos,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.3)
            )
            texto_ia = respuesta.text
            break  # Si respondió con éxito, salimos del ciclo
        except Exception as e:
            ultimo_error = str(e)
            print(f"Intento {intento + 1} fallido con Gemini: {ultimo_error}")
            if "503" in ultimo_error or "UNAVAILABLE" in ultimo_error or "429" in ultimo_error:
                time.sleep(2 * (intento + 1))  # Espera 2s, luego 4s antes de reintentar
            else:
                break  # Si es otro tipo de error, no tiene caso reintentar

    if not texto_ia:
        return jsonify({
            "error": "El tutor está recibiendo muchas consultas en este momento. Espera unos 5 segundos y vuelve a presionar 'Consultar'."
        }), 503

    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO interacciones_ia (id_estudiante, id_pregunta, prompt_alumno, respuesta_ia, latencia_reflexion_ms)
            VALUES (?, ?, ?, ?, ?)
        ''', (id_estudiante, id_pregunta, prompt_alumno, texto_ia, latencia))
        conn.commit()
        conn.close()

        return jsonify({"respuesta": texto_ia})
    except Exception as db_err:
        print(f"Error al guardar interacción en SQLite: {db_err}")
        return jsonify({"respuesta": texto_ia})

    except Exception as e:
        print(f"Error detallado en la API de Gemini: {e}")
        return jsonify({"error": f"Error de conexión con el tutor: {str(e)}"}), 500

# Ruta para recibir telemetría del teclado
@app.route('/api/telemetria', methods=['POST'])
def registrar_telemetria():
    if 'id_estudiante' not in session:
        return jsonify({"status": "error"}), 401
        
    datos = request.json
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO auditoria_editor (id_estudiante, id_pregunta, tipo_evento, cantidad_caracteres)
        VALUES (?, ?, ?, ?)
    ''', (
        session['id_estudiante'],
        datos.get('id_pregunta'),
        datos.get('tipo_evento'),
        datos.get('cantidad_caracteres', 0)
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# Ruta para guardar respuesta final y justificación
@app.route('/api/finalizar', methods=['POST'])
def finalizar_reactivo():
    if 'id_estudiante' not in session:
        return jsonify({"status": "error"}), 401
        
    datos = request.json
    id_estudiante = session['id_estudiante']
    id_pregunta = datos.get('id_pregunta')
    codigo_final = datos.get('codigo_final')
    justificacion = datos.get('justificacion', '')
    tiempo_total = datos.get('tiempo_total', 0)
    
    conn = get_db_connection()
    existente = conn.execute('SELECT id_resultado FROM resultados_evaluacion WHERE id_estudiante = ? AND id_pregunta = ?', (id_estudiante, id_pregunta)).fetchone()
    
    if existente:
        conn.execute('''
            UPDATE resultados_evaluacion 
            SET codigo_final = ?, justificacion = ?, tiempo_total_resolucion_seg = ? 
            WHERE id_estudiante = ? AND id_pregunta = ?
        ''', (codigo_final, justificacion, tiempo_total, id_estudiante, id_pregunta))
    else:
        conn.execute('''
            INSERT INTO resultados_evaluacion (id_estudiante, id_pregunta, codigo_final, justificacion, tiempo_total_resolucion_seg)
            VALUES (?, ?, ?, ?, ?)
        ''', (id_estudiante, id_pregunta, codigo_final, justificacion, tiempo_total))
        
    conn.commit()
    conn.close()
    return jsonify({"status": "guardado"})

if __name__ == '__main__':
    # threaded=True permite atender peticiones simultáneas de los 20 alumnos
    # debug=False evita reinicios inesperados y mejora el rendimiento en red local
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)