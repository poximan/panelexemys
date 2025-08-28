import re
import pandas
from src.logger import Logosaurio

class logs():
    def __init__(self, logger: Logosaurio):
        # Almacena la instancia del logger para usarla en los métodos
        self.logger = logger

    def logs_console_print(self, func: str, reason: str, desc: str) -> None:
        # Usa el logger para registrar el mensaje
        self.logger.log(f"{func} ~ ( {reason} ): {desc}.", origen="TCP/API")

    def logs_logo_print(self, logo: str, version: str) -> None:
        # Aquí puedes decidir si quieres que el logo se registre o solo se imprima
        # Una opción es imprimirlo directamente
        print(re.sub("<version>", version, logo))
        self.logger.log(f"Imprimiendo logo de la version {version}", origen="TCP/API")

    def logs_result_print(self, result: str | pandas.DataFrame) -> None:
        # En lugar de solo imprimir, puedes registrar el resultado
        self.logger.log(f"Resultado de la operación:\n{result}", origen="TCP/API")

    def logs_load_process_print(self) -> None:
        # Para mensajes de carga, también usamos el logger
        self.logger.log("Proceso de carga en curso...", origen="TCP/API")