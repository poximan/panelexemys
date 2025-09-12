import time
import json
from src.modelo.registro_falla import RegistroFalla
from src.persistencia.dao.dao_reles import reles_dao
from src.persistencia.dao.dao_fallas_reles import fallas_reles_dao
from .modbus_driver import ModbusTcpDriver
from src.logger import Logosaurio
from src.utils.paths import load_observar_key

class ProtectionRelayClient:
    """
    Cliente para monitorear reles de proteccion via Modbus.
    Gestiona lectura de registros de falla y persistencia de la falla mas reciente.
    """
    def __init__(self, modbus_driver: ModbusTcpDriver, refresh_interval: int, logger: Logosaurio):
        """
        inicializa cliente con driver modbus compartido y periodo de refresco
        """
        self.driver = modbus_driver
        self.refresh_interval = refresh_interval
        self.logger = logger

        # ids modbus activos desde la base
        self.relay_unit_ids = list(reles_dao.get_all_reles_with_descriptions().keys())

        self._last_observing_status = None

        if not self.relay_unit_ids:
            self.logger.log(
                "No se encontraron IDs de reles activos para monitorear en la base de datos. El cliente de reles estara inactivo.",
                origen="OBS/RELE"
            )
        else:
            self.logger.log(f"Monitoreando reles con Unit IDs: {self.relay_unit_ids}", origen="OBS/RELE")

    def _is_observing_enabled(self) -> bool:
        """
        consulta bandera 'reles_consultar' desde observar.json
        """
        try:
            return bool(load_observar_key("reles_consultar", False))
        except Exception as e:
            self.logger.log(f"ERROR al leer clave reles_consultar: {e}", origen="OBS/RELE")
            return False

    def read_relay_status(self, relay_id: int):
        """
        lee registros de falla de un rele y guarda la falla mas reciente si es nueva
        """
        start_address = int('3700', 16)
        end_address = int('3718', 16)
        num_registers_per_fault = 15

        all_fault_records = []

        for current_address in range(start_address, end_address + 1):
            if not self._is_observing_enabled():
                self.logger.log(
                    f"Monitoreo deshabilitado durante la lectura de Rele (Unit ID: {relay_id}). Deteniendo lectura en Addr {hex(current_address)}.",
                    origen="OBS/RELE"
                )
                return None

            self.logger.log(
                f"Rele (Unit ID: {relay_id}) - Leyendo registro Addr {hex(current_address)} (Decimal: {current_address})",
                origen="OBS/RELE"
            )

            registers = self.driver.read_holding_registers(current_address, num_registers_per_fault, unit_id=relay_id)

            if registers:
                try:
                    registro_falla = RegistroFalla(registers, self.logger)
                    all_fault_records.append(registro_falla)
                    self.logger.log(
                        f"Rele (Unit ID: {relay_id}) - Registro {hex(current_address)} decodificado. Falla nro {registro_falla.fault_number}",
                        origen="OBS/RELE"
                    )
                except ValueError as e:
                    self.logger.log(
                        f"ERROR al decodificar registros de falla desde Addr {hex(current_address)} para Unit ID {relay_id}: {e}. Registros brutos: {registers}",
                        origen="OBS/RELE"
                    )
                except Exception as e:
                    self.logger.log(
                        f"ERROR inesperado al procesar registros desde Addr {hex(current_address)} para Unit ID {relay_id}: {e}",
                        origen="OBS/RELE"
                    )
            else:
                self.logger.log(
                    f"Fallo al leer {num_registers_per_fault} registros desde Addr {hex(current_address)} de Rele (Unit ID {relay_id}).",
                    origen="OBS/RELE"
                )

        if all_fault_records:
            latest_fault_record = None
            max_fault_number = -1

            for record in all_fault_records:
                if record.fault_number is not None and isinstance(record.fault_number, int) and record.fault_number > max_fault_number:
                    max_fault_number = record.fault_number
                    latest_fault_record = record

            if latest_fault_record:
                self.logger.log(
                    f"Falla mas reciente encontrada para Rele (Unit ID {relay_id}) con Numero de Falla: {latest_fault_record.fault_number}.",
                    origen="OBS/RELE"
                )

                internal_rele_id = reles_dao.get_internal_id_by_modbus_id(relay_id)

                if internal_rele_id is not None:
                    fault_timestamp_iso = latest_fault_record.fault_datetime.isoformat() if latest_fault_record.fault_datetime else None

                    if not fallas_reles_dao.falla_exists(internal_rele_id, latest_fault_record.fault_number, fault_timestamp_iso):
                        fallas_reles_dao.insert_falla_rele(
                            id_rele=internal_rele_id,
                            numero_falla=latest_fault_record.fault_number,
                            timestamp=fault_timestamp_iso,
                            fasea_corr=latest_fault_record.current_phase_a,
                            faseb_corr=latest_fault_record.current_phase_b,
                            fasec_corr=latest_fault_record.current_phase_c,
                            tierra_corr=latest_fault_record.earth_current
                        )
                        self.logger.log("Falla insertada en la DB", origen="OBS/RELE")
                    else:
                        self.logger.log(
                            f"Falla (Nro {latest_fault_record.fault_number}, Timestamp: {fault_timestamp_iso}) para Rele interno ID {internal_rele_id} ya existe en la DB. No se reinserta.",
                            origen="OBS/RELE"
                        )
                else:
                    self.logger.log(
                        f"No se pudo encontrar el ID interno para el rele Modbus ID {relay_id}. No se registrara la falla en la BD.",
                        origen="OBS/RELE"
                    )
                    return None

                return latest_fault_record.to_dict()
            else:
                self.logger.log(
                    "No se pudo determinar la falla mas reciente a pesar de haber registros decodificados.",
                    origen="OBS/RELE"
                )
                return None
        else:
            self.logger.log(
                f"No se encontraron registros de falla validos para Rele (Unit ID {relay_id}) en el rango {hex(start_address)}-{hex(end_address)}.",
                origen="OBS/RELE"
            )
            return None

    def start_monitoring_loop(self):
        """
        bucle continuo de monitoreo de reles activos
        """
        self.logger.log(
            f"Iniciando observador de Reles (Host: {self.driver.host}:{self.driver.port}, Intervalo: {self.refresh_interval}s)...",
            origen="OBS/RELE"
        )

        while True:
            current_observing_status = self._is_observing_enabled()

            if current_observing_status != self._last_observing_status:
                if not current_observing_status:
                    self.logger.log("Monitoreo de Reles MiCOM PAUSADO", origen="OBS/RELE")
                else:
                    self.logger.log("Monitoreo de Reles MiCOM REANUDADO", origen="OBS/RELE")
                self._last_observing_status = current_observing_status

            if not current_observing_status:
                time.sleep(self.refresh_interval)
                continue

            if not self.driver.is_connected():
                if not self.driver.connect():
                    self.logger.log(
                        "No se pudo establecer conexion con el servidor Modbus. Reintentando en el proximo ciclo.",
                        origen="OBS/RELE"
                    )
                    time.sleep(self.refresh_interval)
                    continue

            if not self.relay_unit_ids:
                self.logger.log("No hay reles activos para monitorear. Esperando...", origen="OBS/RELE")
                time.sleep(self.refresh_interval)
                continue

            for relay_id in self.relay_unit_ids:
                self.logger.log(f"Comienza iteracion sobre rele {relay_id}", origen="OBS/RELE")
                self.read_relay_status(relay_id)

            time.sleep(self.refresh_interval)