import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from src.persistencia.dao_historicos import historicos_dao as dao
from src.persistencia.dao_grd import grd_dao

BUTTON_CLASS_DEFAULT = 'button-default'
BUTTON_CLASS_ACTIVE = 'button-active'
STATE_TEXT_MAP = {0: "Desconectado", 1: "Conectado"}

def get_controls_and_graph_layout(db_grd_descriptions, initial_grd_value):
    """
    Define el layout para los controles (dropdown, botones de tiempo, paginación)
    y el gráfico principal de conexión.
    """
    return html.Div(className='controls-and-graph-container', children=[
        # Contenedor para Dropdown y Botones de Tiempo/Paginación
        html.Div(className='controls-panel', children=[
            html.Div(className='dropdown-container', children=[
                html.Label("Seleccionar GRD", className='control-label'),
                dcc.Dropdown(
                    id='grd-id-dropdown',
                    options=[{'label': desc, 'value': _id} for _id, desc in db_grd_descriptions.items()],
                    value=initial_grd_value,
                    clearable=False,
                    placeholder="No hay equipos para seleccionar" if not db_grd_descriptions else "Seleccione un GRD",
                    className='grd-id-dropdown'
                ),
            ]),
            html.Div(className='time-buttons-wrapper-outer', children=[
                html.Label("Ventana de Datos", className='control-label'),
                html.Div(className='time-buttons-wrapper-inner', children=[
                    html.Button('1 Sem', id='1sem-btn', n_clicks=0,
                                 className=BUTTON_CLASS_ACTIVE if initial_grd_value and '1sem' == '1sem' else BUTTON_CLASS_DEFAULT),
                    html.Button('1 Mes', id='1mes-btn', n_clicks=0,
                                 className=BUTTON_CLASS_ACTIVE if initial_grd_value and '1mes' == '1sem' else BUTTON_CLASS_DEFAULT),
                    html.Button('Todo', id='todo-btn', n_clicks=0,
                                 className=BUTTON_CLASS_ACTIVE if initial_grd_value and 'todo' == '1sem' else BUTTON_CLASS_DEFAULT),
                ]),
                html.Div(id='pagination-controls', className='pagination-controls-container', children=[
                    html.Button('Anterior', id='prev-btn', n_clicks=0, className='pagination-button'),
                    html.Button('Siguiente', id='next-btn', n_clicks=0, className='pagination-button'),
                ]),
            ]),
        ]),

        # Contenedor para el Gráfico Principal
        html.Div(className='main-graph-section', children=[
            # Mensaje de advertencia si no hay equipos configurados
            html.Div(id='no-grd-warning', className='no-grd-warning',
                     children="ADVERTENCIA: No se han encontrado equipos GRD en la base de datos para consulta." if not db_grd_descriptions else ""),
            # Gráfico principal del estado 'conectado'
            dcc.Graph(
                id='connected-wave-graph',
                className='connected-graph-container',
                config={'displayModeBar': True}
            ),
        ]),
    ])


