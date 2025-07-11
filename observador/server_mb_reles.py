import time
import os # Importar el modulo os para manejar rutas de archivo
from .modbus_driver import ModbusTcpDriver # Importacion relativa
from modelo.registro_falla import RegistroFalla
import config
from persistencia.dao_reles import reles_dao # Importa el DAO para la tabla 'reles'
from persistencia.dao_fallas_reles import fallas_reles_dao # Importa el nuevo DAO para la tabla 'fallas_reles'

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
        
        # Obtener los IDs de los reles activos directamente desde el DAO de reles
        # Se asume que get_all_reles_with_descriptions ya filtra los "NO APLICA"
        self.relay_unit_ids = list(reles_dao.get_all_reles_with_descriptions().keys())
        
        # Construir la ruta absoluta al archivo observar.txt al inicializar
        # Asumiendo que 'observar.txt' esta en el MISMO directorio que 'server_mb_reles.py'.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.observar_file_path = os.path.join(script_dir, 'observar.txt') # Ruta corregida

        # Variable para almacenar el ultimo estado de observacion reportado
        self._last_observing_status = None 

        if not self.relay_unit_ids:
            print("ADVERTENCIA (Relay Client): No se encontraron IDs de reles activos para monitorear en la base de datos. El cliente de reles estara inactivo.")
        else:
            print(f"Relay Client: Monitoreando reles con Unit IDs: {self.relay_unit_ids}")

    def _is_observing_enabled(self) -> bool:
        """
        Lee el estado del archivo observar.txt.
        Retorna True si el contenido es 'true' (ignorando mayusculas/minusculas), False en caso contrario.
        Maneja el caso de que el archivo no exista o haya errores de lectura.
        """
        if not os.path.exists(self.observar_file_path):
            # Si el archivo no existe, asumimos que la observacion esta deshabilitada.
            return False
        try:
            with open(self.observar_file_path, 'r') as f:
                content = f.read().strip().lower()
                is_enabled = (content == 'true') 
                return is_enabled
        except Exception as e:
            print(f"ERROR al leer el estado de observacion desde {self.observar_file_path}: {e}")
            return False

    def read_relay_status(self, relay_id: int):
        """
        Lee el estado de un rele especifico usando Modbus Function Code 03 (Read Holding Registers).
        Para cada rele, lee consecutivamente bloques de 15 registros, comenzando desde la direccion 0x3700
        hasta la direccion 0x3718. Cada una de estas direcciones se considera el inicio de un posible
        registro de falla. De todos los registros de falla leidos, se selecciona y retorna aquel
        que tenga el 'fault_number' mas grande.

        Args:
            relay_id (int): El Unit ID del rele a leer.

        Returns:
            dict: Diccionario con los datos decodificados del RegistroFalla con el mayor fault_number,
                  o None en caso de fallo o si no se encuentran registros validos.
        """
        start_address = int('3700', 16) # Direccion de inicio del primer posible registro de falla
        end_address = int('3718', 16)   # Direccion de inicio del ultimo posible registro de falla
        num_registers_per_fault = 15    # Cantidad de registros que componen un objeto RegistroFalla

        all_fault_records = [] # Lista para almacenar todos los objetos RegistroFalla leidos exitosamente

        # Itera sobre cada direccion de inicio de los posibles registros de falla
        for current_address in range(start_address, end_address + 1):
            # *** VERIFICACION DE OBSERVACION EN CADA INTENTO DE LECTURA DE REGISTRO ***
            # Si la observacion se deshabilita, se detienen las lecturas Modbus de inmediato.
            if not self._is_observing_enabled():
                print(f"Relay Client: Monitoreo deshabilitado durante la lectura de Rele (Unit ID: {relay_id}). Deteniendo lectura en Addr {hex(current_address)}.")
                return None # Detiene la lectura de este rele y retorna inmediatamente

            print(f"Rele (Unit ID: {relay_id}) - Leyendo registro Addr {hex(current_address)} (Decimal: {current_address})")
            
            # Lee 15 registros (un bloque completo para un RegistroFalla) desde la direccion actual
            registers = self.driver.read_holding_registers(current_address, num_registers_per_fault, unit_id=relay_id)
            
            if registers:
                try:
                    # Intenta crear una instancia de RegistroFalla con los registros leidos
                    registro_falla = RegistroFalla(registers)
                    all_fault_records.append(registro_falla)
                    print(f"Rele (Unit ID: {relay_id}) - Registro {hex(current_address)} decodificado. Falla nº{registro_falla.fault_number}")
                except ValueError as e:
                    print(f"Relay Client: ERROR al decodificar registros de falla desde Addr {hex(current_address)} para Unit ID {relay_id}: {e}. Registros brutos: {registers}")
                except Exception as e: # Captura cualquier otra excepcion durante la creacion de RegistroFalla
                    print(f"Relay Client: ERROR inesperado al procesar registros desde Addr {hex(current_address)} para Unit ID {relay_id}: {e}")
            else:
                print(f"Relay Client: Fallo al leer {num_registers_per_fault} registros desde Addr {hex(current_address)} de Rele (Unit ID {relay_id}).")
        
        # Despues de intentar leer todos los posibles registros de falla, encontrar el que tenga el fault_number mas grande
        if all_fault_records:
            # Encontrar el registro con el fault_number mas grande
            latest_fault_record = None
            # Inicializar con un valor que asegure que el primer fault_number valido sera mayor
            max_fault_number = -1 

            for record in all_fault_records:
                # Asegurarse de que fault_number sea un valor numerico valido antes de comparar
                if record.fault_number is not None and isinstance(record.fault_number, int) and record.fault_number > max_fault_number:
                    max_fault_number = record.fault_number
                    latest_fault_record = record
            
            if latest_fault_record:
                print(f"Relay Client: Falla mas reciente encontrada para Rele (Unit ID {relay_id}) con Numero de Falla: {latest_fault_record.fault_number}.")
                
                # *** INSERCION EN LA BASE DE DATOS ***
                # Primero, obtener el ID interno del rele desde la tabla 'reles'
                internal_rele_id = reles_dao.get_internal_id_by_modbus_id(relay_id)
                
                if internal_rele_id is not None:
                    # Convertir el timestamp del objeto RegistroFalla a formato ISO para la base de datos
                    fault_timestamp_iso = latest_fault_record.fault_datetime.isoformat() if latest_fault_record.fault_datetime else None

                    # Verificar si la falla ya existe antes de insertar
                    if not fallas_reles_dao.falla_exists(internal_rele_id, latest_fault_record.fault_number, fault_timestamp_iso):
                        # Insertar la falla en la tabla 'fallas_reles'
                        fallas_reles_dao.insert_falla_rele(
                            id_rele=internal_rele_id,
                            numero_falla=latest_fault_record.fault_number,
                            timestamp=fault_timestamp_iso,
                            fasea_corr=latest_fault_record.current_phase_a,
                            faseb_corr=latest_fault_record.current_phase_b,
                            fasec_corr=latest_fault_record.current_phase_c,
                            tierra_corr=latest_fault_record.earth_current
                        )
                    else:
                        print(f"Relay Client: Falla (Nº {latest_fault_record.fault_number}, Timestamp: {fault_timestamp_iso}) para Rele interno ID {internal_rele_id} ya existe en la DB. No se reinserta.")
                else:
                    print(f"ADVERTENCIA: No se pudo encontrar el ID interno para el rele Modbus ID {relay_id}. No se registrara la falla en la BD.")

                return latest_fault_record.to_dict()
            else:
                print(f"Relay Client: No se pudo determinar la falla mas reciente para Rele (Unit ID {relay_id}) a pesar de haber leido registros. Posiblemente todos los fault_number fueron invalidos.")
                return None
        else:
            print(f"Relay Client: No se encontraron registros de falla validos para Rele (Unit ID {relay_id}) en el rango {hex(start_address)}-{hex(end_address)}.")
            return None
    
    def start_monitoring_loop(self):
        """
        Inicia un bucle continuo para monitorear el estado de todos los reles
        configurados en `self.relay_unit_ids`.
        La observacion de Modbus se controla a nivel de la lectura de registros.
        """
        print(f"Iniciando monitoreo de Reles de Proteccion (Host: {self.driver.host}:{self.driver.port}, Intervalo: {self.refresh_interval}s)...")
        
        while True:
            current_observing_status = self._is_observing_enabled()

            # Solo imprime el mensaje de estado si ha cambiado
            if current_observing_status != self._last_observing_status:
                if not current_observing_status:
                    print("Monitoreo de Reles MiCOM PAUSADO (observar.txt indica OFF).")
                else:
                    print("Monitoreo de Reles MiCOM REANUDADO (observar.txt indica ON).")
                self._last_observing_status = current_observing_status

            # Si la observacion esta deshabilitada, espera y continua al siguiente ciclo
            if not current_observing_status: 
                time.sleep(self.refresh_interval) # Anadimos el sleep aqui para evitar un bucle de CPU intenso
                continue 
            
            # Intenta conectar el driver Modbus si no esta conectado.
            # No se intenta reconectar si ya esta conectado.
            if not self.driver.is_connected():
                if not self.driver.connect():
                    print("Relay Client: No se pudo establecer conexion con el servidor Modbus. Reintentando en el proximo ciclo.") 
                    time.sleep(self.refresh_interval) # Anadimos el sleep aqui para evitar un bucle de CPU intenso
                    continue # Vuelve al inicio del bucle para reintentar la conexion

            # Si la lista de reles esta vacia (por ejemplo, despues del filtrado 'NO APLICA'),
            # el cliente espera sin intentar lecturas.
            if not self.relay_unit_ids:
                print("Relay Client: No hay reles activos para monitorear. Esperando...") 
                time.sleep(self.refresh_interval) # Anadimos el sleep aqui para evitar un bucle de CPU intenso
                continue # Vuelve al inicio del bucle para revisar mas tarde

            # Itera sobre cada rele activo y lee su estado
            # La funcion read_relay_status contendra la logica para detener las consultas Modbus
            # si el monitoreo esta deshabilitado.
            for relay_id in self.relay_unit_ids:
                print(f"Comienza iteracion sobre rele {relay_id}")
                self.read_relay_status(relay_id)
                # Aqui podrias anadir logica adicional basada en el estado leido,
                # como enviar alertas, actualizar una base de datos especifica de reles, etc.
            
            # Espera el intervalo definido antes de la siguiente ronda de monitoreo
            time.sleep(self.refresh_interval)