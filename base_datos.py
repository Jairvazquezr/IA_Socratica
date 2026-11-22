import sqlite3

def inicializar_bd():
    # Se crea el archivo telemetria.db automáticamente si no existe
    conexion = sqlite3.connect('telemetria.db')
    cursor = conexion.cursor()

    # Tabla para registrar a los estudiantes (Actualizada con las preguntas asignadas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudiantes (
            id_estudiante INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            semestre TEXT,
            preguntas_asignadas TEXT -- NUEVO CAMPO PARA GUARDAR LOS IDS (Ej. "1,11,15,22,30")
        )
    ''')

    # Tabla para las interacciones con el tutor socrático (IA)[cite: 1]
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interacciones_ia (
            id_interaccion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            prompt_alumno TEXT,
            respuesta_ia TEXT,
            timestamp_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
            latencia_reflexion_ms INTEGER, -- Tiempo transcurrido antes de volver a teclear
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    # Tabla para la auditoría del editor de código (Keylogging controlado)[cite: 1]
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auditoria_editor (
            id_evento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            tipo_evento TEXT, -- Ej: 'backspace', 'copy_paste', 'run_code'
            cantidad_caracteres INTEGER,
            timestamp_evento DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    # Tabla para el envío del código final y su evaluación[cite: 1]
    # Tabla para el envío del código final y su evaluación (Actualizada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados_evaluacion (
            id_resultado INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            codigo_final TEXT,
            justificacion TEXT, -- NUEVO CAMPO AGREGADO
            tiempo_total_resolucion_seg INTEGER,
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    conexion.commit()
    conexion.close()
    print("Base de datos 'telemetria.db' inicializada correctamente.")

if __name__ == '__main__':
    inicializar_bd()