def register_controls_and_graph_callbacks(app: dash.Dash):
    """
    Registra los callbacks relacionados con los controles de selección
    y el gráfico principal de conexión.
    """

    @app.callback(
        Output('time-window-state', 'data'),
        Output('1sem-btn', 'className'),
        Output('1mes-btn', 'className'),
        Output('todo-btn', 'className'),
        [Input('1sem-btn', 'n_clicks'),
         Input('1mes-btn', 'n_clicks'),
         Input('todo-btn', 'n_clicks'),
         Input('grd-id-dropdown', 'value')],
        [State('time-window-state', 'data')]
    )
    def set_time_window_and_grd(n_1sem, n_1mes, n_todo, selected_grd_id_from_dropdown, current_state_data):
        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

        new_state = current_state_data.copy()

        if not triggered_id or triggered_id == 'grd-id-dropdown':
            new_state['page_number'] = 0
            if triggered_id == 'grd-id-dropdown':
                new_state['current_grd_id'] = selected_grd_id_from_dropdown

        if triggered_id == '1sem-btn':
            new_state['time_window'] = '1sem'
            new_state['page_number'] = 0
        elif triggered_id == '1mes-btn':
            new_state['time_window'] = '1mes'
            new_state['page_number'] = 0
        elif triggered_id == 'todo-btn':
            new_state['time_window'] = 'todo'
            new_state['page_number'] = 0

        if triggered_id != 'grd-id-dropdown':
            new_state['current_grd_id'] = selected_grd_id_from_dropdown

        class_1sem = BUTTON_CLASS_ACTIVE if new_state['time_window'] == '1sem' else BUTTON_CLASS_DEFAULT
        class_1mes = BUTTON_CLASS_ACTIVE if new_state['time_window'] == '1mes' else BUTTON_CLASS_DEFAULT
        class_todo = BUTTON_CLASS_ACTIVE if new_state['time_window'] == 'todo' else BUTTON_CLASS_DEFAULT

        return new_state, class_1sem, class_1mes, class_todo

    @app.callback(
        Output('time-window-state', 'data', allow_duplicate=True),
        [Input('prev-btn', 'n_clicks'),
         Input('next-btn', 'n_clicks')],
        [State('time-window-state', 'data')],
        prevent_initial_call=True
    )
    def navigate_pages(n_prev, n_next, current_state_data):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        new_state = current_state_data.copy()
        time_window = new_state['time_window']
        page_number = new_state['page_number']
        grd_id = new_state['current_grd_id']

        if grd_id is None or time_window == 'todo':
            raise dash.exceptions.PreventUpdate

        today_str = datetime.now().strftime('%Y-%m-%d')
        total_segments = 0
        if time_window == '1sem':
            total_segments = dao.get_total_weeks_for_grd(grd_id, today_str)
        elif time_window == '1mes':
            total_segments = dao.get_total_months_for_grd(grd_id, today_str)

        if total_segments <= 0:
            raise dash.exceptions.PreventUpdate

        if button_id == 'prev-btn':
            if page_number < total_segments - 1:
                new_state['page_number'] = page_number + 1
            else:
                raise dash.exceptions.PreventUpdate
        elif button_id == 'next-btn':
            if page_number > 0:
                new_state['page_number'] = page_number - 1
            else:
                raise dash.exceptions.PreventUpdate

        return new_state

    @app.callback(
        Output('pagination-controls', 'style'),
        Output('prev-btn', 'disabled'),
        Output('next-btn', 'disabled'),
        [Input('time-window-state', 'data')]
    )
    def update_pagination_controls(time_window_state_data):
        time_window = time_window_state_data['time_window']
        page_number = time_window_state_data['page_number']
        grd_id = time_window_state_data['current_grd_id']

        if time_window == 'todo' or grd_id is None:
            return {'display': 'none'}, True, True

        today_str = datetime.now().strftime('%Y-%m-%d')
        total_segments = 0
        if time_window == '1sem':
            total_segments = dao.get_total_weeks_for_grd(grd_id, today_str)
        elif time_window == '1mes':
            total_segments = dao.get_total_months_for_grd(grd_id, today_str)

        if total_segments <= 1:
            return {'display': 'flex', 'justifyContent': 'center', 'gap': '1rem'}, True, True

        prev_disabled = (page_number == total_segments - 1)
        next_disabled = (page_number == 0)

        return {'display': 'flex', 'justifyContent': 'center', 'gap': '1rem'}, prev_disabled, next_disabled


    @app.callback(
        Output('connected-wave-graph', 'figure'),
        Output('no-grd-warning', 'children'), # Actualizamos el mensaje de advertencia del gráfico
        [Input('time-window-state', 'data'),
         Input('interval-component', 'n_intervals'), # Se sigue actualizando con el intervalo
         Input('connected-wave-graph', 'relayoutData')]
    )
    def update_connected_wave_graph(time_window_state_data, n_intervals, relayout_data):
        selected_grd_id = time_window_state_data['current_grd_id']

        current_db_grd_descriptions = grd_dao.get_all_grds_with_descriptions()

        if not current_db_grd_descriptions:
            no_grd_message = "ADVERTENCIA: No se han encontrado equipos GRD en la base de datos para consulta."
            fig = go.Figure(data=[], layout=go.Layout(
                title={'text': no_grd_message, 'font': dict(family="Inter", size=20, color="#333")},
                xaxis={'visible': False}, yaxis={'visible': False}, height=400,
                font=dict(family="Inter", size=14, color="#333")
            ))
            return fig, no_grd_message # Retornamos el mensaje para el Div de advertencia

        if selected_grd_id is None:
            default_message = "Por favor, seleccione un equipo GRD del menú desplegable."
            fig = go.Figure(data=[], layout=go.Layout(
                title={'text': default_message, 'font': dict(family="Inter", size=20, color="#333")},
                xaxis={'visible': False}, yaxis={'visible': False}, height=400,
                font=dict(family="Inter", size=14, color="#333")
            ))
            return fig, default_message # Retornamos el mensaje para el Div de advertencia


        time_window = time_window_state_data['time_window']
        page_number = time_window_state_data['page_number']

        today_str = datetime.now().strftime('%Y-%m-%d')
        df = pd.DataFrame()

        xaxis_tickformat = "%d/%m/%y %H:%M"
        xaxis_dtick = None
        xaxis_tickangle = 0

        if time_window == '1sem':
            df = dao.get_weekly_data_for_grd(selected_grd_id, today_str, page_number)
            grd_title_period = f"Semana {page_number + 1} (última semana al {datetime.strptime(today_str, '%Y-%m-%d').strftime('%d/%m/%Y')})"
        elif time_window == '1mes':
            df = dao.get_monthly_data_for_grd(selected_grd_id, today_str, page_number)
            grd_title_period = f"Mes {page_number + 1} (último mes al {datetime.strptime(today_str, '%Y-%m-%d').strftime('%d/%m/%Y')})"
            xaxis_tickformat = "%d/%m/%y"
        elif time_window == 'todo':
            df = dao.get_all_data_for_grd(selected_grd_id)
            grd_title_period = "Todos los Datos"
            xaxis_tickformat = "%m/%y"
            xaxis_dtick = "M1"
            xaxis_tickangle = 0

        grd_description_for_title = grd_dao.get_grd_description(selected_grd_id)
        grd_title_text = f"Histórico de Conexión - {grd_title_period}" if grd_description_for_title else f"Histórico de Conexión - GRD {selected_grd_id} - {grd_title_period}"

        traces = []
        shapes = []
        plot_x_line = []
        plot_y_line = []
        custom_hover_data_for_line = []

        if not df.empty:
            df = df.sort_values(by='timestamp').reset_index(drop=True)

            plot_start_time = df['timestamp'].min()
            plot_end_time = df['timestamp'].max()
            if page_number == 0 and time_window != 'todo':
                plot_end_time = datetime.now()
            
            initial_state_before_window = dao.get_connected_state_before_timestamp(selected_grd_id, plot_start_time)
            current_state_for_plot = initial_state_before_window if initial_state_before_window is not None else (df['conectado'].iloc[0] if not df.empty else 0)

            plot_x_line.append(plot_start_time)
            plot_y_line.append(current_state_for_plot)
            custom_hover_data_for_line.append(STATE_TEXT_MAP[current_state_for_plot])

            for i in range(len(df)):
                current_ts_data_point = df['timestamp'].iloc[i]
                current_val_data_point = df['conectado'].iloc[i]

                segment_start_time = plot_x_line[-1]
                segment_end_time = current_ts_data_point

                if segment_start_time < segment_end_time:
                    shapes.append(
                        dict(
                            type="rect", xref="x", yref="y",
                            x0=segment_start_time, y0=0, x1=segment_end_time, y1=1,
                            fillcolor='#28a745' if current_state_for_plot == 1 else '#dc3545',
                            opacity=0.4, layer="below", line_width=0,
                        )
                    )

                plot_x_line.append(current_ts_data_point)
                plot_y_line.append(current_state_for_plot)
                custom_hover_data_for_line.append(STATE_TEXT_MAP[current_state_for_plot])

                plot_x_line.append(current_ts_data_point)
                plot_y_line.append(current_val_data_point)
                custom_hover_data_for_line.append(STATE_TEXT_MAP[current_val_data_point])

                current_state_for_plot = current_val_data_point

            if plot_x_line[-1] < plot_end_time:
                shapes.append(
                    dict(
                        type="rect", xref="x", yref="y",
                        x0=plot_x_line[-1], y0=0, x1=plot_end_time, y1=1,
                        fillcolor='#28a745' if current_state_for_plot == 1 else '#dc3545',
                        opacity=0.4, layer="below", line_width=0,
                    )
                )
                plot_x_line.append(plot_end_time)
                plot_y_line.append(current_state_for_plot)
                custom_hover_data_for_line.append(STATE_TEXT_MAP[current_state_for_plot])

            traces.append(
                go.Scatter(
                    x=plot_x_line, y=plot_y_line, mode='lines',
                    line=dict(color='rgba(0,0,0,0)', width=0),
                    name='Estado de Conexión', customdata=custom_hover_data_for_line,
                    hovertemplate="<b>Fecha/Hora:</b> %{x|%Y-%m-%d %H:%M:%S}<br><b>Estado:</b> %{customdata}<extra></extra>"
                )
            )
        else:
            if time_window == '1sem':
                end_of_period = datetime.now() - timedelta(weeks=page_number)
                start_of_period = end_of_period - timedelta(days=6)
                plot_start_time = start_of_period.replace(hour=0, minute=0, second=0, microsecond=0)
                plot_end_time = end_of_period.replace(hour=23, minute=59, second=59, microsecond=999999)
            elif time_window == '1mes':
                ref_date = datetime.now() - relativedelta(months=page_number)
                plot_start_time = ref_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                plot_end_time = (plot_start_time + relativedelta(months=1) - timedelta(microseconds=1))
            else:
                plot_start_time = datetime.now() - timedelta(days=30)
                plot_end_time = datetime.now()

            initial_state_for_empty_df = dao.get_connected_state_before_timestamp(selected_grd_id, plot_start_time)
            default_val = initial_state_for_empty_df if initial_state_for_empty_df is not None else 0
            traces.append(
                go.Scatter(
                    x=[plot_start_time, plot_end_time], y=[default_val, default_val], mode='lines',
                    line=dict(color='rgba(0,0,0,0)', width=0), name='Sin Datos / Estado Anterior',
                    customdata=[STATE_TEXT_MAP[default_val], STATE_TEXT_MAP[default_val]],
                    hovertemplate="<b>Fecha/Hora:</b> %{x|%Y-%m-%d %H:%M:%S}<br><b>Estado:</b> %{customdata}<extra></extra>"
                )
            )
            shapes.append(
                dict(
                    type="rect", xref="x", yref="y",
                    x0=plot_start_time, y0=0, x1=plot_end_time, y1=1,
                    fillcolor='#28a745' if default_val == 1 else '#dc3545',
                    opacity=0.2, layer="below", line_width=0,
                )
            )

        fig = go.Figure(data=traces, layout={'shapes': shapes})

        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else 'initial_load'

        reset_zoom = False
        if triggered_id in ['grd-id-dropdown', '1sem-btn', '1mes-btn', 'todo-btn']:
            reset_zoom = True

        if relayout_data and 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data and not reset_zoom:
            fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
        else:
            fig.update_xaxes(range=[plot_start_time, plot_end_time])

        fig.update_layout(
            title={'text': grd_title_text, 'font': dict(size=20, family="Inter", color="#333")},
            xaxis_title='Fecha y Hora', yaxis_title='Estado',
            yaxis=dict(
                tickmode='array', tickvals=[0.25, 0.75], ticktext=['Desconectado', 'Conectado'],
                range=[-0.1, 1.1],
                fixedrange=True
            ),
            height=300,
            plot_bgcolor='#f8f9fa', paper_bgcolor='#ffffff',
            margin=dict(l=40, r=40, t=80, b=40), font=dict(family="Inter", size=12, color="#333"),
            modebar_add=["zoom", "pan", "resetscale"]
        )

        # Aquí siempre devolvemos un mensaje vacío para el div de advertencia
        # ya que el manejo de mensajes específicos (como "No hay datos recientes")
        # se hace directamente en el título del gráfico si no hay GRD o no hay selección.
        # Solo necesitamos el mensaje si no hay GRDs en la DB al inicio.
        warning_children = "ADVERTENCIA: No se han encontrado equipos GRD en la base de datos para consulta." if not current_db_grd_descriptions else ""

        return fig, warning_children