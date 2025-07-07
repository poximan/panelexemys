from pymodbus.client import ModbusTcpClient

class ModbusTcpDriver:
    """
    Driver genérico para la conexión y comunicación con un servidor Modbus TCP.
    Encapsula la lógica de conexión, reintento y manejo de errores básicos.
    """
    def __init__(self, host: str, port: int, connect_timeout: int = 5):
        """
        Inicializa el driver Modbus TCP.

        Args:
            host (str): Dirección IP o nombre de host del servidor Modbus TCP.
            port (int): Puerto del servidor Modbus TCP (por defecto 502).
            connect_timeout (int): Tiempo de espera en segundos para intentar la conexión.
        """
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self._client = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        Intenta establecer una conexión con el servidor Modbus TCP.
        """
        if self._is_connected and self._client:
            return True # Ya conectado

        if self._client:
            self._client.close() # Cierra cualquier conexión anterior por si acaso

        try:
            self._client = ModbusTcpClient(self.host, port=self.port, timeout=self.connect_timeout)
            if self._client.connect():
                self._is_connected = True
                # print(f"Modbus Driver: Conectado a {self.host}:{self.port}")
                return True
            else:
                self._is_connected = False
                print(f"Modbus Driver: No se pudo conectar a {self.host}:{self.port}")
                return False
        except Exception as e:
            self._is_connected = False
            print(f"Modbus Driver: Error al intentar conectar a {self.host}:{self.port}: {e}")
            return False

    def disconnect(self):
        """
        Cierra la conexión Modbus TCP.
        """
        if self._client and self._is_connected:
            self._client.close()
            self._is_connected = False
            # print(f"Modbus Driver: Desconectado de {self.host}:{self.port}")

    def read_input_registers(self, address_offset: int, count: int, unit_id: int):
        """
        Lee una serie de registros de entrada (Input Registers) del esclavo Modbus.

        Args:
            address_offset (int): La dirección de inicio del registro (offset 0 para 30001).
            count (int): La cantidad de registros a leer.
            unit_id (int): El Unit ID (Slave ID) del esclavo al que consultar.

        Returns:
            list[int]: Lista de valores de los registros si la lectura fue exitosa, o None en caso de error.
        """
        if not self._is_connected and not self.connect():
            return None # No se pudo conectar

        try:
            result = self._client.read_input_registers(address_offset, count=count, slave=unit_id)

            if result is None:
                print(f"Modbus Driver: Error de comunicación o respuesta inválida del servidor para Unit ID {unit_id}, Addr {address_offset}, Cant {count}.")
                return None
            
            if hasattr(result, 'isError') and result.isError():
                print(f"Modbus Driver: El esclavo (Unit ID {unit_id}) reportó un error de protocolo: {result} al leer {address_offset}.")
                return None
            
            elif result.registers:
                return result.registers
            else:
                print(f"Modbus Driver: Se recibió una respuesta válida, pero sin registros para Unit ID {unit_id}, Addr {address_offset}, Cant {count}.")
                return None
        except Exception as e:
            print(f"Modbus Driver: Excepción en lectura para Unit ID {unit_id}, Addr {address_offset}, Cant {count}: {e}.")
            self.disconnect() # Posiblemente la conexión se perdió
            return None

    def read_holding_registers(self, address_offset: int, count: int, unit_id: int):
        """
        Lee una serie de registros de retención (Holding Registers) del esclavo Modbus.
        (Añadido para completar el driver genérico, no necesariamente usado por tus clientes actuales)
        """
        if not self._is_connected and not self.connect():
            return None

        try:
            result = self._client.read_holding_registers(address_offset, count=count, slave=unit_id)
            if result is None or (hasattr(result, 'isError') and result.isError()):
                print(f"Modbus Driver: Error al leer holding registers para Unit ID {unit_id}, Addr {address_offset}: {result}")
                return None
            return result.registers
        except Exception as e:
            print(f"Modbus Driver: Excepción en lectura de holding registers para Unit ID {unit_id}, Addr {address_offset}: {e}")
            self.disconnect()
            return None

    def write_single_register(self, address_offset: int, value: int, unit_id: int):
        """
        Escribe un único registro de retención (Holding Register) en el esclavo Modbus.
        (Añadido para completar el driver genérico)
        """
        if not self._is_connected and not self.connect():
            return False

        try:
            result = self._client.write_register(address_offset, value, slave=unit_id)
            if result is None or (hasattr(result, 'isError') and result.isError()):
                print(f"Modbus Driver: Error al escribir registro para Unit ID {unit_id}, Addr {address_offset}, Value {value}: {result}")
                return False
            # print(f"Modbus Driver: Escrito {value} en Unit ID {unit_id}, Addr {address_offset}")
            return True
        except Exception as e:
            print(f"Modbus Driver: Excepción al escribir registro para Unit ID {unit_id}, Addr {address_offset}, Value {value}: {e}")
            self.disconnect()
            return False

    def is_connected(self) -> bool:
        """
        Retorna el estado actual de la conexión.
        """
        return self._is_connected