import time
from datetime import datetime
from .modbus_driver import ModbusTcpDriver
from persistencia.dao_historicos import historicos_dao as dao
from persistencia.dao_grd import grd_dao

class GrdMiddlewareClient:
    """
    Cliente específico para monitorear el estado de los GRDs a través de Modbus.
    Utiliza un ModbusTcpDriver para la comunicación.
    """
    def __init__(self, modbus_driver: ModbusTcpDriver, default_unit_id: int, register_count: int, refresh_interval: int = 2000):
        self.driver = modbus_driver
        self.default_unit_id = default_unit_id
        self.register_count = register_count
        self.refresh_interval = refresh_interval
        self._active_grd_data = None # Caché de GRDs activos
        self._last_grd_data_refresh = 0 # Tiempo del último refresh

    def _refresh_grd_data(self):
        """Refresca la lista de GRDs activos desde la base de datos."""
        # Limitar la frecuencia de consulta a la DB si no es un cambio crítico
        if time.time() - self._last_grd_data_refresh > 2000:
            self._active_grd_data = grd_dao.get_all_grds_with_descriptions()
            self._last_grd_data_refresh = time.time()
            if not self._active_grd_data:
                print("ADVERTENCIA (GRD Client): No se encontraron GRDs activos en la base de datos para monitorear.")
            else:
                print(f"GRD Client: GRDs activos para monitorear actualizados: {list(self._active_grd_data.keys())}")


    def get_bit(self, value: int, bit_index: int) -> int:
        """Retorna el estado de un bit específico en un entero."""
        return (value >> bit_index) & 1

    def start_observer_loop(self):
        """
        Inicia el bucle de observación para los GRDs.
        Lee el estado 'conectado' e lo inserta en la DB si hay cambios.
        """
        print(f"Iniciando observador de GRD Middleware (Unit ID: {self.default_unit_id}, Intervalo: {self.refresh_interval}s)...")
        
        while True:
            self._refresh_grd_data() # Asegura que la lista de GRDs esté actualizada
            grd_ids_to_monitor = list(self._active_grd_data.keys()) if self._active_grd_data else []

            if not grd_ids_to_monitor:
                print("GRD Client: No hay GRDs para monitorear. Esperando...")
                time.sleep(self.refresh_interval)
                continue

            timestamp_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Asegurar conexión del driver al inicio del ciclo de monitoreo
            if not self.driver.is_connected() and not self.driver.connect():
                print("GRD Client: No se pudo establecer conexión con el servidor Modbus. Reintentando en el próximo ciclo.")
                time.sleep(self.refresh_interval)
                continue # Saltar al siguiente ciclo

            for grd_id in grd_ids_to_monitor:
                grd_description = self._active_grd_data.get(grd_id, "Desconocido")
                modbus_start_address_offset = (grd_id - 1) * self.register_count
                
                registers_data = self.driver.read_input_registers(modbus_start_address_offset, self.register_count, unit_id=self.default_unit_id)
                
                if registers_data is not None and len(registers_data) >= self.register_count:
                    # El registro 16 está en el índice 15 (0-indexed)
                    reg_16_value = registers_data[15]
                    current_connected_value = self.get_bit(reg_16_value, 0)
                else:
                    # Si la lectura Modbus falla o no retorna suficientes datos, asume desconectado.
                    print(f"GRD Client: ADVERTENCIA: Fallo al leer registros para GRD_ID {grd_id} ({grd_description}). Asumiendo estado DESCONECTADO.")
                    current_connected_value = 0 # Asume desconectado en caso de fallo de lectura

                latest_value_in_db_for_grd = dao.get_latest_connected_state_for_grd(grd_id)

                if current_connected_value != latest_value_in_db_for_grd:
                    print(f"¡Cambio detectado para GRD_ID {grd_id} ({grd_description}): observado (MB) {current_connected_value}, anterior (BD): {latest_value_in_db_for_grd}. Actualizando.")
                    dao.insert_historico_reading(grd_id, timestamp_now, current_connected_value)             

            time.sleep(self.refresh_interval)