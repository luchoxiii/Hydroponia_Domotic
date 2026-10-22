"""Sistema de Control de Hidroponía - Aplicación Principal."""
import os
import logging
from logging.handlers import RotatingFileHandler
import shutil
from datetime import datetime, date, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response

from config import Config, obtener_config
from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from models.alerta import Alerta
from models.dispositivo import Dispositivo
from services import (
    catalogo, alertas, monitoreo, dispositivos, clima, ml_engine,
    datos_csv, telegram_bot, telemetria_dev, notificaciones_usuario, bitacora
)


def crear_app(config_class=None):
    """Factory de la aplicación Flask para desarrollo y producción."""
    if config_class is None:
        config_class = obtener_config()

    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Asegurar que existen directorios requeridos (datos y logs)
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    log_dir = app.config.get('LOG_DIR', os.path.join(os.path.dirname(__file__), 'logs'))
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Configuración de Logging Rotativo en Producción
    if not app.debug and not app.testing:
        log_file = os.path.join(log_dir, 'hydrocontrol.log')
        if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
            ))
            log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
            log_level = getattr(logging, log_level_name, logging.INFO)
            file_handler.setLevel(log_level)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(log_level)
            app.logger.info("HydroControl iniciado en modo Producción.")

    # Soporte para Reverse Proxy (Nginx, Traefik, Caddy, Cloudflare)
    if app.config.get('USE_PROXY_FIX'):
        try:
            from werkzeug.middleware.proxy_fix import ProxyFix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
        except Exception as e:
            app.logger.warning(f"No se pudo inicializar ProxyFix: {e}")

    # Headers HTTP de Seguridad
    @app.after_request
    def aplicar_headers_seguridad(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Server'] = 'HydroControl-AppServer'
        return response
    
    # Inicializar base de datos
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        catalogo.cargar_catalogo_default()
        try:
            telemetria_dev.notificar_instalacion_arranque()
        except Exception:
            pass
        try:
            bitacora.registrar_evento('ARRANQUE_SISTEMA', 'SISTEMA', {
                'instancia': telemetria_dev.obtener_id_instancia(),
                'modo': 'Producción' if not app.debug else 'Desarrollo'
            })
        except Exception:
            pass
    
    # Context processor para alertas en navbar
    @app.context_processor
    def inject_alertas():
        try:
            return {'alertas_count': alertas.contar_alertas_no_leidas()}
        except Exception:
            return {'alertas_count': 0}
    
    # ==================== RUTAS PRINCIPALES ====================
    
    @app.route('/')
    def dashboard():
        """Dashboard principal."""
        stats = monitoreo.obtener_estadisticas_dashboard()
        alertas_recientes = alertas.obtener_alertas(limite=10)
        return render_template('dashboard.html', stats=stats, alertas_recientes=alertas_recientes)
    
    # ==================== CATÁLOGO ====================
    
    @app.route('/catalogo')
    def catalogo_lista():
        """Lista del catálogo de especies."""
        termino = request.args.get('buscar', '')
        categoria = request.args.get('categoria', '')
        especies = catalogo.buscar_especies(termino=termino or None, categoria=categoria or None)
        return render_template('catalogo.html', especies=especies, 
                             buscar=termino, categoria=categoria)
    
    @app.route('/catalogo/agregar', methods=['GET', 'POST'])
    def catalogo_agregar():
        """Agrega una nueva especie al catálogo."""
        if request.method == 'POST':
            try:
                especie = catalogo.crear_especie(request.form)
                try:
                    telemetria_dev.notificar_alta_dev(
                        'Especie', especie.nombre_comun,
                        {'Categoría': especie.categoria, 'pH': f"{especie.ph_min}-{especie.ph_max}", 'EC': f"{especie.ec_min}-{especie.ec_max}"}
                    )
                except Exception:
                    pass
                try:
                    telegram_bot.notificar_alta_especie(especie)
                except Exception:
                    pass
                try:
                    bitacora.registrar_evento('ALTA_ESPECIE', 'AGRONOMICO', {
                        'id': especie.id,
                        'nombre': especie.nombre_comun,
                        'categoria': especie.categoria
                    })
                except Exception:
                    pass
                flash(f'Especie "{especie.nombre_comun}" agregada al catálogo.', 'success')
                return redirect(url_for('catalogo_lista'))
            except Exception as e:
                flash(f'Error al agregar especie: {str(e)}', 'danger')
        return render_template('agregar_especie.html')
    
    @app.route('/catalogo/<int:especie_id>')
    def catalogo_detalle(especie_id):
        """Detalle de una especie."""
        especie = catalogo.obtener_especie(especie_id)
        return render_template('especie_detalle.html', especie=especie)
    
    @app.route('/catalogo/<int:especie_id>/eliminar', methods=['POST'])
    def catalogo_eliminar(especie_id):
        """Elimina una especie del catálogo."""
        try:
            catalogo.eliminar_especie(especie_id)
            try:
                bitacora.registrar_evento('BAJA_ESPECIE', 'AGRONOMICO', {'especie_id': especie_id})
            except Exception:
                pass
            flash('Especie eliminada del catálogo.', 'success')
        except Exception as e:
            flash(f'Error al eliminar: {str(e)}', 'danger')
        return redirect(url_for('catalogo_lista'))
    
    # ==================== CULTIVOS ====================
    
    @app.route('/cultivos')
    def cultivos_lista():
        """Lista de cultivos activos."""
        estado = request.args.get('estado', 'ACTIVO')
        cultivos = Cultivo.query.filter_by(estado=estado).order_by(Cultivo.created_at.desc()).all()
        return render_template('cultivos.html', cultivos=cultivos, estado=estado)
    
    @app.route('/cultivos/agregar', methods=['GET', 'POST'])
    def cultivos_agregar():
        """Agrega un nuevo cultivo."""
        if request.method == 'POST':
            try:
                cultivo = Cultivo(
                    especie_id=int(request.form['especie_id']),
                    nombre=request.form['nombre'],
                    fecha_siembra=date.fromisoformat(request.form['fecha_siembra']),
                    ubicacion=request.form.get('ubicacion', ''),
                    notas=request.form.get('notas', '')
                )
                db.session.add(cultivo)
                db.session.commit()
                try:
                    notificaciones_usuario.despachar_alta_cultivo(cultivo)
                except Exception:
                    pass
                try:
                    telemetria_dev.notificar_alta_dev(
                        'Cultivo', cultivo.nombre,
                        {
                            'Especie': cultivo.especie.nombre_comun if cultivo.especie else 'N/A',
                            'Ubicación': cultivo.ubicacion or 'N/A',
                            'Siembra': cultivo.fecha_siembra.strftime('%d/%m/%Y') if cultivo.fecha_siembra else 'N/A'
                        }
                    )
                except Exception:
                    pass
                try:
                    telegram_bot.notificar_alta_cultivo(cultivo)
                except Exception:
                    pass
                try:
                    bitacora.registrar_evento('ALTA_CULTIVO', 'AGRONOMICO', {
                        'id': cultivo.id,
                        'nombre': cultivo.nombre,
                        'especie': cultivo.especie.nombre_comun if cultivo.especie else 'N/A',
                        'ubicacion': cultivo.ubicacion
                    })
                except Exception:
                    pass
                flash(f'Cultivo "{cultivo.nombre}" creado exitosamente.', 'success')
                return redirect(url_for('cultivo_detalle', cultivo_id=cultivo.id))
            except Exception as e:
                flash(f'Error al crear cultivo: {str(e)}', 'danger')
        
        especies = Especie.query.order_by(Especie.nombre_comun).all()
        return render_template('agregar_cultivo.html', especies=especies, today=date.today().isoformat())
    
    @app.route('/cultivos/<int:cultivo_id>')
    def cultivo_detalle(cultivo_id):
        """Dashboard individual de un cultivo con lecturas, alertas, clima y Machine Learning."""
        cultivo = Cultivo.query.get_or_404(cultivo_id)
        resumen = monitoreo.obtener_resumen_cultivo(cultivo_id)
        lecturas_recientes = LecturaSensor.query.filter_by(
            cultivo_id=cultivo_id
        ).order_by(LecturaSensor.timestamp.desc()).limit(50).all()
        alertas_cultivo = Alerta.query.filter_by(
            cultivo_id=cultivo_id
        ).order_by(Alerta.created_at.desc()).limit(20).all()

        # 1. Clima exterior actual
        clima_actual = clima.obtener_clima_actual()

        # 2. Evaluación del Modelo de Machine Learning
        evaluacion_ml = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_actual)

        # 3. Análisis comparativo microclima interno vs exterior
        temp_in = resumen.get('TEMPERATURA', {}).get('valor', 22.0)
        hum_in = resumen.get('HUMEDAD', {}).get('valor', 60.0)
        temp_ext = clima_actual.get('temp_externa', 20.0)
        hum_ext = clima_actual.get('humedad_externa', 55.0)
        cat = cultivo.especie.categoria if cultivo.especie else 'PLANTA'
        analisis_clima = clima.evaluar_impacto_climatico(temp_in, hum_in, temp_ext, hum_ext, categoria=cat)

        return render_template('cultivo_detalle.html', 
                               cultivo=cultivo, 
                               resumen=resumen, 
                               lecturas=lecturas_recientes,
                               alertas_cultivo=alertas_cultivo,
                               clima=clima_actual,
                               ml=evaluacion_ml,
                               analisis_clima=analisis_clima)

    @app.route('/cultivos/<int:cultivo_id>/exportar.csv')
    def cultivo_exportar_csv(cultivo_id):
        """Descarga el historial de lecturas y clima del cultivo en formato CSV."""
        cultivo = Cultivo.query.get_or_404(cultivo_id)
        csv_data = datos_csv.exportar_cultivo_csv(cultivo_id)
        nombre_archivo = f"cultivo_{cultivo_id}_{cultivo.nombre.replace(' ', '_')}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={nombre_archivo}"}
        )

    @app.route('/cultivos/<int:cultivo_id>/importar-csv', methods=['POST'])
    def cultivo_importar_csv(cultivo_id):
        """Carga datos históricos o telemetría desde un archivo CSV subido."""
        if 'archivo_csv' not in request.files:
            flash('No se seleccionó ningún archivo CSV.', 'warning')
            return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

        archivo = request.files['archivo_csv']
        if archivo.filename == '':
            flash('Nombre de archivo vacío.', 'warning')
            return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

        contenido = archivo.read()
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_id, contenido)

        if codigo == 200:
            flash(
                f"CSV importado: {res['lecturas_importadas']} lecturas guardadas. "
                f"Alertas disparadas: {res['alertas_generadas']}.",
                'success' if res['alertas_generadas'] == 0 else 'warning'
            )
        else:
            flash(f"Error al importar CSV: {res.get('error', 'desconocido')}", 'danger')

        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

    @app.route('/cultivos/<int:cultivo_id>/reentrenar-ml', methods=['POST'])
    def cultivo_reentrenar_ml(cultivo_id):
        """Reentrena el modelo de Machine Learning con el estado actual."""
        try:
            ml_engine.entrenar_modelo(guardar=True)
            flash('¡Modelo de Machine Learning reentrenado con éxito!', 'success')
        except Exception as e:
            flash(f'Error al reentrenar modelo: {str(e)}', 'danger')
        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

    @app.route('/cultivos/<int:cultivo_id>/enviar-telegram', methods=['POST'])
    def cultivo_enviar_telegram(cultivo_id):
        """Envía el reporte biométrico y de telemetría de un cultivo a Telegram."""
        resultado = telegram_bot.enviar_reporte_telemetria_telegram(cultivo_id)
        if resultado.get('ok'):
            flash('¡Reporte de telemetría y salud IA enviado exitosamente a Telegram!', 'success')
        else:
            flash(f"No se pudo enviar a Telegram: {resultado.get('error', 'Verifica el Token y Chat ID')}", 'warning')
        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

    @app.route('/cultivos/<int:cultivo_id>/simular', methods=['POST'])
    def simular_cultivo_lecturas(cultivo_id):
        """Simula lecturas de sensores para un cultivo."""
        anomala = request.form.get('tipo_simulacion') == 'alerta'
        _, alertas_gen = monitoreo.simular_lecturas(cultivo_id, anomalas=anomala)
        if alertas_gen:
            flash(f'Simulación completada: se registraron lecturas y se generaron {len(alertas_gen)} alerta(s).', 'warning')
        else:
            flash('Simulación completada: todas las lecturas están dentro de los rangos ideales.', 'success')
        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))
    
    @app.route('/cultivos/<int:cultivo_id>/lectura', methods=['POST'])
    def registrar_lectura_sensor(cultivo_id):
        """Registra una nueva lectura de sensor."""
        try:
            tipo = request.form['tipo']
            valor = float(request.form['valor'])
            lectura, alertas_generadas = monitoreo.registrar_lectura(cultivo_id, tipo, valor)
            
            if alertas_generadas:
                for a in alertas_generadas:
                    flash(f'{a.nivel_info["icono"]} {a.mensaje}', 
                          'warning' if a.nivel == 'ADVERTENCIA' else 'danger')
            else:
                flash(f'Lectura de {lectura.tipo_info["nombre"]} registrada: {valor} {lectura.tipo_info["unidad"]}', 'success')
            try:
                bitacora.registrar_evento('LECTURA_SENSOR', 'IOT', {
                    'cultivo_id': cultivo_id,
                    'tipo': tipo,
                    'valor': valor
                })
            except Exception:
                pass
        except Exception as e:
            flash(f'Error al registrar lectura: {str(e)}', 'danger')
        
        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))
    
    @app.route('/cultivos/<int:cultivo_id>/estado', methods=['POST'])
    def cambiar_estado_cultivo(cultivo_id):
        """Cambia el estado de un cultivo."""
        cultivo = Cultivo.query.get_or_404(cultivo_id)
        nuevo_estado = request.form['estado']
        cultivo.estado = nuevo_estado
        db.session.commit()
        try:
            bitacora.registrar_evento('CAMBIO_ESTADO_CULTIVO', 'AGRONOMICO', {
                'cultivo_id': cultivo_id,
                'nombre': cultivo.nombre,
                'nuevo_estado': nuevo_estado
            })
        except Exception:
            pass
        flash(f'Estado de "{cultivo.nombre}" cambiado a {nuevo_estado}.', 'success')
        return redirect(url_for('cultivo_detalle', cultivo_id=cultivo_id))

    @app.route('/cultivos/<int:cultivo_id>/eliminar', methods=['POST'])
    def cultivo_eliminar(cultivo_id):
        """Elimina un cultivo y limpia en cascada su historial, alertas y desvincula sensores."""
        try:
            nombre = monitoreo.eliminar_cultivo(cultivo_id)
            flash(f'Cultivo "{nombre}" y todo su historial fueron eliminados exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el cultivo: {str(e)}', 'danger')
        return redirect(url_for('cultivos_lista'))
    
    # ==================== ALERTAS ====================
    
    @app.route('/alertas')
    def alertas_lista():
        """Lista de alertas."""
        solo_no_leidas = request.args.get('no_leidas', '0') == '1'
        lista_alertas = alertas.obtener_alertas(solo_no_leidas=solo_no_leidas)
        return render_template('alertas.html', alertas=lista_alertas, 
                             solo_no_leidas=solo_no_leidas)
    
    @app.route('/alertas/<int:alerta_id>/leer', methods=['POST'])
    def alerta_marcar_leida(alerta_id):
        """Marca una alerta como leída."""
        alertas.marcar_como_leida(alerta_id)
        try:
            bitacora.registrar_evento('ALERTA_LEIDA', 'AGRONOMICO', {'alerta_id': alerta_id})
        except Exception:
            pass
        return redirect(request.referrer or url_for('alertas_lista'))
    
    @app.route('/alertas/leer-todas', methods=['POST'])
    def alertas_marcar_todas_leidas():
        """Marca todas las alertas como leídas."""
        alertas.marcar_todas_leidas()
        try:
            bitacora.registrar_evento('TODAS_ALERTAS_LEIDAS', 'AGRONOMICO', {})
        except Exception:
            pass
        flash('Todas las alertas marcadas como leídas.', 'success')
        return redirect(url_for('alertas_lista'))

    # ==================== TELEGRAM (TELEMETRÍA Y ALERTAS) ====================

    @app.route('/telegram')
    def telegram_panel():
        """Panel de configuración y monitoreo de Telegram."""
        cfg = telegram_bot.obtener_config_telegram()
        cultivos = Cultivo.query.filter_by(estado='ACTIVO').order_by(Cultivo.nombre).all()
        return render_template('telegram.html', cfg=cfg, cultivos=cultivos)

    @app.route('/telegram/config', methods=['POST'])
    def telegram_guardar_config():
        """Guarda la configuración de Telegram (Token y Chat ID)."""
        bot_token = request.form.get('bot_token', '').strip()
        chat_id = request.form.get('chat_id', '').strip()
        notificaciones = request.form.get('notificaciones_activas') == '1'

        telegram_bot.guardar_config_telegram(bot_token, chat_id, notificaciones)
        flash('Configuración de Telegram guardada correctamente.', 'success')
        return redirect(url_for('telegram_panel'))

    @app.route('/telegram/probar', methods=['POST'])
    def telegram_probar():
        """Envía un mensaje de prueba al chat de Telegram configurado."""
        bot_token = request.form.get('bot_token', '').strip() or None
        chat_id = request.form.get('chat_id', '').strip() or None

        resultado = telegram_bot.probar_conexion_telegram(bot_token=bot_token, chat_id=chat_id)
        if resultado.get('ok'):
            flash('¡Mensaje de prueba enviado con éxito! Revisa tu aplicación de Telegram.', 'success')
        else:
            flash(f"Error al conectar con Telegram: {resultado.get('error', 'Verifica el Token y Chat ID')}", 'danger')
        return redirect(url_for('telegram_panel'))

    @app.route('/telegram/reporte-general', methods=['POST'])
    def telegram_enviar_general():
        """Envía un resumen general de telemetría a Telegram."""
        resultado = telegram_bot.enviar_reporte_general_telegram()
        if resultado.get('ok'):
            flash('Resumen general enviado a Telegram con éxito.', 'success')
        else:
            flash(f"Error al enviar resumen: {resultado.get('error')}", 'warning')
        return redirect(url_for('telegram_panel'))

    @app.route('/api/v1/telegram/webhook', methods=['POST'])
    def telegram_webhook():
        """
        Endpoint Webhook para recibir mensajes/comandos del Bot de Telegram.
        Procesa comandos como /start, /status, /cultivos, /telemetria, /clima, /alertas.
        """
        update = request.get_json(silent=True) or {}
        mensaje = update.get('message') or update.get('edited_message') or {}
        texto = mensaje.get('text', '')
        chat_id = mensaje.get('chat', {}).get('id')

        if texto and chat_id:
            telegram_bot.procesar_comando_telegram(texto, chat_id)

        return jsonify({'status': 'ok'}), 200

    @app.route('/api/v1/telegram/status')
    def api_telegram_status():
        """Consulta el estado actual de la integración de Telegram en formato JSON."""
        cfg = telegram_bot.obtener_config_telegram()
        return jsonify({
            'configurado': bool(cfg.get('bot_token') and cfg.get('chat_id')),
            'notificaciones_activas': cfg.get('notificaciones_activas', False),
            'origen': cfg.get('origen'),
            'chat_id': cfg.get('chat_id') if cfg.get('chat_id') else None
        })

    # ==================== CANALES DE NOTIFICACIÓN DEL USUARIO (DISCORD & TELEGRAM) ====================

    @app.route('/notificaciones')
    def notificaciones_panel():
        """Panel de configuración de notificaciones para el usuario (Telegram & Discord)."""
        cfg = notificaciones_usuario.obtener_config_notificaciones()
        return render_template('notificaciones.html', cfg=cfg)

    @app.route('/notificaciones/guardar', methods=['POST'])
    def notificaciones_guardar():
        """Guarda la configuración personalizada de canales de aviso del usuario."""
        datos = {
            'discord_activo': request.form.get('discord_activo') == '1',
            'discord_webhook_url': request.form.get('discord_webhook_url', '').strip(),
            'telegram_activo': request.form.get('telegram_activo') == '1',
            'telegram_token': request.form.get('telegram_token', '').strip(),
            'telegram_chat_id': request.form.get('telegram_chat_id', '').strip(),
            'alertas_criticas': request.form.get('alertas_criticas') == '1',
            'alertas_advertencias': request.form.get('alertas_advertencias') == '1',
            'altas_cultivos': request.form.get('altas_cultivos') == '1',
            'altas_dispositivos': request.form.get('altas_dispositivos') == '1',
        }
        notificaciones_usuario.guardar_config_notificaciones(datos)
        flash('Configuración de notificaciones guardada exitosamente.', 'success')
        return redirect(url_for('notificaciones_panel'))

    @app.route('/notificaciones/probar-discord', methods=['POST'])
    def notificaciones_probar_discord():
        """Prueba inmediata de la conexión por Discord Webhook."""
        webhook_url = request.form.get('discord_webhook_url', '').strip()
        if not webhook_url:
            flash('Por favor ingresa una URL de Webhook de Discord válida.', 'warning')
            return redirect(url_for('notificaciones_panel'))

        res = notificaciones_usuario.probar_discord(webhook_url)
        if res.get('ok'):
            flash('¡Mensaje de prueba enviado exitosamente a tu canal de Discord!', 'success')
        else:
            flash(f"Error al conectar con Discord: {res.get('error')}", 'danger')
        return redirect(url_for('notificaciones_panel'))

    @app.route('/notificaciones/probar-telegram', methods=['POST'])
    def notificaciones_probar_telegram():
        """Prueba inmediata de la conexión por el Telegram personal del usuario."""
        token = request.form.get('telegram_token', '').strip()
        chat_id = request.form.get('telegram_chat_id', '').strip()
        if not token or not chat_id:
            flash('Por favor ingresa tanto el Token del Bot como el Chat ID de Telegram.', 'warning')
            return redirect(url_for('notificaciones_panel'))

        res = notificaciones_usuario.probar_telegram_usuario(token, chat_id)
        if res.get('ok'):
            flash('¡Mensaje de prueba enviado exitosamente a tu Telegram!', 'success')
        else:
            flash(f"Error al enviar mensaje a Telegram: {res.get('error')}", 'danger')
        return redirect(url_for('notificaciones_panel'))


    # ==================== API JSON ====================
    
    @app.route('/api/dashboard')
    def api_dashboard():
        """Datos JSON para el dashboard."""
        return jsonify(monitoreo.obtener_estadisticas_dashboard())
    
    @app.route('/api/cultivo/<int:cultivo_id>/lecturas')
    def api_lecturas(cultivo_id):
        """Lecturas de un cultivo en formato JSON para gráficos."""
        tipo = request.args.get('tipo')
        horas = int(request.args.get('horas', 24))
        lecturas = monitoreo.obtener_lecturas(cultivo_id, tipo=tipo, horas=horas)
        return jsonify([l.to_dict() for l in lecturas])
    
    @app.route('/api/cultivo/<int:cultivo_id>/diagnostico-ml')
    def api_diagnostico_ml(cultivo_id):
        """Endpoint JSON con la evaluación predictiva de ML y análisis agroclimático."""
        cultivo = Cultivo.query.get_or_404(cultivo_id)
        resumen = monitoreo.obtener_resumen_cultivo(cultivo_id)
        clima_actual = clima.obtener_clima_actual()
        eval_ml = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_actual)
        return jsonify(eval_ml)
    
    # ==================== DISPOSITIVOS (IoT / HARDWARE) ====================
    
    @app.route('/dispositivos')
    def dispositivos_lista():
        """Lista de dispositivos IoT registrados y asistentes de conexión."""
        lista = dispositivos.listar_dispositivos()
        cultivos = Cultivo.query.filter_by(estado='ACTIVO').order_by(Cultivo.nombre).all()
        host_url = request.host_url.rstrip('/')
        return render_template('dispositivos.html', dispositivos=lista, cultivos=cultivos, host_url=host_url)
    
    @app.route('/dispositivos/nuevo', methods=['POST'])
    def dispositivo_nuevo():
        """Crea un nuevo dispositivo con API key única."""
        try:
            nombre = request.form['nombre']
            tipo_hardware = request.form.get('tipo_hardware', 'ESP32')
            cultivo_id = request.form.get('cultivo_id')
            cultivo_id = int(cultivo_id) if cultivo_id else None
            ubicacion = request.form.get('ubicacion', '')
            disp = dispositivos.crear_dispositivo(nombre, tipo_hardware, cultivo_id, ubicacion)
            try:
                notificaciones_usuario.despachar_alta_dispositivo(disp)
            except Exception:
                pass
            try:
                telemetria_dev.notificar_alta_dev(
                    'Dispositivo IoT', disp.nombre,
                    {
                        'Hardware': disp.tipo_hardware,
                        'Cultivo': disp.cultivo.nombre if disp.cultivo else 'Global',
                        'API Key': disp.api_key
                    }
                )
            except Exception:
                pass
            try:
                telegram_bot.notificar_alta_dispositivo(disp)
            except Exception:
                pass
            flash(f'Dispositivo "{disp.nombre}" registrado. Su API Key es: {disp.api_key}', 'success')
        except Exception as e:
            flash(f'Error al registrar dispositivo: {str(e)}', 'danger')
        return redirect(url_for('dispositivos_lista'))
    
    @app.route('/dispositivos/<int:disp_id>/eliminar', methods=['POST'])
    def dispositivo_eliminar(disp_id):
        """Elimina un dispositivo."""
        if dispositivos.eliminar_dispositivo(disp_id):
            flash('Dispositivo eliminado.', 'success')
        else:
            flash('Dispositivo no encontrado.', 'warning')
        return redirect(url_for('dispositivos_lista'))
    
    @app.route('/dispositivos/<int:disp_id>/regenerar-key', methods=['POST'])
    def dispositivo_regenerar_key(disp_id):
        """Regenera la API key de un dispositivo."""
        disp = dispositivos.regenerar_api_key(disp_id)
        flash(f'Nueva API Key para "{disp.nombre}": {disp.api_key}', 'info')
        return redirect(url_for('dispositivos_lista'))

    @app.route('/dispositivos/<int:disp_id>/descargar-firmware')
    def dispositivo_descargar_firmware(disp_id):
        """Descarga el firmware C++ (.ino) pre-rellenado para el dispositivo con 1 clic."""
        disp = dispositivos.obtener_dispositivo(disp_id)
        if not disp:
            flash('Dispositivo no encontrado.', 'warning')
            return redirect(url_for('dispositivos_lista'))
        host_url = request.host_url.rstrip('/')
        contenido = dispositivos.generar_firmware_esp32(disp, host_url=host_url)
        return Response(
            contenido,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename=hydro_{disp.nombre.replace(" ", "_")}.ino'}
        )

    @app.route('/dispositivos/descargar-firmware-form', methods=['POST'])
    def dispositivo_descargar_firmware_form():
        """Descarga el firmware C++ (.ino) con SSID y password WiFi personalizados desde el formulario rápido."""
        disp_id = request.form.get('dispositivo_id')
        disp = dispositivos.obtener_dispositivo(int(disp_id)) if disp_id else None
        if not disp:
            flash('Dispositivo no seleccionado.', 'warning')
            return redirect(url_for('dispositivos_lista'))
        wifi_ssid = request.form.get('wifi_ssid', 'MI_WIFI_RED')
        wifi_pass = request.form.get('wifi_pass', 'PASSWORD_WIFI')
        host_url = request.host_url.rstrip('/')
        contenido = dispositivos.generar_firmware_esp32(disp, host_url=host_url, wifi_ssid=wifi_ssid, wifi_pass=wifi_pass)
        return Response(
            contenido,
            mimetype='text/plain',
            headers={'Content-Disposition': f'attachment; filename=firmware_{disp.nombre.replace(" ", "_")}.ino'}
        )

    @app.route('/dispositivos/simulador-virtual', methods=['POST'])
    def dispositivo_simular_telemetria_btn():
        """Conecta un sensor virtual y envía lecturas simuladas instantáneas con 1 clic."""
        cultivo_id = request.form.get('cultivo_id')
        cultivo_id = int(cultivo_id) if cultivo_id else None
        modo = request.form.get('modo', 'normal')

        resultado, codigo, payload = dispositivos.simular_envio_telemetria(cultivo_id=cultivo_id, modo=modo)
        if codigo == 200:
            if modo == 'anomalia':
                flash(f'⚠️ [Simulador] Se inyectaron lecturas ANÓMALAS (pH 4.2, Temp 34.5°C) al cultivo ID {cultivo_id}. Verifica las alertas y el score de salud ML.', 'warning')
            else:
                flash(f'🧪 [Simulador] Telemetría virtual enviada exitosamente (pH {payload["ph"]}, Temp {payload["temperatura"]}°C, EC {payload["ec"]}).', 'success')
        else:
            flash(f'Error al simular telemetría: {resultado.get("error")}', 'danger')
        return redirect(request.referrer or url_for('dispositivos_lista'))

    # ==================== INTELIGENCIA ARTIFICIAL & ML ====================

    @app.route('/ml')
    def ml_dashboard():
        """Panel central de Inteligencia Artificial & Machine Learning."""
        metricas = ml_engine.obtener_metricas_modelo()
        clima_actual = clima.obtener_clima_actual()
        cultivos_activos = Cultivo.query.filter_by(estado='ACTIVO').all()

        diagnosticos_cultivos = []
        proyecciones_gdd = []

        for c in cultivos_activos:
            resumen = monitoreo.obtener_resumen_cultivo(c.id)
            diag = ml_engine.evaluar_salud_cultivo(c, resumen, clima_actual)
            diagnosticos_cultivos.append({
                'cultivo': c,
                'diagnostico': diag
            })

            # Proyección GDD
            temp_reciente = resumen.get('TEMPERATURA', {}).get('valor', 22.0)
            gdd = ml_engine.estimar_gdd_y_cosecha(c, temp_media=temp_reciente)
            proyecciones_gdd.append({
                'cultivo': c,
                'gdd': gdd
            })

        return render_template(
            'ml_dashboard.html',
            metricas=metricas,
            clima_actual=clima_actual,
            diagnosticos_cultivos=diagnosticos_cultivos,
            proyecciones_gdd=proyecciones_gdd
        )

    @app.route('/ml/reentrenar', methods=['POST'])
    def ml_reentrenar():
        """Reentrena el modelo de Machine Learning y registra el evento en la bitácora."""
        try:
            ml_engine.entrenar_modelo(guardar=True)
            try:
                bitacora.registrar_evento('REENTRENAMIENTO_ML', 'SISTEMA', {
                    'algoritmo': 'Random Forest Classifier',
                    'n_estimadores': 100,
                    'muestras': 1500
                })
            except Exception:
                pass
            flash('¡Modelo de Machine Learning re-entrenado y calibrado exitosamente!', 'success')
        except Exception as e:
            flash(f'Error al re-entrenar modelo de ML: {str(e)}', 'danger')
        return redirect(url_for('ml_dashboard'))

    @app.route('/api/ml/simular', methods=['POST'])
    def api_ml_simular():
        """Endpoint JSON para el simulador 'What-If' de Machine Learning en vivo."""
        datos = request.get_json(silent=True) or {}
        resultado = ml_engine.simular_prediccion(datos)
        return jsonify(resultado)

    @app.route('/api/ml/metricas')
    def api_ml_metricas():
        """Endpoint JSON que retorna las métricas de precisión y variables del modelo."""
        return jsonify(ml_engine.obtener_metricas_modelo())
    
    # ==================== TELEMETRÍA IoT & API HARDWARE ====================
    
    @app.route('/api/v1/ping')
    def api_ping():
        """Ping rápido para comprobar conexión desde microcontroladores."""
        api_key = request.args.get('api_key') or request.headers.get('X-API-Key')
        disp = dispositivos.obtener_por_api_key(api_key) if api_key else None
        return jsonify({
            'status': 'online',
            'server_time': datetime.now(timezone.utc).isoformat(),
            'dispositivo': disp.nombre if disp else None,
            'cultivo_id': disp.cultivo_id if disp else None
        })

    @app.route('/api/v1/telemetria', methods=['POST'])
    def api_telemetria():
        """
        Recibe lecturas de sensores de microcontroladores (ESP32, Raspberry Pi, Arduino).
        Soporta JSON con API key en header 'X-API-Key' o en el body 'api_key'.
        """
        datos = request.get_json(silent=True) or {}
        # Permitir API key en cabecera HTTP
        header_key = request.headers.get('X-API-Key')
        if header_key and not datos.get('api_key'):
            datos['api_key'] = header_key

        ip_origen = request.headers.get('X-Forwarded-For', request.remote_addr)
        respuesta, codigo = dispositivos.procesar_telemetria(datos, ip_origen=ip_origen)
        return jsonify(respuesta), codigo

    @app.route('/api/v1/update', methods=['GET', 'POST'])
    def api_update_simple():
        """
        Endpoint ultra-simple para microcontroladores básicos que usan GET con query params:
        GET /api/v1/update?api_key=...&ph=6.2&temp=22.1&hum=65&ec=1.3&nivel_agua=85
        """
        if request.method == 'POST':
            datos = request.form.to_dict() or request.get_json(silent=True) or {}
        else:
            datos = request.args.to_dict()

        header_key = request.headers.get('X-API-Key')
        if header_key and not datos.get('api_key'):
            datos['api_key'] = header_key

        ip_origen = request.headers.get('X-Forwarded-For', request.remote_addr)
        respuesta, codigo = dispositivos.procesar_telemetria(datos, ip_origen=ip_origen)
        return jsonify(respuesta), codigo

    @app.route('/api/dispositivos')
    def api_dispositivos():
        """Devuelve la lista de dispositivos registrados en formato JSON."""
        lista = dispositivos.listar_dispositivos()
        return jsonify([d.to_dict() for d in lista])

    @app.route('/api/alertas/count')
    def api_alertas_count():
        """Cuenta de alertas no leídas."""
        return jsonify({'count': alertas.contar_alertas_no_leidas()})
    
    # ==================== BITÁCORA CIFRADA ====================

    @app.route('/bitacora')
    def bitacora_panel():
        """Panel de visualización y auditoría de la bitácora cifrada."""
        cat_filtro = request.args.get('categoria') or None
        eventos = bitacora.leer_bitacora(limite=200, filtro_categoria=cat_filtro)
        stats = bitacora.estadisticas_bitacora()
        auditoria = bitacora.verificar_integridad_cadena()
        return render_template('bitacora.html', eventos=eventos, stats=stats, auditoria=auditoria, cat_filtro=cat_filtro)

    @app.route('/bitacora/verificar', methods=['POST'])
    def bitacora_verificar():
        """Ejecuta una verificación de integridad forense bajo demanda."""
        auditoria = bitacora.verificar_integridad_cadena()
        if auditoria.get('integra'):
            flash(f"Auditoría Exitosa: {auditoria.get('mensaje')}", 'success')
        else:
            flash(f"¡Alerta de Manipulación!: {auditoria.get('motivo')} (Línea {auditoria.get('linea_corrupta')})", 'danger')
        return redirect(url_for('bitacora_panel'))

    @app.route('/bitacora/descargar')
    def bitacora_descargar():
        """Descarga el archivo cifrado (.enc) en su estado raw para custodia offline."""
        ruta = bitacora._ruta_bitacora()
        if not os.path.exists(ruta):
            flash('No hay archivo de bitácora generado aún.', 'warning')
            return redirect(url_for('bitacora_panel'))
        with open(ruta, 'rb') as f:
            contenido = f.read()
        return Response(
            contenido,
            mimetype='application/octet-stream',
            headers={'Content-Disposition': 'attachment; filename=bitacora_cifrada.enc'}
        )

    # ==================== HEALTHCHECK & MONITOREO DE PRODUCCIÓN ====================

    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        """Sonda de salud para orquestadores (Docker, Kubernetes) y balanceadores."""
        db_status = 'ok'
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception as e:
            db_status = f'error: {str(e)}'

        ml_status = 'ok' if ml_engine.obtener_metricas_modelo().get('activo') else 'degraded'

        disk_free_mb = None
        try:
            stat = shutil.disk_usage(os.path.join(os.path.dirname(__file__), 'data'))
            disk_free_mb = round(stat.free / (1024 * 1024), 2)
        except Exception:
            pass

        es_saludable = (db_status == 'ok')
        status_code = 200 if es_saludable else 503

        return jsonify({
            'status': 'healthy' if es_saludable else 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': 'production' if not app.debug else 'development',
            'database': db_status,
            'machine_learning': ml_status,
            'disk_free_mb': disk_free_mb,
            'instance_id': telemetria_dev.obtener_id_instancia()
        }), status_code
    
    return app


# Punto de entrada
app = crear_app()

if __name__ == '__main__':
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', False)
    app.run(host=host, port=port, debug=debug)
