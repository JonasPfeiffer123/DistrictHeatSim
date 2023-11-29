import pandapipes as pp
import geopandas as gpd
from shapely.geometry import LineString

# Zugriff auf die Koordinaten jeder Linie
def get_line_coords_and_lengths(gdf):
    all_line_coords, all_line_lengths = [], []
    # Berechnung der Länge jeder Linie
    gdf['length'] = gdf.geometry.length
    for index, row in gdf.iterrows():
        line = row['geometry']
        
        # Überprüfen, ob die Geometrie ein LineString ist
        if line.geom_type == 'LineString':
            # Zugriff auf die Koordinatenpunkte
            coords = list(line.coords)
            length = row['length']
            all_line_coords.append(coords)
            all_line_lengths.append(length)
        else:
            print(f"Geometrie ist kein LineString: {line.type}")

    return all_line_coords, all_line_lengths


def get_all_point_coords_from_line_cords(all_line_coords):
    point_coords = [koordinate for paar in all_line_coords for koordinate in paar]
    # Entfernen von Duplikaten
    unique_point_coords = list(set(point_coords))
    return unique_point_coords


def create_network(gdf_vorlauf, gdf_rl, gdf_hast, gdf_wea, pipe_creation_mode="diameter"):
    def create_junctions_from_coords(net_i, all_coords):
        junction_dict = {}
        for i, coords in enumerate(all_coords, start=0):
            junction_id = pp.create_junction(net_i, pn_bar=1.05, tfluid_k=293.15, name=f"Junction {i}", geodata=coords)
            junction_dict[coords] = junction_id
        return junction_dict

    def create_pipes_diameter(net_i, all_line_coords, all_line_lengths, junction_dict, pipe_type, diameter_mm):
        for coords, length_m, i in zip(all_line_coords, all_line_lengths, range(0, len(all_line_coords))):
            pp.create_pipe_from_parameters(net_i, from_junction=junction_dict[coords[0]],
                                           to_junction=junction_dict[coords[1]], length_km=length_m/1000,
                                           diameter_m=diameter_mm/1000, k_mm=.1, alpha_w_per_m2k=10, name=f"{pipe_type} Pipe {i}",
                                           geodata=coords, sections=5, text_k=283)

    def create_pipes_type(net_i, all_line_coords, all_line_lengths, junction_dict, line_type, pipetype):
        for coords, length_m, i in zip(all_line_coords, all_line_lengths, range(0, len(all_line_coords))):
            pp.create_pipe(net_i, from_junction=junction_dict[coords[0]], to_junction=junction_dict[coords[1]],
                           std_type=pipetype, length_km=length_m/1000, k_mm=.1, alpha_w_per_m2k=10,
                           name=f"{line_type} Pipe {i}", geodata=coords, sections=5, text_k=283)

    def create_heat_exchangers(net_i, all_coords, q_heat_exchanger, junction_dict, name_prefix):
        for i, coords in enumerate(all_coords, start=0):
            pp.create_heat_exchanger(net_i, from_junction=junction_dict[coords[0]],
                                     to_junction=junction_dict[coords[1]], diameter_m=0.02, loss_coefficient=100,
                                     qext_w=q_heat_exchanger, name=f"{name_prefix} {i}")

    def create_circulation_pump_pressure(net_i, all_coords, junction_dict, name_prefix):
        for i, coords in enumerate(all_coords, start=0):
            pp.create_circ_pump_const_pressure(net_i, junction_dict[coords[1]], junction_dict[coords[0]],
                                               p_flow_bar=4, plift_bar=1.5, t_flow_k=273.15 + 90, type="auto",
                                               name=f"{name_prefix} {i}")

    net = pp.create_empty_network(fluid="water")

    # Verarbeiten von Vorlauf und Rücklauf
    junction_dict_vl = create_junctions_from_coords(net, get_all_point_coords_from_line_cords(
        get_line_coords_and_lengths(gdf_vorlauf)[0]))
    junction_dict_rl = create_junctions_from_coords(net, get_all_point_coords_from_line_cords(
        get_line_coords_and_lengths(gdf_rl)[0]))

    # Erstellen der Pipes
    if pipe_creation_mode == "diameter":
        diameter_mm = 100
        create_pipes_diameter(net, *get_line_coords_and_lengths(gdf_vorlauf), junction_dict_vl, "Vorlauf", diameter_mm)
        create_pipes_diameter(net, *get_line_coords_and_lengths(gdf_rl), junction_dict_rl, "Rücklauf", diameter_mm)

    if pipe_creation_mode == "type":
        pipetype = "110_PE_100_SDR_17"
        create_pipes_type(net, *get_line_coords_and_lengths(gdf_vorlauf), junction_dict_vl, "Vorlauf", pipetype)
        create_pipes_type(net, *get_line_coords_and_lengths(gdf_rl), junction_dict_rl, "Rücklauf", pipetype)

    # Erstellen der Heat Exchangers
    create_heat_exchangers(net, get_line_coords_and_lengths(gdf_hast)[0], 60000,
                           {**junction_dict_vl, **junction_dict_rl}, "HAST")

    # Erstellen der circulation pump pressure
    create_circulation_pump_pressure(net, get_line_coords_and_lengths(gdf_wea)[0], {**junction_dict_vl,
                                                                                    **junction_dict_rl}, "WEA")
    return net


