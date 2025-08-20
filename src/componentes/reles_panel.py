from dash import html, dcc, no_update, dash_table
from dash.dependencies import Input, Output, State
import dash_daq as daq
import os
import json # Importamos la libreria json
from datetime import datetime
from src.persistencia.dao_reles import reles_dao
from src.persistencia.dao_fallas_reles import fallas_reles_dao
import config

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
                label='Observar Reles MiCOM',
                labelPosition='right',
                on=False,
                style={'margin-right': '10px'}
            ),
            # El Div para el Output es mantenido, pero el callback retornara no_update
            html.Div(id='reles-micom-observer-status', className='hidden-element')
        ], className='reles-controls-container'),

        html.Div(
            id='reles-faults-container',
            children=[html.P("Cargando datos de fallas de reles...")],
            className='reles-faults-grid-container'
        ),

        # Componente dcc.Interval para refrescar los datos de las fallas
        dcc.Interval(
            id='reles-faults-interval',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
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
        Output('reles-micom-observer-status', 'children'),
        Input('reles-micom-observer-toggle', 'on')
    )
    def update_observer_status(is_observing):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..'))
        # Cambiamos la extension del archivo a .json
        observar_file_path = os.path.join(project_root, 'observador', 'observar.json')
        
        relative_observar_file_path = os.path.relpath(observar_file_path, project_root)

        try:
            # Leer el contenido actual del archivo
            if os.path.exists(observar_file_path):
                with open(observar_file_path, 'r') as f:
                    content = f.read()
                    if content:
                        data = json.loads(content)
                    else:
                        data = {}
            else:
                data = {}

            # Actualizar solo la clave 'reles_consultar'
            data['reles_consultar'] = is_observing
            
            # Escribir el objeto JSON completo de vuelta al archivo
            with open(observar_file_path, 'w') as f:
                json.dump(data, f, indent=4) # Usamos indent=4 para una mejor legibilidad del JSON

            console_log_message = f"Observador de Reles: {'ON' if is_observing else 'OFF'}. Estado de 'reles_consultar' guardado en {relative_observar_file_path}"
            print(console_log_message) 
        
        except (IOError, json.JSONDecodeError) as e:
            console_log_message = f"ERROR al guardar el estado en {relative_observar_file_path}: {e}"
            print(console_log_message)
        
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
        
        active_reles = reles_dao.get_all_reles_with_descriptions()

        if not active_reles:
            return html.P("No hay reles activos configurados o con descripcion 'NO APLICA'.", className="text-gray-600 mt-4")

        for modbus_id, description in active_reles.items():
            internal_rele_id = reles_dao.get_internal_id_by_modbus_id(modbus_id)
            
            if internal_rele_id is not None:
                latest_falla = fallas_reles_dao.get_latest_falla_for_rele(internal_rele_id)
                
                if latest_falla:
                    formatted_timestamp = latest_falla['timestamp']
                    try:
                        dt_object = datetime.fromisoformat(latest_falla['timestamp'])
                        formatted_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass

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
                                style_table={'overflowX': 'auto'},
                                style_cell={'textAlign': 'left', 'fontFamily': 'Inter, sans-serif', 'padding': '8px 12px'},
                                style_header={'backgroundColor': '#66A5AD', 'color': 'white', 'fontWeight': 'bold'},
                                style_data_conditional=[
                                    {
                                        'if': {'row_index': 'odd'},
                                        'backgroundColor': '#C4DFE6'
                                    }
                                ]
                            )
                        ], className="reles-fault-card")
                    )

        if not fault_tables:
            return html.P("No hay datos de fallas disponibles para mostrar o no hay reles configurados.", className="text-gray-600 mt-4")
        
        return fault_tables