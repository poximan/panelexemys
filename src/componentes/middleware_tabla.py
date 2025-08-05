import dash
from dash import html
from dash.dependencies import Input, Output
import pandas as pd
from datetime import datetime
from src.persistencia.dao_historicos import historicos_dao as dao
from src.persistencia.dao_grd import grd_dao

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

        current_db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()

        if not current_db_grd_descriptions:
            no_grd_message = "ADVERTENCIA: No se han encontrado equipos GRD en la base de datos para consulta."
            return "Detalles del Equipo", html.P(no_grd_message, className="warning-text")

        if selected_grd_id is None:
            default_message = "Por favor, seleccione un equipo GRD del menu desplegable."
            return "Detalles del Equipo", html.P(default_message, className="info-text")


        today_str = datetime.now().strftime('%Y-%m-%d')
        df = pd.DataFrame()

        # Replicamos la logica de carga de datos para la tabla
        if time_window == '1sem':
            df = dao.get_weekly_data_for_grd(selected_grd_id, today_str, page_number)
        elif time_window == '1mes':
            df = dao.get_monthly_data_for_grd(selected_grd_id, today_str, page_number)
        elif time_window == 'todo':
            df = dao.get_all_data_for_grd(selected_grd_id)

        if df.empty:
            table_content = html.P(f"No hay datos recientes para el GRD ID {selected_grd_id} en el periodo seleccionado.", className="warning-text")
            # Obtener y usar la descripcion del GRD para el titulo de la tabla de detalles
            grd_description_for_table_title = grd_dao.get_grd_description(selected_grd_id)
            grd_data_title_text = f"Detalles del Equipo GRD {selected_grd_id} ({grd_description_for_table_title})" if grd_description_for_table_title else f"Detalles del Equipo GRD {selected_grd_id}"
            return grd_data_title_text, table_content

        latest_record = df.sort_values(by='timestamp', ascending=False).iloc[0]

        table_header = html.Thead(html.Tr([
            html.Th("Campo", className="table-header-cell"),
            html.Th("Valor", className="table-header-cell")
        ]))

        table_rows = [
            html.Tr([
                html.Td("Ultima Actualizacion", className="table-data-cell"),
                html.Td(latest_record['timestamp'].strftime("%Y-%m-%d %H:%M:%S"), className="table-data-cell-mono")
            ]),
            html.Tr([
                html.Td("GRD ID", className="table-data-cell"),
                html.Td(latest_record['id_grd'], className="table-data-cell-mono")
            ]),
            html.Tr([
                html.Td("Estado Conectado", className="table-data-cell"),
                html.Td("Si" if latest_record['conectado'] == 1 else "No",
                        className=f"table-data-cell-status {'status-connected' if latest_record['conectado']==1 else 'status-disconnected'}")
            ]),
        ]

        table_content = html.Table(className="data-table", children=[
            table_header,
            html.Tbody(table_rows)
        ])

        grd_description_for_table_title = grd_dao.get_grd_description(selected_grd_id)
        grd_data_title_text = f"Estado actual de {grd_description_for_table_title}"

        return grd_data_title_text, table_content