# Resumen del Proyecto: Sistema de Monitoreo Exemys

Esta es una plataforma de software diseñada para supervisar el estado de equipos remotos, visualizar datos históricos y enviar alertas automáticas.  
Su objetivo principal es facilitar las tareas de gestión y mantenimiento a los operadores, centralizando la información y notificando proactivamente sobre cualquier anomalía detectada en la red de dispositivos.

---

## 1. ¿Para Qué Sirve Este Sistema?

El objetivo principal del sistema es proporcionar una visión completa y actualizada del estado de una red de equipos industriales remotos. Para ello, cumple tres funciones esenciales:

- **Monitoreo Centralizado**: El sistema consulta constantemente el estado de equipos remotos (llamados GRDs) para verificar si están en línea y funcionando correctamente, consolidando toda la información en un único punto.
- **Alertas Proactivas**: Detecta automáticamente problemas, como caídas de conexión en uno o varios equipos, y envía notificaciones por correo electrónico. Esto permite que el personal técnico pueda actuar rápidamente para solucionar el incidente.
- **Visualización y Análisis**: Toda la información recolectada se presenta en un panel de control web (Dashboard) que es fácil de usar. Este panel permite a los usuarios ver el estado actual de la red, la lista de equipos con problemas y analizar datos históricos de conectividad a través de gráficos interactivos.

Para lograr estos objetivos, el sistema está organizado en varios componentes especializados que trabajan en conjunto.

---

## 2. Los Componentes Principales

El sistema posee una arquitectura modular, donde cada componente tiene una responsabilidad clara y definida. Esto facilita su mantenimiento y escalabilidad.

### 2.1. El Núcleo de Monitoreo (Los *Observadores*)

El corazón del sistema son procesos automáticos (llamados *observadores* o hilos) que se ejecutan en segundo plano para recolectar datos de diferentes fuentes sin interrumpir la interfaz de usuario.  

Las tareas de monitoreo más importantes se resumen en la siguiente tabla:

| Tarea de Monitoreo     | Dispositivo Supervisado                       | Protocolo/Método                         | Frecuencia de Chequeo                                   | Propósito Principal                                             |
|-------------------------|-----------------------------------------------|------------------------------------------|---------------------------------------------------------|----------------------------------------------------------------|
| Conectividad de GRD     | Equipos GRD (ej. *SS - presuriz doradillo*)  | Modbus TCP                               | Cada 60 segundos (`MB_INTERVAL_SECONDS`)                | Verificar si los equipos están en línea o desconectados.        |
| Fallas de Relés         | Relés de protección MiCOM                     | Modbus TCP                               | Cada 60 segundos (`MB_INTERVAL_SECONDS`)                | Leer y registrar datos detallados sobre fallas eléctricas.      |
| Estado del M�dem        | Conexi�n de red (200.63.163.36:40000)         | Servicio `router-telef-service` (sondeo TCP local) | Cada 10 segundos | Confirmar que la conexi�n principal a internet est� operativa.  |

---

### 2.2. La Base de Datos (La *Memoria* del Sistema)

El sistema utiliza una base de datos **SQLite (`grdconectados.db`)** como el almacén central de toda la información que recolecta y genera.  

Este componente guarda:

1. **Historial de Conectividad**: Cambios de estado conectados/desconectados en la tabla `historicos`.  
2. **Registro de Fallas**: Detalles de fallas de relés MiCOM en la tabla `fallas_reles`, incluyendo corrientes por fase (`current_phase_a`, `current_phase_b`, etc.).  
3. **Configuración de Equipos**: Información de GRDs y relés en las tablas `grd` y `reles`.  
4. **Auditoría de Notificaciones**: Historial de alarmas enviadas por email en `mensajes_enviados`, con éxito o fallo.

---

### 2.3. El Sistema de Alarmas y Notificaciones

Un componente dedicado (**NotifManager**) revisa continuamente la base de datos para detectar condiciones anómalas que requieran atención.  

Genera tres tipos de alarmas:

- **Alarma Global**: si el % total de equipos conectados < 40% (`GLOBAL_THRESHOLD_ROJO`).  
- **Alarma Individual**: si un equipo específico se desconecta, aunque el resto de la red esté sana.  
- **Alarma de Módem**: si la conexión principal de internet está caída.  

Para evitar falsas alarmas:
- Una condición debe mantenerse al menos **30 minutos** (`ALARM_MIN_SUSTAINED_DURATION_MINUTES`).  
- El NotifManager chequea cada **20 segundos** (`ALARM_CHECK_INTERVAL_SECONDS`).  
- Una vez confirmada la alarma, envía correo a `ALARM_EMAIL_RECIPIENT` usando **Mensagelo**.

---

### 2.4. La Interfaz de Usuario (Dashboard Web)

Construida con **Dash**, es una SPA (*Single Page Application*) que permite interacción en tiempo real.  

Secciones principales:

- **Dashboard Principal**: KPIs globales, lista de equipos desconectados, gráficos históricos.  
- **Panel de Relés MiCOM**: Últimos registros de fallas de relés de protección con datos técnicos.  
- **Panel de Mantenimiento**: Herramientas para verificar estado del correo (smtp, `ping_local`, `ping_remoto`) y enviar correos de prueba vía Mensagelo.

---

### 2.5. Comunicación con la App Móvil (MQTT)

El sistema también interactúa con clientes externos (ej: app móvil) mediante **MQTT**.

- **Publicación de datos**:
  - `exemys/estado/conexion_modem`: estado del puerto TCP remoto (`abierto`, `cerrado` o `desconocido`).  
  - `exemys/estado/grado`: % global de conectividad.  
  - `exemys/estado/grds`: lista de equipos desconectados.  

- **RPC (Petición/Respuesta)**:
  - Se suscribe a `app/req/#` (`MQTT_RPC_REQ_ROOT`).  
  - Ejemplo: la app pide `get_global_status`, el sistema responde con datos actualizados.

---

## 3. ¿Cómo Fluye la Información? El Ciclo de Operación

1. **Recolección**: observador Modbus pide datos a un GRD cada 60s.  
2. **Detección de Cambio**: compara nuevo estado con el último en DB.  
3. **Persistencia**: si cambió, inserta registro en `historicos`.  
4. **Visualización**: el Dashboard actualiza KPIs y gráficos.  
5. **Publicación**: se publica en tópicos MQTT para la app móvil.  
6. **Verificación de Alarma**: NotifManager chequea cada 20s.  
7. **Notificación**: al cumplirse condiciones, se encola un correo vía Mensagelo → registro en `mensajes_enviados`.

---

## 4. Tecnologías Clave Utilizadas

- **Dash, Plotly, Pandas** → UI web interactiva, gráficos y análisis de datos.  
- **Pymodbus** → comunicación industrial con GRDs/relés vía Modbus TCP.  
- **Paho-MQTT** → mensajería en tiempo real y RPC con app móvil.  
- **SQLite** → motor de base de datos ligero y confiable.  
- **Requests** → llamadas HTTP a APIs externas (Mensagelo, router-telef-service).

---


