import time
from datetime import datetime
from src.persistencia.dao_historicos import historicos_dao as dao
from src.persistencia.dao_grd import grd_dao
from src.logger import Logosaurio
from .modbus_driver import ModbusTcpDriver

class GrdMiddlewareClient:
    """
    Cliente especifico para monitorear el estado de los GRDs a traves de Modbus.
    Utiliza un ModbusTcpDriver para la comunicacion.
    """
    def __init__(self, modbus_driver: ModbusTcpDriver, default_unit_id: int,
                 register_count: int, refresh_interval: int, logger: Logosaurio):
        
        self.driver = modbus_driver
        self.default_unit_id = default_unit_id
        self.register_count = register_count
        self.refresh_interval = refresh_interval
        self.logger = logger
        self._active_grd_data = None
        self._last_grd_data_refresh = 0

    def _refresh_grd_data(self):
        """Refresca la lista de GRDs activos desde la base de datos."""
        if time.time() - self._last_grd_data_refresh > 2000:
            self._active_grd_data = grd_dao.get_all_grds_with_descriptions()
            self._last_grd_data_refresh = time.time()
            if not self._active_grd_data:
                self.logger.log(
                    "No se encontraron GRDs activos en la base de datos para monitorear.", 
                    origen="OBS/MW"
                )
            else:
                self.logger.log(f"GRDs activos: {list(self._active_grd_data.keys())}", origen="OBS/MW")

    def get_bit(self, value: int, bit_index: int) -> int:
        """Retorna el estado de un bit especifico en un entero."""
        return (value >> bit_index) & 1

    def start_observer_loop(self):
        """
        Inicia el bucle de observacion para los GRDs.
        Lee el estado 'conectado' e lo inserta en la DB si hay cambios.
        """
        self.logger.log(f"Iniciando observador de GRD Middleware (Unit ID: {self.default_unit_id}, Intervalo: {self.refresh_interval}s)...",
                        origen="OBS/MW"
                        )
        
        while True:
            self._refresh_grd_data()
            grd_ids_to_monitor = list(self._active_grd_data.keys()) if self._active_grd_data else []

            if not grd_ids_to_monitor:
                self.logger.log("No hay GRDs para monitorear. Esperando...", origen="OBS/MW")
                time.sleep(self.refresh_interval)
                continue

            timestamp_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if not self.driver.is_connected() and not self.driver.connect():
                self.logger.log(
                    "No se pudo establecer conexion con el servidor Modbus. Reintentando en el proximo ciclo.",
                    origen="OBS/MW"
                )
                time.sleep(self.refresh_interval)
                continue

            for grd_id in grd_ids_to_monitor:
                if grd_id == 4:
                    self.logger.log(f"Omitiendo GRD_ID {grd_id} del monitoreo.", origen="OBS/MW")
                    continue

                grd_description = self._active_grd_data.get(grd_id, "Desconocido")
                modbus_start_address_offset = (grd_id - 1) * self.register_count
                
                registers_data = self.driver.read_input_registers(
                    modbus_start_address_offset, 
                    self.register_count, 
                    unit_id=self.default_unit_id
                )
                
                if registers_data is not None and len(registers_data) >= self.register_count:
                    reg_16_value = registers_data[15]
                    current_connected_value = self.get_bit(reg_16_value, 0)
                else:
                    self.logger.log(
                        f"Fallo al leer registros para GRD_ID {grd_id} ({grd_description}). Asumiendo estado DESCONECTADO.",
                        origen="OBS/MW"
                    )
                    current_connected_value = 0

                latest_value_in_db_for_grd = dao.get_latest_connected_state_for_grd(grd_id)

                if current_connected_value != latest_value_in_db_for_grd:
                    self.logger.log(
                        f"Cambio detectado en ({grd_description}): "
                        f"observado (MB) {current_connected_value}, anterior (BD): {latest_value_in_db_for_grd}",
                        origen="OBS/MW"
                    )
                    dao.insert_historico_reading(grd_id, timestamp_now, current_connected_value)
                
            time.sleep(self.refresh_interval)