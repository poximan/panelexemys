# ---------------------------------------------------------
# --- middleware exemys -----------------------------------
# ---------------------------------------------------------
MB_HOST = '1.1.1.1'        # IP del servidor Modbus TCP al que te conectaras
MB_PORT = 5                # Puerto estandar Modbus TCP
MB_ID = 1                   # ID de la unidad Modbus (esclavo) a consultar
MB_COUNT = 16                # Numero de words consecutivos a leer
MB_INTERVAL_SECONDS = 60     # Intervalo de lectura Modbus en segundos

# Diccionario de equipos GRD, donde la clave es el ID del GRD y el valor es su descripcion
GRD_DESCRIPTIONS = {
    1: "descripcion del punto"
}

# ---------------------------------------------------------
# --- serie transparente ----------------------------------
# ---------------------------------------------------------
# Diccionario de equipos conectados via serie transparente
ESCLAVOS_MB = {
    1: "descripcion del punto"
}

# ---------------------------------------------------------
# --- Dashboard (dash_config) -----------------------------
# ---------------------------------------------------------
DASHBOARD_REFRESH_INTERVAL_MS = 10 * 1000   # actualizacion del dashboard en milisegundos
GLOBAL_THRESHOLD_ROJO = 40                  # Porcentaje debajo del cual conectividad "roja" (0-39)
GLOBAL_THRESHOLD_AMARILLO = 85              # Porcentaje debajo del cual conectividad "amarilla" (40-89)

# ---------------------------------------------------------
# --- Notificador de Alarmas ------------------------------
# ---------------------------------------------------------
ALARM_CHECK_INTERVAL_SECONDS = 20              # Intervalo para revisar condicion de alarma
ALARM_MIN_SUSTAINED_DURATION_MINUTES = 30      # Cuanto debe sostenerse una alarma para enviar email
ALARM_EMAIL_RECIPIENT = ["miemail@email.com"]
ALARM_EMAIL_SUBJECT_PREFIX = "[Exemys] "       # Prefijo para el asunto del email

# ---------------------------------------------------------
# --- Mensagelo (servicio HTTP de mensajeria) -------------
# ---------------------------------------------------------
# Parametros de conexion al microservicio mensagelo (reemplaza SMTP local)
MENSAGELO_BASE_URL = "http://ip:8081"
MENSAGELO_API_KEY = "miclave"
MENSAGELO_TIMEOUT_SECONDS = 5

# Politica de reintentos con backoff para el enqueue HTTP (send_async)
MENSAGELO_MAX_RETRIES = 5
MENSAGELO_BACKOFF_INITIAL = 0.5   # segundos
MENSAGELO_BACKOFF_MAX = 8.0       # segundos

# ---------------------------------------------------------
# --- MQTT ------------------------------------------------
# ---------------------------------------------------------
MQTT_BROKER_HOST = "hostremoto"
MQTT_BROKER_PORT = 8883
MQTT_BROKER_USERNAME = "miusuario"
MQTT_BROKER_PASSWORD = "micontra"

MQTT_BROKER_KEEPALIVE = 60          # heartbeat con el broker
MQTT_CONNECT_TIMEOUT = 15           # cuanto esperar la primera confirmacion de conexion

# Reconexion (paho maneja el backoff automaticamente con connect_async + loop_start)
MQTT_RECONNECT_DELAY_MIN = 5        # backoff minimo entre reintentos
MQTT_RECONNECT_DELAY_MAX = 60       # backoff maximo entre reintentos

# TLS (opcional)
MQTT_BROKER_USE_TLS = True
MQTT_BROKER_CA_CERT = None      # None o ruta string a certificado
MQTT_CLIENT_CERTFILE = None
MQTT_CLIENT_KEYFILE = None
MQTT_TLS_INSECURE = False

# Presencia del sistema (queda igual, no afecta al movil)
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

# -------- LOS 3 TOPICOS EXACTOS QUE USA EL MOVIL ----------
# (coinciden con tu MqttConfig en Android)
MQTT_TOPIC_MODEM_CONEXION = "topico/subtopico/conexion_modem"  # payload: {"estado":"conectado"|"desconectado","ts":"..."}
MQTT_TOPIC_GRADO           = "topico/subtopico/grado"          # payload: {"porcentaje": 58.3, "total": N, "conectados": M, "ts": "..."}
MQTT_TOPIC_GRDS            = "topico/subtopico/grds"           # payload: {"items":[{"id":11,"nombre":"...","ultima_caida":"..."}], "ts":"..."}

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
DATABASE_DIR = "data"
DATABASE_NAME = "basedatos.db"  # Nombre de la base de datos

# ---------------------------------------------------------
# --- Poblamiento de Datos (bd_poblar) --------------------
# ---------------------------------------------------------
POBLAR_BD = False                        # poblar con datos de test
HISTORICAL_DAYS_TO_GENERATE = 30         # dias a generar desde fecha actual
HISTORICAL_DATA_INTERVAL_SECONDS = 900   # Intervalo de generacion de datos (en segundos)