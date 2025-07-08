import time
from .modbus_driver import ModbusTcpDriver # Importacion relativa
from modelo.registro_falla import RegistroFalla
import config

class ProtectionRelayClient:
    """
    Cliente especifico para interactuar con reles de proteccion a traves de Modbus TCP.
    Utiliza un ModbusTcpDriver para la comunicacion.
    """
    def __init__(self, modbus_driver: ModbusTcpDriver, refresh_interval: int):
        """
        Inicializa el cliente de reles de proteccion.

        Args:
            modbus_driver (ModbusTcpDriver): Instancia del driver Modbus compartido.
            refresh_interval (int): Intervalo de tiempo en segundos para el monitoreo de reles.
        """
        self.driver = modbus_driver
        self.refresh_interval = refresh_interval
        self.relay_unit_ids = self._get_active_relay_ids()
        
        if not self.relay_unit_ids:
            print("ADVERTENCIA (Relay Client): No se encontraron IDs de reles activos para monitorear en config.ESCLAVOS_MB. El cliente de reles estara inactivo.")
        else:
            print(f"Relay Client: Monitoreando reles con Unit IDs: {self.relay_unit_ids}")

    def _get_active_relay_ids(self) -> list[int]:
        """
        Genera la lista de Unit IDs de reles activos desde config.ESCLAVOS_MB,
        excluyendo aquellos con la descripcion "NO APLICA".
        """
        active_ids = []
        for unit_id, description in config.ESCLAVOS_MB.items():
            if "NO APLICA" not in description:
                active_ids.append(unit_id)
        return active_ids

    def read_relay_status(self, relay_id: int):
        """
        Lee el estado de un rele especifico usando Modbus Function Code 03 (Read Holding Registers).
        La direccion 0x3700 (14080 decimal) y la cantidad de registros (15)

        Args:
            relay_id (int): El Unit ID del rele a leer.

        Returns:
            list[int]: Lista de valores de los registros leido, o None en caso de fallo.
        """
        # Direccion de los registros de estado del rele (offset 0x3700)
        # Convertimos '3700' hexadecimal a su valor entero decimal: 14080
        status_address = int('3700', 16) 
        num_registers = 15 # Cantidad de registros a leer, segun documentacion del rele

        print(f"Relay Client: Leyendo estado de Rele (Unit ID: {relay_id}) en Addr {hex(status_address)} (Decimal: {status_address})...")
        registers = self.driver.read_holding_registers(status_address, num_registers, unit_id=relay_id)
        
        if registers:
            try:
                # ¡Aqui creamos la instancia de RegistroFalla!
                registro_falla = RegistroFalla(registers)
                print(f"Relay Client: Falla decodificada para Rele (Unit ID {relay_id}):")
                print(f"   Numero de Falla: {registro_falla.fault_number}")
                print(f"   Fecha/Hora Falla: {registro_falla.fault_datetime}")
                print(f"   Tipo de Falla: {registro_falla.fault_type}")
                print(f"   Fases Intervinientes: {registro_falla.involved_phases_type}")
                print(f"   Corriente Fase A: {registro_falla.current_phase_a}")
                print(f"   Corriente Fase B: {registro_falla.current_phase_b}") # <-- Podrias añadir mas aqui
                print(f"   Corriente Fase C: {registro_falla.current_phase_c}") # <-- Mas impresiones
                print(f"   Corriente Tierra: {registro_falla.earth_current}")   # <-- Mas impresiones
                print(f"   Reconocida: {registro_falla.recognized}")
                # *** INICIO DE LAS POSIBLES MODIFICACIONES/ADICIONES ***
                if registro_falla.fault_datetime: # Solo si la fecha es valida
                    print(f"   Dia de la Semana: {registro_falla.fault_day_of_week}")
                    print(f"   Temporada: {registro_falla.fault_season}")
                    print(f"   Validez Fecha: {registro_falla.fault_date_validity}")
                # *** FIN DE LAS POSIBLES MODIFICACIONES/ADICIONES ***
                
                return registro_falla.to_dict() # Retorna un diccionario con los datos decodificados
            except ValueError as e:
                print(f"Relay Client: ERROR al decodificar registros de falla para Unit ID {relay_id}: {e}")
                print(f"Registros brutos: {registers}")
                return None
        else:
            print(f"Relay Client: Fallo al leer registros de falla de Rele (Unit ID {relay_id}).")
            return None
    
    def start_monitoring_loop(self):
        """
        Inicia un bucle continuo para monitorear el estado de todos los reles
        configurados en `self.relay_unit_ids`.
        """
        print(f"Iniciando monitoreo de Reles de Proteccion (Host: {self.driver.host}:{self.driver.port}, Intervalo: {self.refresh_interval}s)...")
        
        while True:
            # Intenta conectar el driver Modbus si no esta conectado.
            # No se intenta reconectar si ya esta conectado.
            if not self.driver.is_connected():
                if not self.driver.connect():
                    print("Relay Client: No se pudo establecer conexion con el servidor Modbus. Reintentando en el proximo ciclo.")
                    time.sleep(self.refresh_interval)
                    continue # Vuelve al inicio del bucle para reintentar la conexion

            # Si la lista de reles esta vacia (por ejemplo, despues del filtrado 'NO APLICA'),
            # el cliente espera sin intentar lecturas.
            if not self.relay_unit_ids:
                print("Relay Client: No hay reles activos para monitorear. Esperando...")
                time.sleep(self.refresh_interval)
                continue # Vuelve al inicio del bucle para revisar mas tarde

            # Itera sobre cada rele activo y lee su estado
            for relay_id in self.relay_unit_ids:
                print(f"Controlando rele {relay_id}")
                self.read_relay_status(relay_id)
                # Aqui podrias añadir logica adicional basada en el estado leido,
                # como enviar alertas, actualizar una base de datos especifica de reles, etc.
            
            # Espera el intervalo definido antes de la siguiente ronda de monitoreo
            time.sleep(self.refresh_interval)