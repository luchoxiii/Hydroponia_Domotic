"""Servicio de generación y gestión de alertas."""
from models import db
from models.alerta import Alerta
from models.lectura_sensor import LecturaSensor


def verificar_lectura(lectura, especie, auto_commit=True):
    """Verifica una lectura contra los rangos ideales de la especie y genera alertas."""
    alertas_generadas = []
    
    if lectura.tipo == 'PH':
        if lectura.valor < especie.ph_min:
            desviacion = especie.ph_min - lectura.valor
            nivel = 'CRITICA' if desviacion > 1.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='PH_BAJO',
                mensaje=f'pH bajo: {lectura.valor} (mínimo recomendado: {especie.ph_min})',
                nivel=nivel
            )
            alertas_generadas.append(alerta)
        elif lectura.valor > especie.ph_max:
            desviacion = lectura.valor - especie.ph_max
            nivel = 'CRITICA' if desviacion > 1.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='PH_ALTO',
                mensaje=f'pH alto: {lectura.valor} (máximo recomendado: {especie.ph_max})',
                nivel=nivel
            )
            alertas_generadas.append(alerta)

    elif lectura.tipo == 'EC':
        if lectura.valor < especie.ec_min:
            desviacion = especie.ec_min - lectura.valor
            nivel = 'CRITICA' if desviacion > 0.8 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='EC_BAJA',
                mensaje=f'EC baja: {lectura.valor} mS/cm (mínimo: {especie.ec_min})',
                nivel=nivel
            )
            alertas_generadas.append(alerta)
        elif lectura.valor > especie.ec_max:
            desviacion = lectura.valor - especie.ec_max
            nivel = 'CRITICA' if desviacion > 0.8 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='EC_ALTA',
                mensaje=f'EC alta: {lectura.valor} mS/cm (máximo: {especie.ec_max})',
                nivel=nivel
            )
            alertas_generadas.append(alerta)

    elif lectura.tipo == 'TEMPERATURA':
        if lectura.valor < especie.temp_min:
            desviacion = especie.temp_min - lectura.valor
            nivel = 'CRITICA' if desviacion > 5.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='TEMP_BAJA',
                mensaje=f'Temperatura baja: {lectura.valor}°C (mínimo: {especie.temp_min}°C)',
                nivel=nivel
            )
            alertas_generadas.append(alerta)
        elif lectura.valor > especie.temp_max:
            desviacion = lectura.valor - especie.temp_max
            nivel = 'CRITICA' if desviacion > 5.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='TEMP_ALTA',
                mensaje=f'Temperatura alta: {lectura.valor}°C (máximo: {especie.temp_max}°C)',
                nivel=nivel
            )
            alertas_generadas.append(alerta)

    elif lectura.tipo == 'HUMEDAD':
        if lectura.valor < especie.humedad_min:
            desviacion = especie.humedad_min - lectura.valor
            nivel = 'CRITICA' if desviacion > 20.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='HUMEDAD_BAJA',
                mensaje=f'Humedad baja: {lectura.valor}% (mínimo: {especie.humedad_min}%)',
                nivel=nivel
            )
            alertas_generadas.append(alerta)
        elif lectura.valor > especie.humedad_max:
            desviacion = lectura.valor - especie.humedad_max
            nivel = 'CRITICA' if desviacion > 20.0 else 'ADVERTENCIA'
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='HUMEDAD_ALTA',
                mensaje=f'Humedad alta: {lectura.valor}% (máximo: {especie.humedad_max}%)',
                nivel=nivel
            )
            alertas_generadas.append(alerta)

    elif lectura.tipo == 'NIVEL_AGUA':
        if lectura.valor < 20:
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='NIVEL_AGUA_CRITICO',
                mensaje=f'¡Nivel de agua crítico! {lectura.valor}% - Rellenar inmediatamente',
                nivel='CRITICA'
            )
            alertas_generadas.append(alerta)
        elif lectura.valor < 40:
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='NIVEL_AGUA_BAJO',
                mensaje=f'Nivel de agua bajo: {lectura.valor}% - Considerar rellenar',
                nivel='ADVERTENCIA'
            )
            alertas_generadas.append(alerta)

    elif lectura.tipo == 'LUZ':
        if lectura.valor < especie.luz_horas_min:
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='LUZ_BAJA',
                mensaje=f'Horas de luz insuficientes: {lectura.valor}h (mínimo recomendado: {especie.luz_horas_min}h)',
                nivel='ADVERTENCIA'
            )
            alertas_generadas.append(alerta)
        elif lectura.valor > especie.luz_horas_max:
            alerta = Alerta(
                cultivo_id=lectura.cultivo_id,
                tipo='LUZ_ALTA',
                mensaje=f'Exceso de fotoperíodo: {lectura.valor}h (máximo recomendado: {especie.luz_horas_max}h)',
                nivel='ADVERTENCIA'
            )
            alertas_generadas.append(alerta)

    # Guardar alertas
    for alerta in alertas_generadas:
        db.session.add(alerta)
    
    if alertas_generadas and auto_commit:
        db.session.commit()
        # Notificar al usuario (Telegram / Discord) y canal interno
        try:
            from services import notificaciones_usuario
            for alerta in alertas_generadas:
                notificaciones_usuario.despachar_alerta(alerta, especie=especie)
        except Exception:
            pass
        try:
            from services import telegram_bot
            for alerta in alertas_generadas:
                telegram_bot.notificar_alerta_telegram(alerta, especie=especie)
        except Exception:
            pass
        try:
            from services import bitacora
            for alerta in alertas_generadas:
                bitacora.registrar_evento('ALERTA_DISPARADA', 'AGRONOMICO', {
                    'cultivo_id': alerta.cultivo_id,
                    'tipo': alerta.tipo,
                    'nivel': alerta.nivel,
                    'mensaje': alerta.mensaje
                }, severidad=alerta.nivel)
        except Exception:
            pass
    
    return alertas_generadas


def obtener_alertas(solo_no_leidas=False, limite=50):
    """Obtiene las alertas más recientes."""
    query = Alerta.query.order_by(Alerta.created_at.desc())
    if solo_no_leidas:
        query = query.filter_by(leida=False)
    return query.limit(limite).all()


def contar_alertas_no_leidas():
    """Cuenta las alertas no leídas."""
    return Alerta.query.filter_by(leida=False).count()


def marcar_como_leida(alerta_id):
    """Marca una alerta como leída."""
    alerta = Alerta.query.get(alerta_id)
    if alerta:
        alerta.leida = True
        db.session.commit()
    return alerta


def marcar_todas_leidas():
    """Marca todas las alertas como leídas."""
    Alerta.query.filter_by(leida=False).update({'leida': True})
    db.session.commit()
