from dash import html, dcc, no_update
from dash.dependencies import Input, Output, State
import dash_daq as daq  # Importar dash_daq
import os               # Necesario para manipular rutas de archivo

# --- Funciones de Layout ---

def get_reles_micom_layout():
    """
    Define el layout para la pestaña 'Relés MiCOM'.
    Incluye un BooleanSwitch de dash_daq para controlar la observación de relés y un área de estado.
    """

    return html.Div(children=[
        html.H1("Estado relés MiCOM", className='main-title', style={'fontFamily': 'Inter, sans-serif'}), 
        
        html.Div([
            # Usamos daq.BooleanSwitch directamente con su propia etiqueta
            daq.BooleanSwitch(
                id='reles-micom-observer-toggle',
                label='Observar Relés MiCOM', # Etiqueta para el switch
                labelPosition='right', # Posición de la etiqueta (puede ser 'left' o 'right')
                on=False, # 'on' es la propiedad para el valor booleano en BooleanSwitch
                style={'margin-right': '10px'} # Estilo para el contenedor del switch
            ),
            # El Div para el Output es mantenido, pero el callback retornará no_update
            html.Div(id='reles-micom-observer-status', style={'display': 'none'}) # Ocultar visualmente
        ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '20px'}),

        html.Div("Este es un panel de ejemplo para Relés MiCOM.", style={'padding': '20px', 'border': '1px dashed #ccc', 'margin-top': '20px'})
        # Puedes añadir más componentes Dash aquí: dcc.Graph, dash_table.DataTable, dcc.Input, etc.
    ], className='main-container')

# --- Registro de Callbacks ---

def register_reles_micom_callbacks(app):
    """
    Registra los callbacks específicos para la pestaña 'Relés MiCOM'.
    Incluye el callback para el switch de observación.
    """
    @app.callback(
        Output('reles-micom-observer-status', 'children'), # El Output debe permanecer para que el callback sea registrado
        Input('reles-micom-observer-toggle', 'on') # El Input ahora es 'on' para BooleanSwitch
    )
    def update_observer_status(is_observing):

        # Construye la ruta absoluta para el archivo observar.txt
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..')) # Sube un nivel a partir de 'componentes'
        observar_file_path = os.path.join(project_root, 'observador', 'observar.txt')
        
        # Calcula la ruta relativa al directorio raíz del proyecto
        relative_observar_file_path = os.path.relpath(observar_file_path, project_root)

        # Garantiza que la carpeta 'observador' exista
        os.makedirs(os.path.dirname(observar_file_path), exist_ok=True)

        # Escribe el estado en el archivo
        try:
            with open(observar_file_path, 'w') as f:
                f.write(str(is_observing))
            
            # Mensaje para la consola (ahora con la ruta relativa)
            console_log_message = f"Observador de Relés: {'ON' if is_observing else 'OFF'}. Estado guardado en {relative_observar_file_path}"
            print(console_log_message) 
            
        except Exception as e:
            # Mensaje de error para la consola (con la ruta relativa)
            console_log_message = f"ERROR al guardar el estado en {relative_observar_file_path}: {e}"
            print(console_log_message)
        
        # Retorna no_update para evitar que el mensaje sea exhibido en la interfaz del usuario
        return no_update 

    # Aquí puedes añadir más callbacks específicos para esta página en el futuro
    pass