def correct_flow_directions(net):
    # initiale Pipeflow-Berechnung
    pp.pipeflow(net, mode="all")

    # Überprüfen Sie die Geschwindigkeiten in jeder Pipe und tauschen Sie die Junctions bei Bedarf
    for pipe_idx in net.pipe.index:
        # Überprüfen Sie die mittlere Geschwindigkeit in der Pipe
        if net.res_pipe.v_mean_m_per_s[pipe_idx] < 0:
            # Tauschen Sie die Junctions
            from_junction = net.pipe.at[pipe_idx, 'from_junction']
            to_junction = net.pipe.at[pipe_idx, 'to_junction']
            net.pipe.at[pipe_idx, 'from_junction'] = to_junction
            net.pipe.at[pipe_idx, 'to_junction'] = from_junction

    # Führen Sie die Pipeflow-Berechnung erneut durch, um aktualisierte Ergebnisse zu erhalten
    pp.pipeflow(net, mode="all")

    return net


def optimize_diameter_parameters(initial_net, v_max=1, v_min=0.8, dx=0.001):
    pp.pipeflow(initial_net, mode="all")
    velocities = list(initial_net.res_pipe.v_mean_m_per_s)
    
    while max(velocities) > v_max or min(velocities) < v_min:
        for pipe_idx in initial_net.pipe.index:
            # Überprüfen Sie die mittlere Geschwindigkeit in der Pipe
            if initial_net.res_pipe.v_mean_m_per_s[pipe_idx] > v_max:
                # Durchmesser vergrößern
                initial_net.pipe.at[pipe_idx, 'diameter_m'] = initial_net.pipe.at[pipe_idx, 'diameter_m'] + dx
            elif initial_net.res_pipe.v_mean_m_per_s[pipe_idx] < v_min:
                # Durchmesser verkleinern
                initial_net.pipe.at[pipe_idx, 'diameter_m'] = initial_net.pipe.at[pipe_idx, 'diameter_m'] - dx
        pp.pipeflow(initial_net, mode="all")
        velocities = list(initial_net.res_pipe.v_mean_m_per_s)

    return initial_net

def optimize_diameter_types(net, v_max=1.1, v_min=0.7):
    pp.pipeflow(net, mode="all")
    velocities = list(net.res_pipe.v_mean_m_per_s)

    # Auflisten aller verfügbaren Standardtypen für Rohre
    pipe_std_types = pp.std_types.available_std_types(net, "pipe")
    # Filtern nach einem bestimmten Material, z.B. "PE 100"
    filtered_pipe_types = pipe_std_types[pipe_std_types['material'] == 'PE 100']

    # Erstellen eines Dictionarys, das die Position jedes Rohrtyps im gefilterten DataFrame enthält
    type_position_dict = {type_name: i for i, type_name in enumerate(filtered_pipe_types.index)}
    
    while any(v > v_max or v < v_min for v in net.res_pipe.v_mean_m_per_s):
        for pipe_idx, velocity in enumerate(net.res_pipe.v_mean_m_per_s):
            current_type = net.pipe.std_type.at[pipe_idx]
            current_type_position = type_position_dict[current_type]

            if velocity > v_max and current_type_position > 0:
                 # Aktualisieren Sie den Rohrtyp auf den vorherigen Typ
                new_type = filtered_pipe_types.index[current_type_position + 1]
                net.pipe.std_type.at[pipe_idx] = new_type
                # Aktualisieren Sie die Eigenschaften des Rohres
                properties = filtered_pipe_types.loc[new_type]
                net.pipe.at[pipe_idx, 'diameter_m'] = properties['inner_diameter_mm'] / 1000

            elif velocity < v_min and current_type_position < len(filtered_pipe_types) - 1:
                # Aktualisieren Sie den Rohrtyp auf den nächsten Typ
                new_type = filtered_pipe_types.index[current_type_position - 1]
                net.pipe.std_type.at[pipe_idx] = new_type
                # Aktualisieren Sie die Eigenschaften des Rohres
                properties = filtered_pipe_types.loc[new_type]
                net.pipe.at[pipe_idx, 'diameter_m'] = properties['inner_diameter_mm'] / 1000
                
        pp.pipeflow(net, mode="all")
        velocities = list(net.res_pipe.v_mean_m_per_s)

    return net

def export_net_geojson(net):
    # Prüfen, ob geographische Daten vorhanden sind
    if 'pipe_geodata' in net and not net.pipe_geodata.empty:
        # Konvertieren der Rohrdaten in ein GeoDataFrame
        gdf = gpd.GeoDataFrame(net.pipe_geodata)
        gdf['geometry'] = gdf['coords'].apply(lambda x: LineString(x))
        del gdf['coords']  # Entfernen Sie die ursprüngliche Koordinatenspalte

        # Hinzufügen zusätzlicher Eigenschaften wie 'diameter_m'
        gdf['diameter_mm'] = net.pipe['diameter_m'] / 1000
    
        # Setzen Sie das Koordinatensystem, falls bekannt (hier beispielhaft EPSG:4326)
        gdf.set_crs(epsg=25833, inplace=True)

        # Exportieren als GeoJSON
        gdf.to_file("pipes_network.geojson", driver='GeoJSON')
    else:
        print("Keine geographischen Daten im Netzwerk vorhanden.")
