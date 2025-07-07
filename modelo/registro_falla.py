# modelo/registro_falla.py

from datetime import datetime

class RegistroFalla:
    """
    Representa un registro de falla decodificado de una lectura Modbus de un relÃ©,
    siguiendo el formato de fecha/hora IEC 870 detallado.
    """
    def __init__(self, raw_registers: list[int]):
        """
        Inicializa una instancia de RegistroFalla con los registros Modbus brutos.

        Args:
            raw_registers (list[int]): Una lista de 15 enteros (palabras Modbus)
                                       leÃ­dos directamente del relÃ©.
        Raises:
            ValueError: Si la lista de registros no tiene la longitud esperada (15).
        """
        if len(raw_registers) != 15:
            raise ValueError(f"Se esperaban 15 registros Modbus, pero se recibieron {len(raw_registers)}.")
        
        self._raw_registers = raw_registers
        self._parse_registers()

    def _parse_registers(self):
        """
        Decodifica los registros Modbus brutos en atributos significativos
        siguiendo el formato IEC 870 detallado en el CSV proporcionado.
        """
        self.fault_number: int = self._raw_registers[0]

        # Mapeo de los registros brutos a las palabras Modbus segÃºn la direcciÃ³n hex
        # Asumimos que raw_registers[1] es 0x0800, raw_registers[2] es 0x0801, etc.
        word_0800 = self._raw_registers[1] 
        word_0801 = self._raw_registers[2] 
        word_0802 = self._raw_registers[3] 
        word_0803 = self._raw_registers[4] 

        # --- Word 0800: AÃ±o (lÃ³gica compleja con byte alto y bajo) ---
        year_hi_byte = (word_0800 >> 8) & 0xFF # Byte alto de 0x0800
        year_lo_byte = word_0800 & 0xFF        # Byte bajo de 0x0800

        self.fault_year: int | None = None
        # Si el byte alto estÃ¡ en el rango de los aÃ±os 19xx
        if 94 <= year_hi_byte <= 99:
            self.fault_year = 1900 + year_hi_byte
        # Si el byte bajo (despuÃ©s de aplicar la mÃ¡scara 0x7F) estÃ¡ en el rango de los aÃ±os 20xx
        elif 0 <= (year_lo_byte & 0x7F) <= 93:
            self.fault_year = 2000 + (year_lo_byte & 0x7F)
        else:
            print(f"ADVERTENCIA: Formato de aÃ±o no reconocido en Word 0x0800 ({word_0800}). Byte Alto: {year_hi_byte}, Byte Bajo: {year_lo_byte}")
            self.fault_year = None # AÃ±o invÃ¡lido o no decodificable

        # --- Word 0801: Mes, DÃ­a de la Semana, DÃ­a del Mes ---
        # Byte alto de 0x0801 contiene el Mes (mÃ¡scara 0x0F)
        month_byte_hi = (word_0801 >> 8) & 0xFF
        self.fault_month: int = (month_byte_hi & 0x0F) 

        # Byte bajo de 0x0801 contiene DÃ­a de la Semana (mÃ¡scara 0xE0) y DÃ­a del Mes (mÃ¡scara 0x1F)
        day_byte_lo = word_0801 & 0xFF
        self.fault_day_of_week: int = ((day_byte_lo & 0xE0) >> 5) # Extrae bits 5-7 para DÃ­a de la Semana
        self.fault_day: int = (day_byte_lo & 0x1F)               # Extrae bits 0-4 para DÃ­a del Mes

        # --- Word 0802: Temporada, Hora, Validez de Fecha, Minuto ---
        # Byte alto de 0x0802 contiene Temporada (mÃ¡scara 0x80) y Hora (mÃ¡scara 0x1F)
        season_hour_byte_hi = (word_0802 >> 8) & 0xFF
        self.fault_season: int = ((season_hour_byte_hi & 0x80) >> 7) # Extrae bit 7 para Temporada
        self.fault_hour: int = (season_hour_byte_hi & 0x1F)           # Extrae bits 0-4 para Hora

        # Byte bajo de 0x0802 contiene Validez de Fecha (mÃ¡scara 0x80) y Minuto (mÃ¡scara 0x3F)
        validity_minute_byte_lo = word_0802 & 0xFF
        self.fault_date_validity: int = ((validity_minute_byte_lo & 0x80) >> 7) # Extrae bit 7 para Validez de Fecha
        self.fault_minute: int = (validity_minute_byte_lo & 0x3F)               # Extrae bits 0-5 para Minuto

        # --- Word 0803: Milisegundos (Ahora divididos en segundos y microsegundos) ---
        # El valor bruto de este registro representa los milisegundos totales desde el inicio del segundo
        # hasta un mÃ¡ximo de 59999 (lo que abarca hasta 59.999 segundos).
        self.fault_milliseconds_raw: int = word_0803 # Guarda el valor bruto si lo necesitas

        # Calcula los segundos enteros y los microsegundos restantes
        self.fault_seconds: int = self.fault_milliseconds_raw // 1000 # Segundos enteros (0-59)
        self.fault_microseconds: int = (self.fault_milliseconds_raw % 1000) * 1000 # Milisegundos restantes * 1000 para obtener microsegundos

        is_date_components_valid = True

        # Validaciones de rango segÃºn la documentaciÃ³n y los lÃ­mites de datetime
        if self.fault_year is None:
            is_date_components_valid = False 
        elif not (1994 <= self.fault_year <= 2093):
            print(f"ADVERTENCIA: AÃ±o final fuera de rango (1994-2093): {self.fault_year}")
            is_date_components_valid = False
        
        if not (1 <= self.fault_month <= 12):
            print(f"ADVERTENCIA: Mes fuera de rango (1-12): {self.fault_month}")
            is_date_components_valid = False
        if not (1 <= self.fault_day <= 31):
            print(f"ADVERTENCIA: DÃ­a del mes fuera de rango (1-31): {self.fault_day}")
            is_date_components_valid = False
        if not (1 <= self.fault_day_of_week <= 7):
            print(f"ADVERTENCIA: DÃ­a de la semana fuera de rango (1-7): {self.fault_day_of_week}")
            is_date_components_valid = False
        if not (0 <= self.fault_season <= 1):
            print(f"ADVERTENCIA: Temporada fuera de rango (0-1): {self.fault_season}")
            is_date_components_valid = False
        if not (0 <= self.fault_hour <= 23):
            print(f"ADVERTENCIA: Hora fuera de rango (0-23): {self.fault_hour}")
            is_date_components_valid = False
        if not (0 <= self.fault_minute <= 59):
            print(f"ADVERTENCIA: Minuto fuera de rango (0-59): {self.fault_minute}")
            is_date_components_valid = False
        if not (0 <= self.fault_date_validity <= 1):
            print(f"ADVERTENCIA: Validez de fecha fuera de rango (0-1): {self.fault_date_validity}")
            is_date_components_valid = False
            
        # Validaciones para los segundos y microsegundos derivados
        if not (0 <= self.fault_seconds <= 59):
            print(f"ADVERTENCIA: Segundos derivados fuera de rango (0-59): {self.fault_seconds}")
            is_date_components_valid = False
        if not (0 <= self.fault_microseconds <= 999999):
            print(f"ADVERTENCIA: Microsegundos derivados fuera de rango (0-999999): {self.fault_microseconds}")
            is_date_components_valid = False
        
        print("---------------------------\n")

        self.fault_datetime: datetime | None = None
        if not is_date_components_valid or self.fault_year is None:
             print("ERROR: Componentes de fecha/hora detectados como invÃ¡lidos. No se intentarÃ¡ crear objeto datetime.")
        else:
            try:
                # Nota: El objeto datetime de Python no usa directamente DÃ­a de la Semana, Temporada o Validez de Fecha.
                # Estos atributos se guardan por separado en el objeto RegistroFalla.
                self.fault_datetime = datetime(
                    self.fault_year,
                    self.fault_month,
                    self.fault_day,
                    self.fault_hour,
                    self.fault_minute,
                    self.fault_seconds,    # Pasamos los segundos calculados
                    self.fault_microseconds # Pasamos los microsegundos calculados
                )
            except ValueError as e: 
                print(f"Advertencia FINAL (ValueError al crear datetime): {e}")
                print(f"Valores que causaron el error: AÃ±o={self.fault_year}, Mes={self.fault_month}, DÃ­a={self.fault_day}, Hora={self.fault_hour}, Minuto={self.fault_minute}, Segundo={self.fault_seconds}, Microsegundo={self.fault_microseconds}")
                self.fault_datetime = None 

        # --- Resto de los campos del registro de falla (Ãndices a partir del 5) ---
        self.ignored_word_6: int = self._raw_registers[5] 
        self.active_group: int = self._raw_registers[6]
        self.involved_phases_type: int = self._raw_registers[7]
        self.fault_type: int = self._raw_registers[8]
        self.amplitude: int = self._raw_registers[9]
        self.current_phase_a: int = self._raw_registers[10]
        self.current_phase_b: int = self._raw_registers[11]
        self.current_phase_c: int = self._raw_registers[12]
        self.earth_current: int = self._raw_registers[13]
        self.recognized: bool = bool(self._raw_registers[14])

    def __repr__(self):
        """RepresentaciÃ³n para depuraciÃ³n."""
        return (f"RegistroFalla(Numero={self.fault_number}, Fecha={self.fault_datetime}, "
                f"Tipo={self.fault_type}, Fases={self.involved_phases_type}, "
                f"IA={self.current_phase_a}, IB={self.current_phase_b}, IC={self.current_phase_c}, "
                f"ITierra={self.earth_current}, Reconocida={self.recognized})")

    def to_dict(self) -> dict:
        """
        Exporta los datos de la falla a un diccionario.
        """
        return {
            "fault_number": self.fault_number,
            "fault_year": self.fault_year,
            "fault_month": self.fault_month,
            "fault_day": self.fault_day,
            "fault_hour": self.fault_hour,
            "fault_minute": self.fault_minute,
            "fault_seconds": self.fault_seconds,          # Nuevo campo
            "fault_microseconds": self.fault_microseconds, # Nuevo campo
            "fault_milliseconds_raw": self.fault_milliseconds_raw, # Valor bruto original
            "fault_datetime": self.fault_datetime.isoformat() if self.fault_datetime else None,
            "day_of_week": self.fault_day_of_week,  
            "season": self.fault_season,            
            "date_validity": self.fault_date_validity, 
            "ignored_word_6": self.ignored_word_6,
            "active_group": self.active_group,
            "involved_phases_type": self.involved_phases_type,
            "fault_type": self.fault_type,
            "amplitude": self.amplitude,
            "current_phase_a": self.current_phase_a,
            "current_phase_b": self.current_phase_b,
            "current_phase_c": self.current_phase_c,
            "earth_current": self.earth_current,
            "recognized": self.recognized
        }