from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import random
import time
import os
from dotenv import load_dotenv
from openai import OpenAI

app = Flask(__name__)
app.secret_key = 'itm_socratic_ai_secret_key_2026'


load_dotenv()  # Carga las variables desde tu archivo .env
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# Modelo rápido, económico y preciso para tutoría socrática en tiempo real
MODELO_OPENAI = "gpt-4o-mini"

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

def cargar_preguntas():
    with open('banco_preguntas.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Ruta de Acceso / Login (Fija las preguntas por matrícula de forma permanente)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matricula = request.form.get('matricula', '').strip().upper()
        semestre = request.form.get('semestre') or "3er Semestre"
        
        if not matricula:
            return redirect(url_for('login'))

        conn = get_db_connection()
        estudiante = conn.execute(
            'SELECT id_estudiante, preguntas_asignadas FROM estudiantes WHERE matricula = ?',
            (matricula,)
        ).fetchone()
        
        if estudiante:
            id_estudiante = estudiante['id_estudiante']
            preguntas_guardadas = estudiante['preguntas_asignadas']
            
            if preguntas_guardadas:
                ids_asignados = [int(x) for x in preguntas_guardadas.split(',')]
            else:
                todas = cargar_preguntas()
                muestra = random.sample(todas, min(5, len(todas)))
                ids_asignados = [p['id'] for p in muestra]
                ids_str = ",".join(map(str, ids_asignados))
                conn.execute(
                    'UPDATE estudiantes SET preguntas_asignadas = ? WHERE id_estudiante = ?',
                    (ids_str, id_estudiante)
                )
                conn.commit()
        else:
            todas = cargar_preguntas()
            muestra = random.sample(todas, min(5, len(todas)))
            ids_asignados = [p['id'] for p in muestra]
            ids_str = ",".join(map(str, ids_asignados))
            
            cursor = conn.execute(
                'INSERT INTO estudiantes (matricula, semestre, preguntas_asignadas) VALUES (?, ?, ?)',
                (matricula, semestre, ids_str)
            )
            conn.commit()
            id_estudiante = cursor.lastrowid
            
        conn.close()
        
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
    preguntas = [p for p in todas if p['id'] in ids_asignados]
    
    conn = get_db_connection()
    respondidas_db = conn.execute(
        'SELECT DISTINCT id_pregunta FROM resultados_evaluacion WHERE id_estudiante = ?',
        (id_estudiante,)
    ).fetchall()
    conn.close()
    
    preguntas_respondidas = [fila['id_pregunta'] for fila in respondidas_db]
    
    return render_template(
        'index.html',
        preguntas=preguntas,
        respondidas=preguntas_respondidas,
        matricula=session.get('matricula')
    )

# Ruta para el entorno de evaluación (Impide reabrir reactivos ya respondidos)
@app.route('/examen/<int:id_pregunta>')
def examen(id_pregunta):
    if 'id_estudiante' not in session:
        return redirect(url_for('login'))
        
    if id_pregunta not in session.get('preguntas_asignadas_ids', []):
        return redirect(url_for('index'))

    conn = get_db_connection()
    ya_respondida = conn.execute(
        'SELECT id_resultado FROM resultados_evaluacion WHERE id_estudiante = ? AND id_pregunta = ?',
        (session['id_estudiante'], id_pregunta)
    ).fetchone()
    conn.close()

    if ya_respondida:
        return redirect(url_for('index'))
        
    preguntas = cargar_preguntas()
    pregunta_actual = next((p for p in preguntas if p['id'] == id_pregunta), None)
    
    if not pregunta_actual:
        return "Pregunta no encontrada", 404
        
    return render_template('examen.html', pregunta=pregunta_actual)

# Ruta Proxy Inverso para OpenAI con reintentos automáticos
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

    # Construir mensajes en formato estándar de OpenAI
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in historial:
        rol = "user" if msg["role"] == "user" else "assistant"
        mensajes.append({"role": rol, "content": msg["content"]})

    # Asegurar que el prompt actual esté incluido si no venía al final del historial
    if not mensajes or mensajes[-1]["content"] != prompt_alumno:
        mensajes.append({"role": "user", "content": prompt_alumno})

    texto_ia = None
    ultimo_error = ""

    # Intentar hasta 3 veces ante cualquier pico temporal de red
    for intento in range(3):
        try:
            respuesta = client.chat.completions.create(
                model=MODELO_OPENAI,
                messages=mensajes,
                temperature=0.3
            )
            texto_ia = respuesta.choices[0].message.content
            break
        except Exception as e:
            ultimo_error = str(e)
            print(f"Intento {intento + 1} fallido con OpenAI: {ultimo_error}")
            if "503" in ultimo_error or "429" in ultimo_error or "timeout" in ultimo_error.lower():
                time.sleep(2 * (intento + 1))
            else:
                break

    if not texto_ia:
        return jsonify({
            "error": "El tutor está procesando varias consultas en este momento. Espera 5 segundos y vuelve a presionar 'Consultar'."
        }), 503

    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO interacciones_ia (id_estudiante, id_pregunta, prompt_alumno, respuesta_ia, latencia_reflexion_ms)
            VALUES (?, ?, ?, ?, ?)
        ''', (id_estudiante, id_pregunta, prompt_alumno, texto_ia, latencia))
        conn.commit()
        conn.close()
    except Exception as db_err:
        print(f"Error al guardar interacción en SQLite: {db_err}")

    return jsonify({"respuesta": texto_ia})

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

# Ruta para guardar respuesta final y justificación (Protegida contra doble envío)
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
    existente = conn.execute(
        'SELECT id_resultado FROM resultados_evaluacion WHERE id_estudiante = ? AND id_pregunta = ?',
        (id_estudiante, id_pregunta)
    ).fetchone()
    
    if existente:
        conn.close()
        return jsonify({"status": "ya_respondida", "error": "Este reactivo ya fue registrado anteriormente."}), 400

    conn.execute('''
        INSERT INTO resultados_evaluacion (id_estudiante, id_pregunta, codigo_final, justificacion, tiempo_total_resolucion_seg)
        VALUES (?, ?, ?, ?, ?)
    ''', (id_estudiante, id_pregunta, codigo_final, justificacion, tiempo_total))
        
    conn.commit()
    conn.close()
    return jsonify({"status": "guardado"})

# Panel de monitoreo en tiempo real para el investigador (Sala de cómputo)
@app.route('/monitor')
def monitor_grupo():
    conn = get_db_connection()
    filas = conn.execute('''
        SELECT 
            e.id_estudiante,
            e.matricula,
            e.semestre,
            e.preguntas_asignadas,
            COUNT(DISTINCT r.id_pregunta) AS completadas,
            COALESCE(SUM(r.tiempo_total_resolucion_seg), 0) AS tiempo_total_seg,
            (SELECT COUNT(*) FROM interacciones_ia i WHERE i.id_estudiante = e.id_estudiante) AS total_consultas_ia
        FROM estudiantes e
        LEFT JOIN resultados_evaluacion r ON e.id_estudiante = r.id_estudiante
        GROUP BY e.id_estudiante
        ORDER BY e.id_estudiante DESC
    ''').fetchall()
    conn.close()

    filas_html = ""
    for f in filas:
        estado = "Completado" if f['completadas'] >= 5 else "En progreso"
        color = "#16a34a" if f['completadas'] >= 5 else "#2563eb"
        filas_html += f"""
        <tr>
            <td>{f['id_estudiante']}</td>
            <td><strong>{f['matricula']}</strong></td>
            <td>{f['semestre']}</td>
            <td>{f['preguntas_asignadas']}</td>
            <td><span style="color:{color}; font-weight:bold;">{f['completadas']} / 5 ({estado})</span></td>
            <td>{f['total_consultas_ia']}</td>
            <td>{f['tiempo_total_seg']} s</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="10">
        <title>Monitor en Vivo - IA Socrática ITM</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f1f5f9; padding: 20px; color: #1e293b; }}
            h1 {{ color: #1b263b; margin-bottom: 5px; }}
            p {{ color: #64748b; margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            th, td {{ padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: left; }}
            th {{ background: #1b263b; color: white; }}
        </style>
    </head>
    <body>
        <h1>Monitor de Sesión en Vivo — TecNM ITM</h1>
        <p>Actualización automática cada 10 segundos | Alumnos registrados: <strong>{len(filas)}</strong></p>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Matrícula</th>
                    <th>Semestre</th>
                    <th>Reactivos Asignados</th>
                    <th>Avance</th>
                    <th>Consultas al Tutor</th>
                    <th>Tiempo Acumulado</th>
                </tr>
            </thead>
            <tbody>
                {filas_html if filas_html else '<tr><td colspan="7">Aún no hay alumnos conectados.</td></tr>'}
            </tbody>
        </table>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)