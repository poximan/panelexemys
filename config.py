import os

# ---------------------------------------------------------
# --- middleware exemys -----------------------------------
# ---------------------------------------------------------
MB_HOST = 'localhost'       # IP del servidor Modbus TCP al que te conectarás
MB_PORT = 502               # Puerto estándar Modbus TCP
MB_ID = 22                  # ID de la unidad Modbus (esclavo) a consultar.
MB_COUNT = 16               # Número de words consecutivos a leer
MB_INTERVAL_SECONDS = 30   # Intervalo de lectura Modbus en segundos

# Diccionario de equipos GRD, donde la clave es el ID del GRD y el valor es su descripción.
GRD_DESCRIPTIONS = {
    1: "SS - presuriz doradillo",
    2: "SS - pluvial prefectura",
    3: "SS - presuriz agro",
    4: "SE - CD45 Murchison",
    5: "SS - bypass EE4",
    6: "SS - pluvial lugones",
    7: "reserva",
    8: "SE - et doradillo",
    9: "reserva",
    10: "SE - rec2(O) doradillo",
    11: "SE - rec3(N) doradillo",
    12: "reserva",
    13: "SE - et soc.rural",
    14: "SS - edif estivariz GE",
    15: "SE - et juan XXIII",
    16: "reserva",
    17: "SS - pque pesquero"
}

# ---------------------------------------------------------
# --- serie transparente ----------------------------------
# ---------------------------------------------------------
# Diccionario de equipos conectados via serie transparente
ESCLAVOS_MB = {
    1: "NO APLICA - (SE)et soc.rural - plc",
    2: "NO APLICA - (SE)et doradillo - proteccion ¿no esta?",
    3: "(SE)et doradillo - proteccion MiCOM CDA03 33KV",
    4: "NO APLICA - (SE)et doradillo - proteccion MiCOM rele cuba",
    5: "(SE)et doradillo - proteccion MiCOM CDA02 33KV",
    6: "(SE)et doradillo - proteccion MiCOM CDA03 13,2KV",
    7: "NO APLICA - (SS)presuriz doradillo - plc",
    8: "NO APLICA - (SE)et juan XXIII - proteccion janitza umg 96s",
    9: "NO APLICA - (SE)et juan XXIII - proteccion janitza umg 96s",
    10: "NO APLICA - (SE)et juan XXIII - proteccion janitza umg 96s",
    11: "NO APLICA - (SE)et juan XXIII - proteccion MiCOM p12x",
    12: "NO APLICA - (SE)et juan XXIII - proteccion MiCOM p12x",
    13: "NO APLICA - (SE)et juan XXIII - proteccion MiCOM p12x",
    14: "NO APLICA - (SE)et juan XXIII - proteccion MiCOM p12x"
}

# ---------------------------------------------------------
# --- Dashboard (dash_config) -----------------------------
# ---------------------------------------------------------
DASHBOARD_REFRESH_INTERVAL_MS = 10 * 1000   # actualización del dashboard en milisegundos
GLOBAL_THRESHOLD_ROJO = 60              # Porcentaje debajo del cual conectividad "roja" (0-39)
GLOBAL_THRESHOLD_AMARILLO = 85          # Porcentaje debajo del cual conectividad "amarilla" (40-89)

# ---------------------------------------------------------
# --- Notificador de Alarmas ------------------------------
# ---------------------------------------------------------
ALARM_CHECK_INTERVAL_SECONDS = 20           # Intervalo para revisarar condicion de alarma
ALARM_MIN_SUSTAINED_DURATION_MINUTES = 30   # cuanto debe sostenerse una alarma para enviar email

# ---------------------------------------------------------
# --- Servicio de Email (usando smtplib) ------------------
# ---------------------------------------------------------
ALARM_EMAIL_RECIPIENT = ["mi.usuario@proveedor.com"]
ALARM_EMAIL_SENDER = "mi.usuario@proveedor.com"    # Remitente del email (generalmente debe coincidir con SMTP_USERNAME)
ALARM_EMAIL_SUBJECT_PREFIX = "[Exemys] "        # Prefijo para el asunto del email

# Detalles del servidor SMTP
SMTP_SERVER = "proveedor.com" 
SMTP_PORT = 587             # Puerto estándar para TLS (587) o SSL (465). Si no estás seguro, prueba 587 primero.
SMTP_USERNAME = "mi.usuario@proveedor.com"
SMTP_PASSWORD = "mi.pass"
SMTP_USE_TLS = True             # Usa True si el puerto es 587 (STARTTLS), o False si es 465 (SSL)
SMTP_TIMEOUT_SECONDS = 30       # Tiempo máximo de espera para la conexión SMTP

# ---------------------------------------------------------
# --- MQTT ------------------------------------------------
# ---------------------------------------------------------
MQTT_BROKER_HOST = "mi.host"
MQTT_BROKER_PORT = 8883
MQTT_BROKER_USERNAME = "mi.usr"
MQTT_BROKER_PASSWORD = "mi.pass"
MQTT_USE_TLS = True                 # Usar TLS/SSL para la conexión
MQTT_TOPIC_ESTADOS = "estados/"

# ---------------------------------------------------------
# --- Base de Datos ---------------------------------------
# ---------------------------------------------------------
DATABASE_DIR = 'data'
DATABASE_NAME = 'grdconectados.db' # Nombre de la base de datos
os.makedirs(DATABASE_DIR, exist_ok=True) # Asegura que el directorio exista

# ---------------------------------------------------------
# --- Poblamiento de Datos (bd_poblar) --------------------
# ---------------------------------------------------------
POBLAR_BD = False                           # poblar con datos de test
HISTORICAL_DAYS_TO_GENERATE = 30            # días a generar desde fecha actual
HISTORICAL_DATA_INTERVAL_SECONDS = 900      # Intervalo de generacion de datos (en segundos)