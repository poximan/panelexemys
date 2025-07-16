import threading
from src.logger import Logosaurio
import config
from .modbus_driver import ModbusTcpDriver
from .server_mb_middleware import GrdMiddlewareClient
from .server_mb_reles import ProtectionRelayClient

def start_modbus_orchestrator(logger: Logosaurio):
    """
    Funcion principal para iniciar y orquestar los observadores Modbus.
    """    
    logger.log("Iniciando la aplicacion de Observadores Modbus (Orquestador)...", origen="OBS/MAIN")

    # --- 1. Inicializacion del Driver Modbus Centralizado ---
    logger.log(f"Creando driver Modbus TCP para {config.MB_HOST}:{config.MB_PORT}...", origen="OBS/MAIN")
    try:
        common_modbus_driver = ModbusTcpDriver(
            host=config.MB_HOST, 
            port=config.MB_PORT,
            timeout=5,
            logger=logger
        )
    except Exception as e:
        logger.log(f"Error al crear el driver Modbus: {e}. Saliendo...", origen="OBS/MAIN")
        return

    # --- 2. Inicializacion del Cliente de GRD Middleware ---
    logger.log("Inicializando cliente GRD Middleware...", origen="OBS/MAIN")
    grd_client = GrdMiddlewareClient(
        modbus_driver=common_modbus_driver,
        default_unit_id=config.MB_ID,
        register_count=config.MB_COUNT,
        refresh_interval=config.MB_INTERVAL_SECONDS,
        logger=logger
    )

    # --- 3. Inicializacion del Cliente de Reles de Proteccion ---
    logger.log("Inicializando cliente Reles de Proteccion...", origen="OBS/MAIN")
    protection_relay_client = ProtectionRelayClient(
        modbus_driver=common_modbus_driver,
        refresh_interval=config.MB_INTERVAL_SECONDS,
        logger=logger
    )

    # --- 4. Iniciar los bucles de observacion en hilos separados ---
    logger.log("Lanzando observadores en hilos separados...", origen="OBS/MAIN")
    grd_thread = threading.Thread(target=grd_client.start_observer_loop, daemon=True)
    relay_thread = threading.Thread(target=protection_relay_client.start_monitoring_loop, daemon=True)

    grd_thread.start()
    relay_thread.start()
    
    logger.log("Orquestador Modbus iniciado e hilos lanzados.", origen="OBS/MAIN")
    
    try:
        while True:
            threading.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.log("Orquestador detenido por el usuario.", origen="OBS/MAIN")
        common_modbus_driver.disconnect()
        logger.log("Conexion Modbus cerrada. Proceso finalizado.", origen="OBS/MAIN")