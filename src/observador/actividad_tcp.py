import socket
import time
import os
import json

def test_tcp_connection(host: str, port: int, timeout: int = 5):
    """
    Monitorea continuamente la actividad de una conexión TCP en un bucle infinito.
    Escribe el estado de la conexión en el archivo observar.json cada minuto.

    Args:
        host (str): La dirección IP o nombre de host a la que se desea conectar.
        port (int): El número de puerto TCP a probar.
        timeout (int): El tiempo de espera en segundos para la conexión.
    """
    # Construir la ruta absoluta al archivo observar.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    observar_file_path = os.path.join(script_dir, 'observar.json')
    
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        
        status = "desconectado"
        
        try:
            print(f"Comprobando la conectividad de {host}:{port}...")
            s.connect((host, port))
            print(f"Éxito: Conexión establecida a {host}:{port}.")
            status = "conectado"
        except socket.timeout:
            print(f"Error: Tiempo de espera agotado al intentar conectar a {host}:{port}.")
        except ConnectionRefusedError:
            print(f"Error: Conexión rechazada por {host}:{port}. El puerto podría estar cerrado o el servicio inactivo.")
        except Exception as e:
            print(f"Error inesperado al conectar a {host}:{port}: {e}")
        finally:
            s.close()

        # Escribir el resultado del test en el archivo JSON
        try:
            # Leer el contenido actual del archivo
            if os.path.exists(observar_file_path):
                with open(observar_file_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                    else:
                        data = {}
            else:
                data = {}

            # Actualizar la clave con el nuevo estado
            data['ip200_estado'] = status
            
            # Escribir el objeto JSON completo de vuelta al archivo
            with open(observar_file_path, 'w') as f:
                json.dump(data, f, indent=4) 
                
            print(f"Estado de la conexión '{status}' guardado en observar.json.")
        
        except (IOError, json.JSONDecodeError) as e:
            print(f"ERROR al guardar el estado en {observar_file_path}: {e}")
            
        # Esperar 60 segundos antes de la siguiente comprobación
        time.sleep(60)