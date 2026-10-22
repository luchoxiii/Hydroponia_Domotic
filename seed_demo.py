"""Script para inicializar datos de demostración con plantas y hongos."""
from datetime import date, timedelta
from app import app
from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from services.monitoreo import registrar_lectura, simular_lecturas


def poblar_datos_demo():
    with app.app_context():
        # Crear dispositivos demo si no existen aún
        from models.dispositivo import Dispositivo
        if Dispositivo.query.count() == 0:
            c_first = Cultivo.query.first()
            c_second = Cultivo.query.offset(1).first()
            d1 = Dispositivo(
                nombre='ESP32 - Módulo NFT 1',
                tipo_hardware='ESP32',
                api_key='hydro_demo_esp32_nft1',
                cultivo_id=c_first.id if c_first else None,
                ubicacion='Invernadero Principal - Canal A'
            )
            d2 = Dispositivo(
                nombre='Sensor Humedad - Cámara Hongos',
                tipo_hardware='MicroPython',
                api_key='hydro_demo_pico_hongos',
                cultivo_id=c_second.id if c_second else None,
                ubicacion='Cámara Húmeda B'
            )
            db.session.add_all([d1, d2])
            db.session.commit()
            print("Creados dispositivos IoT demo con claves API preconfiguradas.")

        # Verificar si ya existen cultivos
        if Cultivo.query.count() > 0:
            print("Ya existen cultivos registrados. Omitiendo poblar cultivos demo.")
            return

        # 1. Planta: Lechuga Butterhead
        esp_lechuga = Especie.query.filter_by(nombre_comun='Lechuga Butterhead').first()
        if esp_lechuga:
            c1 = Cultivo(
                especie_id=esp_lechuga.id,
                nombre='Lechugas NFT - Canal 1',
                fecha_siembra=date.today() - timedelta(days=18),
                ubicacion='Módulo NFT A-1',
                estado='ACTIVO',
                notas='Solución nutritiva general para hojas verdes. Crecimiento óptimo.'
            )
            db.session.add(c1)
            db.session.commit()
            print(f"Creado cultivo: {c1.nombre} (ID: {c1.id})")
            # Generar lecturas en rango
            simular_lecturas(c1.id, anomalas=False)

        # 2. Hongo: Seta Ostra
        esp_seta = Especie.query.filter_by(nombre_comun='Seta Ostra').first()
        if esp_seta:
            c2 = Cultivo(
                especie_id=esp_seta.id,
                nombre='Seta Ostra - Cámara Húmeda',
                fecha_siembra=date.today() - timedelta(days=10),
                ubicacion='Cámara Húmeda Bloque B',
                estado='ACTIVO',
                notas='Sustrato esterilizado en paja y café. Etapa de fructificación.'
            )
            db.session.add(c2)
            db.session.commit()
            print(f"Creado cultivo: {c2.nombre} (ID: {c2.id})")
            # Generar lecturas en rango para hongo
            simular_lecturas(c2.id, anomalas=False)

        # 3. Planta con alertas: Tomate Cherry
        esp_tomate = Especie.query.filter_by(nombre_comun='Tomate Cherry').first()
        if esp_tomate:
            c3 = Cultivo(
                especie_id=esp_tomate.id,
                nombre='Tomates Cherry - Cubo Holandés',
                fecha_siembra=date.today() - timedelta(days=32),
                ubicacion='Línea de Goteo C-3',
                estado='ACTIVO',
                notas='Iniciando floración. Monitoreando consumo de agua y nutrientes.'
            )
            db.session.add(c3)
            db.session.commit()
            print(f"Creado cultivo: {c3.nombre} (ID: {c3.id})")
            # Forzar lecturas con anomalías para que genere alertas demostrativas
            simular_lecturas(c3.id, anomalas=True)

        # 4. Dispositivos demo
        from models.dispositivo import Dispositivo
        if Dispositivo.query.count() == 0:
            d1 = Dispositivo(
                nombre='ESP32 - Módulo NFT 1',
                tipo_hardware='ESP32',
                api_key='hydro_demo_esp32_nft1',
                cultivo_id=1,
                ubicacion='Invernadero Principal - Canal A'
            )
            d2 = Dispositivo(
                nombre='Sensor Humedad - Cámara Hongos',
                tipo_hardware='MicroPython',
                api_key='hydro_demo_pico_hongos',
                cultivo_id=2,
                ubicacion='Cámara Húmeda B'
            )
            db.session.add_all([d1, d2])
            db.session.commit()
            print("Creados 2 dispositivos IoT demo con claves API preconfiguradas.")

        print("¡Datos de demostración cargados exitosamente!")


if __name__ == '__main__':
    poblar_datos_demo()
