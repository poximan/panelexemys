# ---------------------------------------------------------
# --- middleware exemys -----------------------------------
# ---------------------------------------------------------
MB_HOST = '1.1.1.1'       # IP del servidor Modbus TCP al que te conectarás
MB_PORT = 202               # Puerto estándar Modbus TCP
MB_ID = 22                  # ID de la unidad Modbus (esclavo) a consultar.
MB_COUNT = 16               # Número de words consecutivos a leer
MB_INTERVAL_SECONDS = 60   # Intervalo de lectura Modbus en segundos

# Diccionario de equipos GRD, donde la clave es el ID del GRD y el valor es su descripción.
GRD_DESCRIPTIONS = {    
    1: "reserva"
}

# ---------------------------------------------------------
# --- serie transparente ----------------------------------
# ---------------------------------------------------------
# Diccionario de equipos conectados via serie transparente
ESCLAVOS_MB = {
    1: "NO APLICA - este punto no usa puerto transparente"
}

# ---------------------------------------------------------
# --- Dashboard (dash_config) -----------------------------
# ---------------------------------------------------------
DASHBOARD_REFRESH_INTERVAL_MS = 10 * 1000   # actualización del dashboard en milisegundos
GLOBAL_THRESHOLD_ROJO = 40              # Porcentaje debajo del cual conectividad "roja" (0-39)
GLOBAL_THRESHOLD_AMARILLO = 85          # Porcentaje debajo del cual conectividad "amarilla" (40-89)

# ---------------------------------------------------------
# --- Notificador de Alarmas ------------------------------
# ---------------------------------------------------------
ALARM_CHECK_INTERVAL_SECONDS = 20           # Intervalo para revisarar condicion de alarma
ALARM_MIN_SUSTAINED_DURATION_MINUTES = 30   # cuanto debe sostenerse una alarma para enviar email

# ---------------------------------------------------------
# --- Servicio de Email (usando smtplib) ------------------
# ---------------------------------------------------------
ALARM_EMAIL_RECIPIENT = ["midestino1@destino.com", "midestino2@destino.com"]
ALARM_EMAIL_SENDER = "miorigen@origen.com"    # Remitente del email (generalmente debe coincidir con SMTP_USERNAME)
ALARM_EMAIL_SUBJECT_PREFIX = "[Exemys] "        # Prefijo para el asunto del email

# Detalles del servidor SMTP
SMTP_SERVER = "tostadora" 
SMTP_PORT = 587             # Puerto estándar para TLS (587) o SSL (465). Si no estás seguro, prueba 587 primero.
SMTP_USERNAME = "miusuario"
SMTP_PASSWORD = "micontrasenia"
SMTP_USE_TLS = True             # Usa True si el puerto es 587 (STARTTLS), o False si es 465 (SSL)
SMTP_TIMEOUT_SECONDS = 30       # Tiempo máximo de espera para la conexión SMTP

# ---------------------------------------------------------
# --- MQTT ------------------------------------------------
# ---------------------------------------------------------
MQTT_BROKER_HOST = "mibrokermqtt"
MQTT_BROKER_PORT = 8
MQTT_BROKER_USERNAME = "usr"
MQTT_BROKER_PASSWORD = "contr"

MQTT_BROKER_KEEPALIVE = 60          # <— heartbeat con el broker
MQTT_CONNECT_TIMEOUT = 15           # <— cuánto esperar la 1ª confirmación de conexión

# Reconexión (paho maneja el backoff automáticamente con connect_async + loop_start)
MQTT_RECONNECT_DELAY_MIN = 5        # <— backoff mínimo entre reintentos
MQTT_RECONNECT_DELAY_MAX = 60       # <— backoff máximo entre reintentos

# TLS (opcional)
MQTT_BROKER_USE_TLS = True
MQTT_BROKER_CA_CERT = None      # None o ruta string a certificado
MQTT_CLIENT_CERTFILE = None
MQTT_CLIENT_KEYFILE = None
MQTT_TLS_INSECURE = False

# Presencia del sistema (queda igual, no afecta al móvil)
MQTT_WILL_TOPIC = "topico1/sistema"
MQTT_WILL_PAYLOAD = "offline"
MQTT_WILL_QOS = 1
MQTT_WILL_RETAIN = True

MQTT_ONLINE_TOPIC = "topico2/sistema"
MQTT_ONLINE_PAYLOAD = "online"
MQTT_ONLINE_QOS = 1
MQTT_ONLINE_RETAIN = True

MQTT_OFFLINE_TOPIC = "topico3/sistema"
MQTT_OFFLINE_PAYLOAD = "offline"
MQTT_OFFLINE_QOS = 1
MQTT_OFFLINE_RETAIN = True

# -------- LOS 3 TÓPICOS EXACTOS QUE USA EL MÓVIL ----------
# (coinciden con tu MqttConfig en Android)
MQTT_TOPIC_MODEM_CONEXION = "topico4/estado/conexion_modem"  # payload: "conectado" | "desconectado"
MQTT_TOPIC_GRADO           = "topico5/estado/grado"          # payload: {"porcentaje": 58.3}
MQTT_TOPIC_GRDS            = "topico6/estado/grds"           # payload: {"items":[{"id":11,"nombre":"...", "ultima_caida":"2025-08-19T12:19:01Z"}]}

# QoS/retain por defecto
MQTT_PUBLISH_QOS_STATE = 1
MQTT_PUBLISH_RETAIN_STATE = True

# ---------------- RPC sobre MQTT (request/response) ----------------------
# El cliente publica requests en este arbol. El servidor responde SIEMPRE
# usando alguno de los 3 topicos ya suscritos por el movil (reply_to).
MQTT_RPC_REQ_ROOT = "app/req"        # nos suscribimos a "app/req/#"
# Acciones soportadas (para validacion/evolucion)
MQTT_RPC_ALLOWED_ACTIONS = {
    "get_global_status",   # responde en estado/exemys con resumen + ultimos estados por GRD
    "get_modem_status",    # responde en estado/sensor con estado del modem
    # futuro: "get_last_faults", etc., sin agregar nuevos topicos de suscripcion
}

# TOPICOS VALIDOS PARA reply_to (solo los 3)
MQTT_RPC_ALLOWED_REPLY_TO = {
    MQTT_TOPIC_MODEM_CONEXION,
    MQTT_TOPIC_GRADO,
    MQTT_TOPIC_GRDS,
}

# ---------------------------------------------------------
# --- Base de Datos ---------------------------------------
# ---------------------------------------------------------
DATABASE_DIR = 'data'
DATABASE_NAME = 'grdconectados.db' # Nombre de la base de datos

# ---------------------------------------------------------
# --- Poblamiento de Datos (bd_poblar) --------------------
# ---------------------------------------------------------
POBLAR_BD = False                           # poblar con datos de test
HISTORICAL_DAYS_TO_GENERATE = 30            # días a generar desde fecha actual
HISTORICAL_DATA_INTERVAL_SECONDS = 900      # Intervalo de generacion de datos (en segundos)