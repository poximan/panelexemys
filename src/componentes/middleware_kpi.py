import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from datetime import datetime
from src.persistencia.dao_historicos import historicos_dao as dao
from src.persistencia.dao_grd import grd_dao

def get_kpi_panel_layout():
    """
    Define el layout para el panel de indicadores KPI (Gauge, Semáforo, Lista de desconectados).
    """
    return html.Div(className='kpi-panel-container', children=[
        # Indicador de Aguja (Gauge)
        html.Div(className='kpi-item gauge-graph-container', children=[
            dcc.Graph(
                id='connection-gauge',
                config={'displayModeBar': False},
                className='gauge-graph'
            ),
        ]),

        # Semáforo de Estado
        html.Div(className='kpi-item traffic-light-container', children=[
            html.H3("Salud conexión", className='kpi-subtitle'),
            html.Div(className='traffic-light-circles-wrapper', children=[
                html.Div(id='traffic-light-red', className='traffic-light-circle initial-gray'),
                html.Div(id='traffic-light-yellow', className='traffic-light-circle initial-gray'),
                html.Div(id='traffic-light-green', className='traffic-light-circle initial-gray'),
            ])
        ]),

        # Lista de Equipos Desconectados (Tabla)
        html.Div(className='kpi-item disconnected-list-container', children=[
            html.H3("Actualmente Desconectados", className='kpi-subtitle'),
            html.Div(className='disconnected-table-wrapper', children=[
                html.Table(id='disconnected-grds-table', className='disconnected-table', children=[
                    html.Thead(html.Tr([
                        html.Th("Equipo", className='disconnected-table-header-cell'),
                        html.Th("Última Caída", className='disconnected-table-header-cell'),
                        # NEW COLUMN: Tiempo Desconectado
                        html.Th("T.Desc. (min)", className='disconnected-table-header-cell')
                    ])),
                    html.Tbody(id='disconnected-table-body', children=[])
                ])
            ])
        ]),
    ])


def register_kpi_panel_callbacks(app: dash.Dash, config):
    """
    Registra los callbacks para el panel de indicadores KPI.
    """
    @app.callback(
        Output('connection-gauge', 'figure'),
        Output('traffic-light-green', 'style'),
        Output('traffic-light-yellow', 'style'),
        Output('traffic-light-red', 'style'),
        Output('disconnected-table-body', 'children'),
        Input('interval-component', 'n_intervals')
    )
    def update_kpi_panel(n_intervals):
        latest_states_from_db = dao.get_latest_states_for_all_grds()

        total_grds_for_kpi = len(latest_states_from_db)
        connected_grds_count = sum(1 for state in latest_states_from_db.values() if state == 1)

        if total_grds_for_kpi > 0:
            connection_percentage = (connected_grds_count / total_grds_for_kpi) * 100
        else:
            connection_percentage = 0

        gauge_figure = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=connection_percentage,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Grado conectividad", 'font': {'size': 20, 'family': 'Inter', 'color': '#4a5568'}},
                number={'suffix': "%", 'font': {'size': 24}},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "darkblue"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, config.GLOBAL_THRESHOLD_ROJO - 1], 'color': '#f8d7da'},
                        {'range': [config.GLOBAL_THRESHOLD_ROJO, config.GLOBAL_THRESHOLD_AMARILLO - 1], 'color': '#fff3cd'},
                        {'range': [config.GLOBAL_THRESHOLD_AMARILLO, 100], 'color': '#d4edda'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': connection_percentage
                    }
                }
            )
        )
        gauge_figure.update_layout(height=200, margin={'l': 10, 'r': 10, 't': 40, 'b': 0})

        green_style = {'backgroundColor': '#ccc', 'transition': 'background-color 0.5s'}
        yellow_style = {'backgroundColor': '#ccc', 'transition': 'background-color 0.5s'}
        red_style = {'backgroundColor': '#ccc', 'transition': 'background-color 0.5s'}

        if connection_percentage >= config.GLOBAL_THRESHOLD_AMARILLO:
            green_style['backgroundColor'] = '#28a745'
        elif connection_percentage >= config.GLOBAL_THRESHOLD_ROJO:
            yellow_style['backgroundColor'] = '#ffc107'
        else:
            red_style['backgroundColor'] = '#dc3545'

        disconnected_grds_data = dao.get_all_disconnected_grds()

        disconnected_table_rows = []
        if disconnected_grds_data:
            current_time = datetime.now() # Get current time once for efficiency
            for item in disconnected_grds_data:
                timestamp_obj = item.get('last_disconnected_timestamp')
                timestamp_str = 'N/A'
                time_disconnected_minutes = 'N/A'

                if isinstance(timestamp_obj, datetime):
                    timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S")
                    time_difference = current_time - timestamp_obj
                    # Calculate difference in minutes and format it nicely
                    total_seconds = int(time_difference.total_seconds())
                    minutes = total_seconds // 60
                    hours = minutes // 60
                    days = hours // 24

                    if days > 0:
                        time_disconnected_minutes = f"{days}d {hours % 24}h {minutes % 60}m"
                    elif hours > 0:
                        time_disconnected_minutes = f"{hours}h {minutes % 60}m"
                    else:
                        time_disconnected_minutes = f"{minutes}m"

                grd_description = grd_dao.get_grd_description(item['id_grd'])
                display_name = f"GRD {item['id_grd']} ({grd_description})" if grd_description else f"GRD {item['id_grd']}"

                disconnected_table_rows.append(
                    html.Tr([
                        html.Td(display_name, className='disconnected-table-data-cell'),
                        html.Td(timestamp_str, className='disconnected-table-timestamp-cell'),
                        # NEW CELL: Time Disconnected
                        html.Td(time_disconnected_minutes, className='disconnected-table-data-cell')
                    ])
                )
        else:
            disconnected_table_rows.append(
                html.Tr(html.Td("Todos los equipos conectados.", colSpan=3, className='disconnected-table-empty-message'))
            )

        return gauge_figure, green_style, yellow_style, red_style, disconnected_table_rows