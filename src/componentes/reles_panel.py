from dash import html, dcc, no_update, dash_table
from dash.dependencies import Input, Output, State
import dash_daq as daq
import os
from datetime import datetime # Importacion corregida: necesario para datetime.fromisoformat
from src.persistencia.dao_reles import reles_dao # Importa el DAO para la tabla 'reles'
from src.persistencia.dao_fallas_reles import fallas_reles_dao # Importa el DAO para la tabla 'fallas_reles'
import config # Importacion corregida: necesario para config.DASHBOARD_REFRESH_INTERVAL_MS

# --- Funciones de Layout ---

def get_reles_micom_layout():
    """
    Define el layout para la pestaña 'Reles MiCOM'.
    Incluye un BooleanSwitch de dash_daq para controlar la observacion de reles,
    un area de estado, y un contenedor para las tablas de fallas.
    """
    return html.Div(children=[
        html.H1("Estado Reles MiCOM", className='main-title'),
        
        html.Div([
            # Usamos daq.BooleanSwitch directamente con su propia etiqueta
            daq.BooleanSwitch(
                id='reles-micom-observer-toggle',
                label='Observar Reles MiCOM', # Etiqueta para el switch
                labelPosition='right', # Posicion de la etiqueta (puede ser 'left' o 'right')
                on=False, # 'on' es la propiedad para el valor booleano en BooleanSwitch
                style={'margin-right': '10px'} # Estilo especifico, se mantiene inline
            ),
            # El Div para el Output es mantenido, pero el callback retornara no_update
            html.Div(id='reles-micom-observer-status', className='hidden-element') # Estilo migrado
        ], className='reles-controls-container'),

        html.Div(
            id='reles-faults-container',
            children=[html.P("Cargando datos de fallas de reles...")],
            className='reles-faults-grid-container'
        ),

        # Componente dcc.Interval para refrescar los datos de las fallas
        dcc.Interval(
            id='reles-faults-interval',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS, # Intervalo de refresco desde config
            n_intervals=0
        )
    ])

# --- Registro de Callbacks ---

def register_reles_micom_callbacks(app):
    """
    Registra los callbacks especificos para la pestaña 'Reles MiCOM'.
    Incluye el callback para el switch de observacion y para la tabla de fallas.
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
        
        # Calcula la ruta relativa al directorio raiz del proyecto
        relative_observar_file_path = os.path.relpath(observar_file_path, project_root)

        # Escribe el estado en el archivo
        try:
            with open(observar_file_path, 'w') as f:
                f.write(str(is_observing).lower()) # Escribe 'true' o 'false' en minusculas
            
            # Mensaje para la consola (ahora con la ruta relativa)
            console_log_message = f"Observador de Reles: {'ON' if is_observing else 'OFF'}. Estado guardado en {relative_observar_file_path}"
            print(console_log_message) 
            
        except Exception as e:
            # Mensaje de error para la consola (con la ruta relativa)
            console_log_message = f"ERROR al guardar el estado en {relative_observar_file_path}: {e}"
            print(console_log_message)
        
        # Retorna no_update para evitar que el mensaje sea exhibido en la interfaz del usuario
        return no_update 

    @app.callback(
        Output('reles-faults-container', 'children'),
        Input('reles-faults-interval', 'n_intervals')
    )
    def update_reles_faults_display(n_intervals):
        """
        Actualiza la visualizacion de las ultimas fallas de los reles.
        """
        fault_tables = []
        
        # Obtener todos los reles activos desde la base de datos
        active_reles = reles_dao.get_all_reles_with_descriptions()

        if not active_reles:
            return html.P("No hay reles activos configurados o con descripcion 'NO APLICA'.", className="text-gray-600 mt-4")

        for modbus_id, description in active_reles.items():
            # Obtener el ID interno del rele para consultar la tabla de fallas
            internal_rele_id = reles_dao.get_internal_id_by_modbus_id(modbus_id)
            
            if internal_rele_id is not None:
                latest_falla = fallas_reles_dao.get_latest_falla_for_rele(internal_rele_id)
                
                if latest_falla:
                    # Formatear el timestamp para una mejor lectura
                    formatted_timestamp = latest_falla['timestamp']
                    try:
                        # Intenta convertir a datetime y luego formatear si es posible
                        dt_object = datetime.fromisoformat(latest_falla['timestamp'])
                        formatted_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass # Si no se puede convertir, usa el string original

                    # Preparar datos para Dash DataTable
                    data_for_table = [
                        {"Atributo": "ID Modbus", "Valor": modbus_id},
                        {"Atributo": "Descripcion", "Valor": description},
                        {"Atributo": "Numero de Falla", "Valor": latest_falla['numero_falla']},
                        {"Atributo": "Fecha/Hora", "Valor": formatted_timestamp},
                        {"Atributo": "Corriente Fase A", "Valor": latest_falla['fasea_corr']},
                        {"Atributo": "Corriente Fase B", "Valor": latest_falla['faseb_corr']},
                        {"Atributo": "Corriente Fase C", "Valor": latest_falla['fasec_corr']},
                        {"Atributo": "Corriente Tierra", "Valor": latest_falla['tierra_corr']},
                    ]

                    fault_tables.append(
                        html.Div([                            
                            dash_table.DataTable(
                                id=f'falla-table-{modbus_id}',
                                columns=[
                                    {"name": "Atributo", "id": "Atributo"},
                                    {"name": "Valor", "id": "Valor"}
                                ],
                                data=data_for_table,
                                style_table={'overflowX': 'auto'}, # margin-bottom movido a CSS
                                style_cell={'textAlign': 'left', 'fontFamily': 'Inter, sans-serif', 'padding': '8px 12px'}, # Se mantiene inline por especificidad o se puede migrar
                                style_header={'backgroundColor': '#66A5AD', 'color': 'white', 'fontWeight': 'bold'}, # Se mantiene inline por especificidad o se puede migrar
                                style_data_conditional=[
                                    {
                                        'if': {'row_index': 'odd'},
                                        'backgroundColor': '#C4DFE6' # Se mantiene inline, ya que style_data_conditional es una propiedad de Dash
                                    }
                                ]
                            )
                        ], className="reles-fault-card") # Estilo migrado
                    )

        if not fault_tables:
            return html.P("No hay datos de fallas disponibles para mostrar o no hay reles configurados.", className="text-gray-600 mt-4")
        
        return fault_tables