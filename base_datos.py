import sqlite3

def inicializar_bd():
    # Se crea el archivo telemetria.db automáticamente si no existe
    conexion = sqlite3.connect('telemetria.db', timeout=30.0)
    cursor = conexion.cursor()

    # Habilitar modo WAL desde la creación para soportar concurrencia en laboratorio
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('PRAGMA synchronous=NORMAL;')

    # Tabla para registrar a los estudiantes y sus 5 reactivos fijos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudiantes (
            id_estudiante INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE,
            semestre TEXT,
            preguntas_asignadas TEXT
        )
    ''')

    # Tabla para las interacciones con el tutor socrático (IA)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interacciones_ia (
            id_interaccion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            prompt_alumno TEXT,
            respuesta_ia TEXT,
            timestamp_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
            latencia_reflexion_ms INTEGER,
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    # Tabla para la auditoría del editor de código (Keylogging controlado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auditoria_editor (
            id_evento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            tipo_evento TEXT,
            cantidad_caracteres INTEGER,
            timestamp_evento DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    # Tabla para el envío de la respuesta final, justificación y tiempo real
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados_evaluacion (
            id_resultado INTEGER PRIMARY KEY AUTOINCREMENT,
            id_estudiante INTEGER,
            id_pregunta INTEGER,
            codigo_final TEXT,
            justificacion TEXT,
            tiempo_total_resolucion_seg INTEGER,
            FOREIGN KEY (id_estudiante) REFERENCES estudiantes (id_estudiante)
        )
    ''')

    conexion.commit()
    conexion.close()
    print("Base de datos 'telemetria.db' inicializada correctamente en modo concurrente.")

if __name__ == '__main__':
    inicializar_bd()