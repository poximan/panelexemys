import dash
from dash import html
from dash.dependencies import Input, Output
from datetime import datetime
from src.web.clients.modbus_client import modbus_client

def get_main_data_table_layout():
    """
    Define el layout para la tabla de detalles del GRD y su titulo.
    """
    return html.Div(children=[
        html.H2(id='grd-data-title', className='grd-data-title'),
        html.Div(id='grd-data-table', className='grd-table-container'),
    ])


def register_main_data_table_callbacks(app: dash.Dash):
    """
    Registra los callbacks relacionados con la tabla de detalles del GRD.
    """
    @app.callback(
        Output('grd-data-title', 'children'),
        Output('grd-data-table', 'children'),
        [Input('time-window-state', 'data'),
         Input('interval-component', 'n_intervals')] # La tabla tambien se actualiza con el intervalo
    )
    def update_grd_data_table(time_window_state_data, n_intervals):
        selected_grd_id = time_window_state_data['current_grd_id']
        time_window = time_window_state_data['time_window']
        page_number = time_window_state_data['page_number']

        try:
            current_db_grd_descriptions = modbus_client.get_descriptions()
        except Exception:
            current_db_grd_descriptions = {}

        if not current_db_grd_descriptions:
            no_grd_message = "ADVERTENCIA: No se han encontrado equipos GRD en la base de datos para consulta."
            return "Detalles del Equipo", html.P(no_grd_message, className="warning-text")

        if selected_grd_id is None:
            default_message = "Por favor, seleccione un equipo GRD del menu desplegable."
            return "Detalles del Equipo", html.P(default_message, className="info-text")


        try:
            history = modbus_client.get_history(selected_grd_id, time_window, page_number)
        except Exception:
            history = {"data": []}
        records = history.get("data", [])

        if not records:
            table_content = html.P(f"No hay datos recientes para el GRD ID {selected_grd_id} en el periodo seleccionado.", className="warning-text")
            grd_description_for_table_title = current_db_grd_descriptions.get(selected_grd_id)
            grd_data_title_text = f"Detalles del Equipo GRD {selected_grd_id} ({grd_description_for_table_title})" if grd_description_for_table_title else f"Detalles del Equipo GRD {selected_grd_id}"
            return grd_data_title_text, table_content

        latest_record = records[-1]
        timestamp_val = latest_record.get('timestamp')
        if isinstance(timestamp_val, str):
            try:
                timestamp_display = datetime.fromisoformat(timestamp_val).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                timestamp_display = timestamp_val
        else:
            timestamp_display = str(timestamp_val)

        table_header = html.Thead(html.Tr([
            html.Th("Campo", className="table-header-cell"),
            html.Th("Valor", className="table-header-cell")
        ]))

        table_rows = [
            html.Tr([
                html.Td("Ultima Actualizacion", className="table-data-cell"),
                html.Td(timestamp_display, className="table-data-cell-mono")
            ]),
            html.Tr([
                html.Td("GRD ID", className="table-data-cell"),
                html.Td(latest_record.get('id_grd'), className="table-data-cell-mono")
            ]),
            html.Tr([
                html.Td("Estado Conectado", className="table-data-cell"),
                html.Td("Si" if latest_record.get('conectado') == 1 else "No",
                        className=f"table-data-cell-status {'status-connected' if latest_record.get('conectado')==1 else 'status-disconnected'}")
            ]),
        ]

        table_content = html.Table(className="data-table", children=[
            table_header,
            html.Tbody(table_rows)
        ])

        grd_description_for_table_title = current_db_grd_descriptions.get(selected_grd_id)
        grd_data_title_text = f"Estado actual de {grd_description_for_table_title}"

        return grd_data_title_text, table_content
