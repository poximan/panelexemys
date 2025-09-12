from dash import html, dcc, no_update, dash_table
from dash.dependencies import Input, Output, State
import dash_daq as daq
from datetime import datetime
from src.persistencia.dao.dao_reles import reles_dao
from src.persistencia.dao.dao_fallas_reles import fallas_reles_dao
from src.utils.paths import update_observar_key
import config

def get_reles_micom_layout():
    """
    layout de la pestaña Reles MiCOM con switch de observacion y tabla de fallas
    """
    return html.Div(children=[
        html.H1("Estado Reles MiCOM", className='main-title'),

        html.Div([
            daq.BooleanSwitch(
                id='reles-micom-observer-toggle',
                label='Observar Reles MiCOM',
                labelPosition='right',
                on=False,
                style={'margin-right': '10px'}
            ),
            html.Div(id='reles-micom-observer-status', className='hidden-element')
        ], className='reles-controls-container'),

        html.Div(
            id='reles-faults-container',
            children=[html.P("Cargando datos de fallas de reles...")],
            className='reles-faults-grid-container'
        ),

        dcc.Interval(
            id='reles-faults-interval',
            interval=config.DASHBOARD_REFRESH_INTERVAL_MS,
            n_intervals=0
        )
    ])

def register_reles_micom_callbacks(app):
    """
    registra callbacks de la pestaña Reles MiCOM
    """
    @app.callback(
        Output('reles-micom-observer-status', 'children'),
        Input('reles-micom-observer-toggle', 'on')
    )
    def update_observer_status(is_observing):
        """
        persiste bandera reles_consultar en observar.json
        """
        try:
            update_observar_key("reles_consultar", bool(is_observing))
        except Exception:
            pass
        return no_update

    @app.callback(
        Output('reles-faults-container', 'children'),
        Input('reles-faults-interval', 'n_intervals')
    )
    def update_reles_faults_display(_n_intervals):
        """
        arma tarjetas con la ultima falla por rele activo
        """
        from dash import html  # import local para evitar dependencias circulares

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