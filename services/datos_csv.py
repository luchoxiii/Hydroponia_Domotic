"""
Servicio para la exportación e importación de lecturas y telemetría en formato CSV.
Incluye soporte para clima exterior y generación automática de alertas en datos importados.
"""
import io
import csv
from datetime import datetime, timezone
import pandas as pd
from models import db
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from services.alertas import verificar_lectura
from services.clima import obtener_clima_actual


def exportar_cultivo_csv(cultivo_id):
    """
    Exporta todas las lecturas históricas de un cultivo a un archivo CSV en memoria.
    Incluye especie, parámetros ideales de referencia y clima exterior actual.
    """
    cultivo = Cultivo.query.get_or_404(cultivo_id)
    esp = cultivo.especie
    clima = obtener_clima_actual()

    lecturas = LecturaSensor.query.filter_by(
        cultivo_id=cultivo_id
    ).order_by(LecturaSensor.timestamp.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Encabezados
    writer.writerow([
        'timestamp',
        'cultivo_id',
        'cultivo_nombre',
        'especie',
        'categoria',
        'sensor_tipo',
        'sensor_nombre',
        'valor',
        'unidad',
        'rango_min_especie',
        'rango_max_especie',
        'temp_externa_ref',
        'humedad_externa_ref'
    ])

    for l in lecturas:
        tipo = l.tipo
        r_min = ''
        r_max = ''
        if esp:
            if tipo == 'PH':
                r_min, r_max = esp.ph_min, esp.ph_max
            elif tipo == 'EC':
                r_min, r_max = esp.ec_min, esp.ec_max
            elif tipo == 'TEMPERATURA':
                r_min, r_max = esp.temp_min, esp.temp_max
            elif tipo == 'HUMEDAD':
                r_min, r_max = esp.humedad_min, esp.humedad_max
            elif tipo == 'LUZ':
                r_min, r_max = esp.luz_horas_min, esp.luz_horas_max
            elif tipo == 'NIVEL_AGUA':
                r_min, r_max = 40.0, 100.0

        writer.writerow([
            l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            cultivo.id,
            cultivo.nombre,
            esp.nombre_comun if esp else 'N/A',
            esp.categoria if esp else 'N/A',
            l.tipo,
            l.tipo_info['nombre'],
            l.valor,
            l.unidad or l.tipo_info['unidad'],
            r_min,
            r_max,
            clima.get('temp_externa', ''),
            clima.get('humedad_externa', '')
        ])

    output.seek(0)
    return output.getvalue()


def importar_lecturas_csv(cultivo_id, stream_o_contenido):
    """
    Importa lecturas desde un archivo CSV y evalúa automáticamente las alertas.
    Soporta dos formatos comunes:
      1. Formato Ancho (columnas: timestamp, ph, ec, temperatura, humedad, nivel_agua, luz)
      2. Formato Largo (columnas: timestamp, tipo/sensor, valor, unidad)
    """
    cultivo = Cultivo.query.get_or_404(cultivo_id)
    esp = cultivo.especie

    if isinstance(stream_o_contenido, bytes):
        stream_o_contenido = stream_o_contenido.decode('utf-8', errors='replace')

    # Leer con pandas para manejar diversos delimitadores (; o , o tab)
    try:
        df = pd.read_csv(io.StringIO(stream_o_contenido), sep=None, engine='python')
    except Exception as e:
        return {'error': f'No se pudo leer el archivo CSV: {str(e)}'}, 400

    if df.empty:
        return {'error': 'El archivo CSV está vacío'}, 400

    # Normalizar nombres de columnas a minúsculas sin espacios
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    lecturas_creadas = 0
    alertas_generadas = []
    errores = []

    MAPA_COLUMNAS = {
        'ph': 'PH',
        'ec': 'EC',
        'tds': 'EC',
        'temp': 'TEMPERATURA',
        'temperatura': 'TEMPERATURA',
        'temp_interna': 'TEMPERATURA',
        'hum': 'HUMEDAD',
        'humedad': 'HUMEDAD',
        'hum_interna': 'HUMEDAD',
        'nivel_agua': 'NIVEL_AGUA',
        'agua': 'NIVEL_AGUA',
        'water_level': 'NIVEL_AGUA',
        'luz': 'LUZ',
        'horas_luz': 'LUZ'
    }

    # Caso 1: Formato Largo (tiene columna 'sensor_tipo' o 'tipo' o 'sensor' y columna 'valor')
    col_tipo = next((c for c in ['sensor_tipo', 'tipo', 'sensor'] if c in df.columns), None)
    col_valor = next((c for c in ['valor', 'value', 'medicion'] if c in df.columns), None)

    if col_tipo and col_valor:
        for idx, row in df.iterrows():
            try:
                tipo_raw = str(row[col_tipo]).strip().upper()
                tipo_norm = MAPA_COLUMNAS.get(tipo_raw.lower(), tipo_raw)
                valor = float(row[col_valor])

                ts = datetime.now(timezone.utc)
                if 'timestamp' in row and pd.notna(row['timestamp']):
                    try:
                        ts = pd.to_datetime(row['timestamp']).to_pydatetime()
                    except Exception:
                        pass

                lectura = LecturaSensor(
                    cultivo_id=cultivo_id,
                    tipo=tipo_norm,
                    valor=valor,
                    timestamp=ts
                )
                db.session.add(lectura)
                lecturas_creadas += 1

                if esp:
                    a = verificar_lectura(lectura, esp, auto_commit=False)
                    alertas_generadas.extend(a)

                if lecturas_creadas % 500 == 0:
                    db.session.commit()
            except Exception as ex:
                errores.append(f"Fila {idx+1}: {str(ex)}")

    # Caso 2: Formato Ancho (las columnas representan los distintos sensores)
    else:
        for idx, row in df.iterrows():
            ts = datetime.now(timezone.utc)
            if 'timestamp' in row and pd.notna(row['timestamp']):
                try:
                    ts = pd.to_datetime(row['timestamp']).to_pydatetime()
                except Exception:
                    pass

            for col in df.columns:
                if col in MAPA_COLUMNAS and pd.notna(row[col]):
                    try:
                        tipo_norm = MAPA_COLUMNAS[col]
                        valor = float(row[col])

                        lectura = LecturaSensor(
                            cultivo_id=cultivo_id,
                            tipo=tipo_norm,
                            valor=valor,
                            timestamp=ts
                        )
                        db.session.add(lectura)
                        lecturas_creadas += 1

                        if esp:
                            a = verificar_lectura(lectura, esp, auto_commit=False)
                            alertas_generadas.extend(a)

                        if lecturas_creadas % 500 == 0:
                            db.session.commit()
                    except Exception as ex:
                        errores.append(f"Fila {idx+1}, col {col}: {str(ex)}")

    if lecturas_creadas > 0:
        db.session.commit()

    return {
        'status': 'ok',
        'cultivo_id': cultivo_id,
        'cultivo_nombre': cultivo.nombre,
        'lecturas_importadas': lecturas_creadas,
        'alertas_generadas': len(alertas_generadas),
        'errores': errores[:10]  # Limitar para no saturar respuesta
    }, 200
