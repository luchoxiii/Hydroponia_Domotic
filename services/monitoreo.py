"""Servicio de monitoreo y lecturas de sensores."""
from datetime import datetime, timedelta, timezone
from models import db
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from services.alertas import verificar_lectura


def registrar_lectura(cultivo_id, tipo, valor, unidad=None):
    """Registra una nueva lectura de sensor y verifica alertas."""
    cultivo = Cultivo.query.get_or_404(cultivo_id)
    
    lectura = LecturaSensor(
        cultivo_id=cultivo_id,
        tipo=tipo.upper(),
        valor=float(valor),
        unidad=unidad
    )
    db.session.add(lectura)
    db.session.commit()
    
    # Verificar alertas si hay especie asociada
    alertas = []
    if cultivo.especie:
        alertas = verificar_lectura(lectura, cultivo.especie)
    
    return lectura, alertas


def obtener_lecturas(cultivo_id, tipo=None, horas=24):
    """Obtiene las lecturas recientes de un cultivo."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    query = LecturaSensor.query.filter(
        LecturaSensor.cultivo_id == cultivo_id,
        LecturaSensor.timestamp >= desde
    )
    if tipo:
        query = query.filter_by(tipo=tipo.upper())
    return query.order_by(LecturaSensor.timestamp.asc()).all()


def obtener_resumen_cultivo(cultivo_id):
    """Obtiene un resumen del estado actual de un cultivo."""
    cultivo = Cultivo.query.get_or_404(cultivo_id)
    resumen = {}
    
    for tipo in LecturaSensor.TIPOS_SENSOR:
        ultima = cultivo.ultima_lectura(tipo)
        if ultima:
            # Determinar si está en rango
            en_rango = True
            if cultivo.especie:
                esp = cultivo.especie
                if tipo == 'PH':
                    en_rango = esp.ph_min <= ultima.valor <= esp.ph_max
                elif tipo == 'EC':
                    en_rango = esp.ec_min <= ultima.valor <= esp.ec_max
                elif tipo == 'TEMPERATURA':
                    en_rango = esp.temp_min <= ultima.valor <= esp.temp_max
                elif tipo == 'HUMEDAD':
                    en_rango = esp.humedad_min <= ultima.valor <= esp.humedad_max
                elif tipo == 'NIVEL_AGUA':
                    en_rango = ultima.valor >= 40.0
                elif tipo == 'LUZ':
                    en_rango = esp.luz_horas_min <= ultima.valor <= esp.luz_horas_max
            elif tipo == 'NIVEL_AGUA':
                en_rango = ultima.valor >= 40.0
            
            resumen[tipo] = {
                'valor': ultima.valor,
                'unidad': ultima.unidad or ultima.tipo_info['unidad'],
                'icono': ultima.tipo_info['icono'],
                'nombre': ultima.tipo_info['nombre'],
                'en_rango': en_rango,
                'timestamp': ultima.timestamp.isoformat()
            }
    
    return resumen


def simular_lecturas(cultivo_id, anomalas=False):
    """Genera lecturas simuladas para todos los sensores de un cultivo."""
    import random
    cultivo = Cultivo.query.get_or_404(cultivo_id)
    esp = cultivo.especie
    alertas_todas = []

    if not esp:
        return [], []

    # pH
    if anomalas:
        ph_val = round(esp.ph_min - random.uniform(0.5, 1.5), 2)
    else:
        ph_val = round(random.uniform(esp.ph_min, esp.ph_max), 2)
    _, a = registrar_lectura(cultivo_id, 'PH', ph_val)
    alertas_todas.extend(a)

    # EC
    if anomalas and random.choice([True, False]):
        ec_val = round(esp.ec_max + random.uniform(0.5, 1.2), 2)
    else:
        ec_val = round(random.uniform(esp.ec_min, esp.ec_max), 2)
    _, a = registrar_lectura(cultivo_id, 'EC', ec_val)
    alertas_todas.extend(a)

    # Temperatura
    if anomalas and random.choice([True, False]):
        temp_val = round(esp.temp_max + random.uniform(4.0, 8.0), 1)
    else:
        temp_val = round(random.uniform(esp.temp_min, esp.temp_max), 1)
    _, a = registrar_lectura(cultivo_id, 'TEMPERATURA', temp_val)
    alertas_todas.extend(a)

    # Humedad
    if anomalas and random.choice([True, False]):
        hum_val = round(max(10.0, esp.humedad_min - random.uniform(15.0, 25.0)), 1)
    else:
        hum_val = round(random.uniform(esp.humedad_min, esp.humedad_max), 1)
    _, a = registrar_lectura(cultivo_id, 'HUMEDAD', hum_val)
    alertas_todas.extend(a)

    # Nivel de agua
    if anomalas:
        nivel_val = round(random.uniform(10.0, 25.0), 1)
    else:
        nivel_val = round(random.uniform(65.0, 95.0), 1)
    _, a = registrar_lectura(cultivo_id, 'NIVEL_AGUA', nivel_val)
    alertas_todas.extend(a)

    # Luz
    luz_val = round(random.uniform(esp.luz_horas_min, esp.luz_horas_max), 1)
    _, a = registrar_lectura(cultivo_id, 'LUZ', luz_val)
    alertas_todas.extend(a)

    return obtener_resumen_cultivo(cultivo_id), alertas_todas


def obtener_estadisticas_dashboard():
    """Obtiene estadísticas generales para el dashboard."""
    from models.alerta import Alerta
    
    total_cultivos = Cultivo.query.filter_by(estado='ACTIVO').count()
    total_alertas = Alerta.query.filter_by(leida=False).count()
    alertas_criticas = Alerta.query.filter_by(leida=False, nivel='CRITICA').count()
    
    cultivos_activos = Cultivo.query.filter_by(estado='ACTIVO').all()
    
    return {
        'total_cultivos': total_cultivos,
        'total_alertas': total_alertas,
        'alertas_criticas': alertas_criticas,
        'cultivos': [c.to_dict() for c in cultivos_activos]
    }


def eliminar_cultivo(cultivo_id):
    """
    Elimina un cultivo y limpia en cascada todas sus dependencias:
    - Desvincula cualquier placa IoT asociada (seteando cultivo_id=None).
    - Elimina todas sus lecturas históricas de sensores.
    - Elimina todas las alertas generadas por este cultivo.
    - Elimina el cultivo de la base de datos.
    - Registra el evento en la bitácora forense cifrada.
    """
    from models.dispositivo import Dispositivo
    from models.lectura_sensor import LecturaSensor
    from models.alerta import Alerta

    cultivo = Cultivo.query.get_or_404(cultivo_id)
    nombre = cultivo.nombre

    # 1. Desvincular dispositivos IoT asociados para preservar el hardware
    Dispositivo.query.filter_by(cultivo_id=cultivo_id).update({'cultivo_id': None})

    # 2. Eliminar lecturas de sensores asociadas
    LecturaSensor.query.filter_by(cultivo_id=cultivo_id).delete()

    # 3. Eliminar alertas asociadas
    Alerta.query.filter_by(cultivo_id=cultivo_id).delete()

    # 4. Eliminar el cultivo
    db.session.delete(cultivo)
    db.session.commit()

    # 5. Asentar evento en bitácora cifrada
    try:
        from services import bitacora
        bitacora.registrar_evento('ELIMINAR_CULTIVO', 'AGRONOMICO', {
            'cultivo_id': cultivo_id,
            'nombre': nombre
        })
    except Exception:
        pass

    return nombre
