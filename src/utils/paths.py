import os
import json
from typing import Any, Dict, Optional

# -------------------------
# resolucion de rutas base
# -------------------------

def get_project_root() -> str:
    """
    retorna ruta absoluta a la raiz del proyecto
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # utils -> src -> raiz
    return os.path.abspath(os.path.join(here, "..", ".."))

def get_servicios_dir() -> str:
    """
    retorna ruta absoluta al directorio src/servicios
    """
    return os.path.join(get_project_root(), "src", "servicios")

def get_observar_path() -> str:
    """
    retorna la ruta absoluta a observar.json en src/servicios/observar.json
    """
    return os.path.join(get_servicios_dir(), "observar.json")

# -------------------------
# helpers json genericos
# -------------------------

def _ensure_parent_dir(path: str) -> None:
    """
    asegura existencia del directorio padre
    """
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

def _load_json_file(path: str) -> Dict[str, Any]:
    """
    carga json de disco; si no existe o esta vacio retorna {}
    """
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception:
        return {}

def _save_json_file(path: str, data: Dict[str, Any]) -> bool:
    """
    persiste dict como json; retorna True si tuvo exito
    """
    try:
        _ensure_parent_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

# -------------------------
# api especifica observar.json
# -------------------------

def load_observar() -> Dict[str, Any]:
    """
    retorna todo el contenido de observar.json como dict
    """
    return _load_json_file(get_observar_path())

def save_observar(data: Dict[str, Any]) -> bool:
    """
    guarda el dict completo en observar.json
    """
    return _save_json_file(get_observar_path(), data)

def load_observar_key(key: str, default: Optional[Any] = None) -> Any:
    """
    retorna el valor de una clave en observar.json o default si no existe
    """
    data = load_observar()
    return data.get(key, default)

def update_observar_key(key: str, value: Any) -> bool:
    """
    actualiza una clave en observar.json preservando el resto
    """
    data = load_observar()
    data[key] = value
    return save_observar(data)