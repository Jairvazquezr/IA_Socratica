import sqlite3
import csv

def exportar_a_csv():
    conn = sqlite3.connect('telemetria.db', timeout=30.0)
    cursor = conn.cursor()

    # 1. Exportar Resultados Finales y Justificaciones (Para evaluación del docente)
    cursor.execute('''
        SELECT e.matricula, e.semestre, r.id_pregunta, r.codigo_final, r.justificacion, r.tiempo_total_resolucion_seg
        FROM resultados_evaluacion r
        JOIN estudiantes e ON r.id_estudiante = e.id_estudiante
        ORDER BY e.matricula, r.id_pregunta
    ''')
    with open('reporte_resultados_docente.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Matricula', 'Semestre', 'ID_Pregunta', 'Respuesta_Codigo_Final', 'Justificacion_Alumno', 'Tiempo_Segundos'])
        writer.writerows(cursor.fetchall())

    # 2. Exportar Historial de Chat Socrático, Latencias y Marca de Tiempo
    cursor.execute('''
        SELECT e.matricula, i.id_pregunta, i.prompt_alumno, i.respuesta_ia, i.latencia_reflexion_ms, i.timestamp_envio
        FROM interacciones_ia i
        JOIN estudiantes e ON i.id_estudiante = e.id_estudiante
        ORDER BY e.matricula, i.id_interaccion
    ''')
    with open('reporte_interacciones_ia.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Matricula', 'ID_Pregunta', 'Prompt_Alumno', 'Respuesta_IA', 'Latencia_Reflexion_ms', 'Fecha_Hora'])
        writer.writerows(cursor.fetchall())

    # 3. Exportar Telemetría de Teclado (Tasa de arrepentimiento y Copy/Paste)
    cursor.execute('''
        SELECT e.matricula, a.id_pregunta, a.tipo_evento, SUM(a.cantidad_caracteres)
        FROM auditoria_editor a
        JOIN estudiantes e ON a.id_estudiante = e.id_estudiante
        GROUP BY e.matricula, a.id_pregunta, a.tipo_evento
        ORDER BY e.matricula, a.id_pregunta
    ''')
    with open('reporte_telemetria_editor.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Matricula', 'ID_Pregunta', 'Tipo_Evento', 'Total_Caracteres_o_Borrados'])
        writer.writerows(cursor.fetchall())

    # 4. Exportar Resumen Consolidado por Estudiante (Para análisis estadístico)
    cursor.execute('''
        SELECT 
            e.matricula,
            e.semestre,
            e.preguntas_asignadas,
            COUNT(DISTINCT r.id_pregunta) AS reactivos_completados,
            COALESCE(SUM(r.tiempo_total_resolucion_seg), 0) AS tiempo_total_seg,
            (SELECT COUNT(*) FROM interacciones_ia i WHERE i.id_estudiante = e.id_estudiante) AS consultas_ia_totales,
            (SELECT COALESCE(AVG(i.latencia_reflexion_ms), 0) FROM interacciones_ia i WHERE i.id_estudiante = e.id_estudiante) AS latencia_promedio_ms
        FROM estudiantes e
        LEFT JOIN resultados_evaluacion r ON e.id_estudiante = r.id_estudiante
        GROUP BY e.id_estudiante
        ORDER BY e.matricula
    ''')
    with open('reporte_resumen_estudiantes.csv', 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Matricula', 'Semestre', 'Preguntas_Asignadas', 'Reactivos_Completados',
            'Tiempo_Total_Segundos', 'Consultas_IA_Totales', 'Latencia_Promedio_ms'
        ])
        writer.writerows(cursor.fetchall())

    conn.close()
    print("Exportación completada: se generaron 4 archivos CSV listos para abrir en Excel.")

if __name__ == '__main__':
    exportar_a_csv()