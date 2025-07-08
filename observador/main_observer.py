import threading
from .modbus_driver import ModbusTcpDriver
from .server_mb_middleware import GrdMiddlewareClient
from .server_mb_reles import ProtectionRelayClient
import config

def start_modbus_orchestrator():
    """
    Funcion principal para iniciar y orquestar los observadores Modbus.
    Esta funcion es diseÃ±ada para ser llamada desde el proceso principal de una aplicacion mayor.
    """
    print("Iniciando la aplicacion de Observadores Modbus (Orquestador)...")

    # --- 1. Inicializacion del Driver Modbus Centralizado ---
    print(f"Creando driver Modbus TCP para {config.MB_HOST}:{config.MB_PORT}...")
    common_modbus_driver = ModbusTcpDriver(host=config.MB_HOST, port=config.MB_PORT)

    # --- 2. Inicializacion del Cliente de GRD Middleware ---
    print("Inicializando cliente GRD Middleware...")
    grd_client = GrdMiddlewareClient(
        modbus_driver=common_modbus_driver,
        default_unit_id=config.MB_ID, # Unit ID 22, especÃ­fico para los GRDs
        register_count=config.MB_COUNT,
        refresh_interval=config.MB_INTERVAL_SECONDS
    )

    # --- 3. Inicializacion del Cliente de RelÃ©s de ProtecciÃ³n ---
    print("Inicializando cliente Reles de Proteccion...")
    protection_relay_client = ProtectionRelayClient(
        modbus_driver=common_modbus_driver,
        refresh_interval=config.MB_INTERVAL_SECONDS
    )

    # --- 4. Iniciar los bucles de observacion en hilos separados ---
    print("Lanzando observadores en hilos separados...")
    grd_thread = threading.Thread(target=grd_client.start_observer_loop, daemon=True)
    relay_thread = threading.Thread(target=protection_relay_client.start_monitoring_loop, daemon=True)

    grd_thread.start()
    relay_thread.start()    
    
    print("Orquestador Modbus iniciado y hilos lanzados.")