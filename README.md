# Monitoreo y Dashboard de Conectividad GRD

Este solucion describe una aplicación de monitoreo de dispositivos GRD que recopila, almacena y visualiza datos de conectividad. La aplicación incluye un observador Modbus (modbus_obs.py) que lee el estado de los dispositivos y un notificador de alarmas (alarm_notifier.py) que envía correos electrónicos si la conectividad global o individual de un GRD cae por debajo de ciertos umbrales definidos en el archivo de configuración (config.py). Los datos se persisten en una base de datos SQLite gestionada por varios DAO (Data Access Object), como dao_historicos.py, dao_grd.py y dao_mensajes_enviados.py, los cuales interactúan con el esquema de la base de datos (ddl_esquema.py) y garantizan la seguridad en entornos multihilo (dao_base.py). Finalmente, una interfaz de usuario Dash (dash_config.py) muestra el estado de la conectividad y datos históricos, mientras que app.py orquesta la ejecución de estos componentes en hilos separados, y sim_poblar.py proporciona funciones para generar datos de prueba.

## Módulos Principales

El sistema está compuesto por varios módulos que trabajan de forma coordinada para cumplir sus funciones:

*   **`app.py`**: Es el **punto de entrada principal** de la aplicación, encargado de inicializar la base de datos, poblar datos (si está configurado) y lanzar los hilos de los observadores Modbus y de alarmas.
*   **`observador.modbus_obs.py`**: El **observador Modbus** que se conecta a un servidor Modbus TCP para leer el estado de conectividad de los GRD.
*   **`persistencia/` (DAO's y DDL)**: Un conjunto de módulos responsables de la **interacción con la base de datos SQLite**, incluyendo la creación del esquema y las operaciones de inserción y consulta.
*   **`notificador.alarm_notifier.py`**: El **notificador de alarmas** que evalúa las condiciones de conectividad global e individual para disparar y enviar alertas por email.
*   **`dash_config.py`**: Configura y define el **layout y la lógica de los callbacks** del dashboard web interactivo basado en Dash.
*   **`config.py`**: Contiene todas las **configuraciones y constantes** del proyecto, como credenciales de Modbus, umbrales de alarma, datos de email y descripciones de GRD.
*   **`email_sender.py`**: Un módulo auxiliar para el **envío de correos electrónicos** a través de SMTP.
*   **`persistencia.sim_poblar.py`**: Un módulo opcional para **generar datos históricos simulados** con fines de prueba y desarrollo.

---

## Detalles de los Módulos

### 1. Comunicación Modbus (Módulo `observador.modbus_obs.py`)

Este módulo es el **corazón de la recolección de datos** del sistema.

*   **Propósito**: Se encarga de **leer periódicamente los registros de los equipos GRD** a través del protocolo Modbus TCP y determinar su estado de conectividad.
*   **Configuración**: Utiliza parámetros definidos en `config.py` como la **IP del servidor (`MB_HOST`), el puerto (`MB_PORT`), el ID de la unidad (`MB_ID`), el número de registros a leer (`MB_COUNT`) y el intervalo de lectura (`MB_INTERVAL_SECONDS`)**. La lista de **IDs de GRD a monitorear se obtiene de `config.GRD_DESCRIPTIONS`**.
*   **Funcionamiento**:
    *   Se ejecuta en un **hilo separado** iniciado desde `app.py` para no bloquear el proceso principal.
    *   Establece una **conexión Modbus TCP** con el servidor especificado.
    *   Para cada `grd_id` configurado, calcula la dirección de inicio Modbus y **lee 16 registros de entrada**.
    *   El **estado de "conectado" (0 o 1) se extrae del bit 0 del registro 16** (índice 15).
    *   Antes de insertar un nuevo registro, consulta la base de datos para obtener el **último estado conocido** de ese GRD.
    *   **Solo se inserta un nuevo registro en la base de datos si el estado actual difiere del último estado almacenado**, evitando así la escritura de datos redundantes.
    *   Entre cada ciclo de lectura, el observador espera el tiempo definido por `MB_INTERVAL_SECONDS`.
    *   Los mensajes de estado y error se muestran en la consola mediante `print()`.

### 2. Manejo de Inserciones en Base de Datos (Módulos `persistencia/`)

La gestión de la persistencia de datos es manejada por el paquete `persistencia`, que incluye la definición del esquema y las operaciones de acceso a datos (DAO's).

*   **Creación del Esquema (`ddl_esquema.py`)**:
    *   Se encarga de **asegurar la existencia del directorio `data/`** para la base de datos.
    *   **Crea las tablas `grd` e `historicos`** en la base de datos SQLite si no existen.
    *   La tabla `grd` almacena el `id` y la `descripcion` de cada equipo.
    *   La tabla `historicos` guarda las lecturas de conectividad (`timestamp`, `id_grd`, `conectado`) y tiene una **clave foránea a `grd(id)`** para asegurar la integridad referencial.
    *   Habilita explícitamente el soporte de claves foráneas en cada conexión.
    *   Este proceso se ejecuta al inicio de la aplicación a través de `app.py`.
*   **Capa de Acceso a Datos (DAO's)**:
    *   **`dao_base.py`**: Proporciona funciones fundamentales para la conexión a la base de datos SQLite (`get_db_connection()`) y utiliza un **bloqueo (`threading.RLock`) (`db_lock`) para garantizar la seguridad en entornos multihilo**. Configura las conexiones para acceder a las columnas por nombre.
    *   **`dao_grd.py`**: Gestiona la información de los equipos GRD.
        *   `insert_grd_description(self, grd_id: int, description: str)`: Inserta o ignora la inserción de descripciones de GRD, lo que permite que `app.py` pueble la tabla `grd` al inicio sin generar duplicados.
        *   `grd_exists(self, grd_id: int) -> bool`: Verifica la existencia de un GRD, utilizado por `HistoricosDAO` antes de insertar lecturas.
    *   **`dao_historicos.py`**: Maneja las operaciones sobre los datos históricos de conectividad.
        *   `insert_historico_reading(self, grd_id: int, timestamp: str, conectado_value: int)`: Utilizado por el observador Modbus para persistir los estados de conectividad.
        *   Incluye métodos para **recuperar el último estado** de un GRD (`get_latest_connected_state_for_grd`), el **último estado de todos los GRD (excluyendo los de 'reserva')** (`get_latest_states_for_all_grds`), y una lista de **GRDs actualmente desconectados (excluyendo 'reserva')** (`get_all_disconnected_grds`).
        *   También proporciona funciones para obtener **datos históricos por semana, mes o todos los datos** para la visualización en el dashboard, incluyendo cálculos para la paginación (`get_weekly_data_for_grd`, `get_monthly_data_for_grd`, `get_all_data_for_grd`, `get_total_weeks_for_grd`, `get_total_months_for_grd`).
    *   **`dao_mensajes_enviados.py`**: Se encarga de **registrar los intentos de envío de correos electrónicos** en la tabla `mensajes_enviados`, incluyendo el asunto, cuerpo, destinatario y si el envío fue exitoso. Es utilizado por el notificador de alarmas.
*   **Poblamiento de Datos de Prueba (`sim_poblar.py`)**:
    *   Si `config.POBLAR_BD` es `True`, este módulo puede **generar grandes volúmenes de datos históricos ficticios** para los GRD configurados. Estos datos se distribuyen a lo largo de un número configurable de días e intervalos, y se insertan utilizando `INSERT OR IGNORE`.

### 3. Consulta a Base de Datos para Notificar Alarmas (Módulo `notificador.alarm_notifier.py`)

Este módulo monitorea constantemente el estado de la conectividad y dispara alarmas según umbrales predefinidos.

*   **Propósito**: **Detectar condiciones de alarma** relacionadas con la conectividad de los GRD, ya sea a nivel global del sistema o para GRD individuales, y **enviar notificaciones por correo electrónico**.
*   **Configuración**: Depende de `config.py` para el **intervalo de chequeo (`ALARM_CHECK_INTERVAL_SECONDS`)**, la **duración mínima que una condición debe sostenerse (`ALARM_MIN_SUSTAINED_DURATION_MINUTES`)** y el **umbral de conectividad global (`GLOBAL_THRESHOLD_ROJO`)**. También utiliza `config.ALARM_EMAIL_RECIPIENT` para el destinatario de las alarmas.
*   **Funcionamiento**:
    *   Opera en un **hilo separado** iniciado por `app.py`.
    *   En cada ciclo, obtiene el **último estado de conectividad para todos los GRD** y la lista de **GRDs actualmente desconectados** de `historicos_dao`.
    *   **Alarma de Conectividad Global (`_check_global_connectivity_alarm`)**:
        *   Calcula el porcentaje de conectividad global.
        *   Si el porcentaje **cae por debajo de `GLOBAL_THRESHOLD_ROJO` (ej. 70%)** y se mantiene por el `ALARM_MIN_SUSTAINED_DURATION_MINUTES`, se considera una alarma.
        *   Envía un **email con el asunto "Middleware sin conexión"**.
        *   Registra el intento de envío del email en la tabla `mensajes_enviados` a través de `mensajes_enviados_dao`.
        *   La alarma se "resuelve" y se reinicia cuando la conectividad global supera el umbral.
    *   **Alarma de GRD Individual (`_check_individual_grd_alarms`)**:
        *   Se activa si un GRD específico está desconectado y la **conectividad global se mantiene por encima del `GLOBAL_THRESHOLD_ROJO`** (indicando que no es un problema general del sistema).
        *   Si esta condición persiste por el tiempo mínimo configurado, se envía un **email con el nombre del GRD y el asunto "sin conexión"**.
        *   También persiste el registro de envío del email.
        *   La alarma individual se "resuelve" si el GRD se reconecta o si la conectividad global cae por debajo del umbral rojo.
    *   Mantiene el estado de las alarmas (inicio, si ya se disparó) en diccionarios en memoria (`global_connectivity_alarm_state`, `individual_grd_alarm_states`).
    *   Cabe destacar que, aunque `historicos_dao` ya excluye los GRD con descripción `'reserva'` en sus consultas, el módulo `alarm_notifier` incluye una **línea de filtrado adicional para `'reserva'`**, lo que podría ser redundante.
    *   Los mensajes de estado y error se muestran en la consola mediante `print()`.

### 4. Construcción de un Dashboard (Módulo `dash_config.py`)

Este módulo configura la interfaz de usuario interactiva para visualizar el estado de la conectividad de los GRD.

*   **Propósito**: Proporcionar una **representación visual clara y dinámica** del estado actual y los datos históricos de conectividad de los equipos GRD.
*   **Framework**: Construido sobre **Dash (Plotly)**, permitiendo la creación de aplicaciones web analíticas.
*   **Layout (`configure_dash_app`)**:
    *   Define la estructura visual de la aplicación, incluyendo una **cabecera principal** y paneles de indicadores.
    *   **Panel de KPI (Key Performance Indicators)**:
        *   **Indicador de Aguja (`connection-gauge`)**: Muestra el **porcentaje actual de conectividad global** de los GRD, con rangos de colores que indican el nivel de salud (verde, amarillo, rojo). Los umbrales (ej. `GLOBAL_THRESHOLD_ROJO`, `GLOBAL_THRESHOLD_AMARILLO`) se obtienen de `config.py`.
        *   **Semáforo de Estado (`traffic-light-green`, `yellow`, `red`)**: Un semáforo visual que refleja rápidamente la salud general de la conexión global.
        *   **Tabla de Equipos Desconectados (`disconnected-grds-table`)**: Lista los GRD que actualmente están desconectados, junto con la estampa de tiempo de su última caída conocida. Los datos se obtienen del `historicos_dao`.
    *   **Controles de Visualización**:
        *   **Menú Desplegable de GRD (`grd-id-dropdown`)**: Permite al usuario **seleccionar un GRD específico** para visualizar sus datos históricos detallados. Las opciones se generan a partir de `config.GRD_DESCRIPTIONS`.
        *   **Botones de Ventana de Tiempo (`1sem-btn`, `1mes-btn`, `todo-btn`)**: Permiten cambiar la **granularidad de los datos mostrados** en el gráfico principal a una semana, un mes o todo el historial disponible.
    *   **Controles de Paginación (`pagination-controls`)**: Botones "Anterior" y "Siguiente" para **navegar a través de semanas o meses previos** de datos históricos cuando se selecciona una ventana de tiempo específica (Semana o Mes). Estos se deshabilitan u ocultan según la ventana y la disponibilidad de datos.
    *   **Gráfico Principal de Onda de Conexión (`connected-wave-graph`)**: Muestra el **historial de estados conectado/desconectado** para el GRD seleccionado en el tiempo. Utiliza formas rectangulares para representar los periodos de conexión (verde) y desconexión (rojo).
    *   **Tabla de Detalles de GRD (`grd-data-table`)**: Muestra la **información del último registro** para el GRD seleccionado, incluyendo su ID, estado de conexión y la última actualización.
    *   **Actualización Automática (`dcc.Interval`)**: Un componente que dispara **actualizaciones periódicas del dashboard** (definido por `config.DASHBOARD_REFRESH_INTERVAL_MS`) para mantener los datos en tiempo real.
*   **Interactividad (Callbacks)**:
    *   Los callbacks de Dash (`@app.callback`) **vinculan los inputs del usuario (clics en botones, selección de dropdown)** y los intervalos de tiempo a las actualizaciones de los outputs (gráficos, tablas, estilos).
    *   Se utilizan `dcc.Store` (`time-window-state`) para **mantener el estado de la ventana de tiempo y la paginación** a través de las interacciones.
    *   Las consultas a la base de datos para obtener los datos del dashboard se realizan a través de `historicos_dao`.
    *   La **lógica para generar el gráfico** de onda de conexión, incluyendo el manejo de zoom y los colores de los segmentos, reside en el callback `update_dashboard`.
*   **Estilo**: El dashboard utiliza clases CSS definidas en `assets/styles.css` para una apariencia consistente y responsiva.