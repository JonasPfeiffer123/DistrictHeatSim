import pandapipes as pp
import pandapipes.plotting as plot
from pandapipes.timeseries import run_time_series
from pandapower.control.controller.const_control import ConstControl
from pandapower.timeseries import OutputWriter
from pandapower.timeseries import DFData

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

import net_simulation_pandapipes as nsp

def initialize_test_net():
    net = pp.create_empty_network(fluid="water")

    # Junctions for pump
    j1 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 1")
    j2 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 2")

    # Junctions for connection pipes forward line
    j3 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 3")
    j4 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 4")

    # Junctions for heat exchangers
    j5 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 5")
    j6 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 6")
    
    # Junctions for connection pipes 
    j7 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 7")
    j8 = pp.create_junction(net, pn_bar=1.05, tfluid_k=293.15, name="Junction 8")

    pump1 = pp.create_circ_pump_const_pressure(net, j1, j2, p_flow_bar=4,
                                               plift_bar=1.5, t_flow_k=273.15 + 90,
                                               type="auto", name="pump1")

    pipe1 = pp.create_pipe(net, j2, j3, std_type="110_PE_100_SDR_17", length_km=0.01,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe1", sections=5,
                           text_k=283)
    pipe2 = pp.create_pipe(net, j3, j4, std_type="110_PE_100_SDR_17", length_km=0.5,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe2", sections=5,
                           text_k=283)
    pipe3 = pp.create_pipe(net, j4, j5, std_type="110_PE_100_SDR_17", length_km=0.01,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe3", sections=5,
                           text_k=283)
    
    heat_exchanger1 = pp.create_heat_exchanger(net, j5, j6, diameter_m=0.02,
                                               loss_coefficient=100, qext_w=50000,
                                               name="heat_exchanger1")

    pipe4 = pp.create_pipe(net, j6, j7, std_type="110_PE_100_SDR_17", length_km=0.01,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe4", sections=5,
                           text_k=283)
    pipe5 = pp.create_pipe(net, j7, j8, std_type="110_PE_100_SDR_17", length_km=0.5,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe5", sections=5,
                           text_k=283)
    pipe6 = pp.create_pipe(net, j8, j1, std_type="110_PE_100_SDR_17", length_km=0.01,
                           k_mm=.1, alpha_w_per_m2k=10, name="pipe6", sections=5,
                           text_k=283)

    pp.pipeflow(net, mode="all")
    return net

def initialize_net():
    # GeoJSON-Dateien einlesen
    gdf_vl = gpd.read_file('geoJSON_Vorlauf.geojson')
    gdf_rl = gpd.read_file('geoJSON_Rücklauf.geojson')
    gdf_HAST = gpd.read_file('geoJSON_HAST.geojson')
    gdf_WEA = gpd.read_file('geoJSON_Erzeugeranlagen.geojson')

    pipe_creation_mode = "type"
    # pipe_creation_mode = "diameter"

    net = nsp.create_network(gdf_vl, gdf_rl, gdf_HAST, gdf_WEA, pipe_creation_mode)
    net = nsp.correct_flow_directions(net)

    if pipe_creation_mode == "diameter":
        net = nsp.optimize_diameter_parameters(net)

    if pipe_creation_mode == "type":
        net = nsp.optimize_diameter_types(net)

    #plot.simple_plot(net, junction_size=0.2, heat_exchanger_size=0.2, pump_size=0.2, pump_color='green',
     #                pipe_color='black', heat_exchanger_color='blue')

    nsp.export_net_geojson(net)

    # print(net.junction)
    # print(net.junction_geodata)
    # print(net.pipe)
    # print(net.heat_exchanger)
    # print(net.circ_pump_pressure)

    # print(net.res_junction)
    # print(net.res_pipe)
    # print(net.res_heat_exchanger)
    # print(net.res_circ_pump_pressure)

    return(net)

def time_series_net(net):
    time_steps = range(0, 24)  # hourly time steps
    df = pd.DataFrame(index=time_steps)

    qext_w_profile = [50000] * 3 + [60000] * 6 + [70000] * 9 + [80000] * 6
    
    for i in range(1):

        df = pd.DataFrame(index=time_steps, data={'qext_w_'+str(i): qext_w_profile})

        data_source = DFData(df)
        ConstControl(net, element='heat_exchanger', variable='qext_w', element_index=[i], data_source=data_source, profile_name='qext_w_'+str(i))

    log_variables = [('res_junction', 'p_bar'), ('res_pipe', 'v_mean_m_per_s'),
                     ('res_pipe', 'reynolds'), ('res_pipe', 'lambda'), ('heat_exchanger', 'qext_w'),
                     ('res_heat_exchanger', 'v_mean_m_per_s'), ('res_heat_exchanger', 't_from_k'),
                     ('res_heat_exchanger', 't_to_k'), ('circ_pump_pressure', 't_flow_k'), ('res_junction', 't_k')]
    
    ow = OutputWriter(net, time_steps, output_path=None, log_variables=log_variables)

    run_time_series.run_timeseries(net, time_steps, mode="all")

    print("temperature:")
    print(ow.np_results["res_junction.t_k"])

    x = time_steps
    y1 = ow.np_results["res_heat_exchanger.t_from_k"]
    y2 = ow.np_results["res_heat_exchanger.t_to_k"]
    
    plt.xlabel("time step")
    plt.ylabel("temperature [K]")
    plt.title("temperature profile heat exchangers")
    plt.plot(x, y1[:,0], "g-o")
    plt.plot(x, y2[:,0], "b-o")
    plt.legend(["heat exchanger 1 from", "heat exchanger 1 to"], loc='lower left')
    plt.grid()
    plt.show()


net = initialize_net()
# net = initialize_test_net()
print(net.res_junction)
time_series_net(net)
