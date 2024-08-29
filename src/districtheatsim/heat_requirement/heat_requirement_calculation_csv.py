"""
Filename: heat_requirement_calculation_csv.py
Author: Dipl.-Ing. (FH) Jonas Pfeiffer
Date: 2024-07-31
Description: Contains the functions for calculating the heating demand for given buildings.
"""

import numpy as np
from heat_requirement import heat_requirement_VDI4655, heat_requirement_BDEW

def generate_profiles_from_csv(data, TRY, calc_method="Datensatz", ww_demand=0.2, subtyp="03", min_air_temperature=-12.0):
    """
    Generate heating profiles from CSV data.

    Args:
        data (DataFrame): Input data containing building information.
        TRY (str): Path to the TRY data file.
        calc_method (str, optional): Calculation method to use. Defaults to "Datensatz".
        ww_demand (float, optional): Warm water demand as a fraction. Defaults to 0.2.
        subtyp (str, optional): Building subtype. Defaults to "03".
        min_air_temperature (float, optional): Minimum air temperature. Defaults to -12.0.

    Returns:
        tuple: Generated profiles including yearly time steps, total heat, heating heat, warm water heat,
               max heat requirement, supply temperature curve, return temperature curve, and hourly air temperatures.
    """
    try:
        YEU_total_heat_kWh = data["Wärmebedarf"].values.astype(float)
        building_type = data["Gebäudetyp"].values.astype(str)
        subtyp = data["Subtyp"].values.astype(str)
        ww_demand = data["WW_Anteil"].values.astype(float)
        min_air_temperature = data["Normaußentemperatur"].values.astype(float)
    except KeyError:
        print("Unable to read data from CSV.")
        return None

    total_heat_W = []
    heating_heat_W = []
    warmwater_heat_W = []
    max_heat_requirement_W = []
    yearly_time_steps = None

    building_type_to_method = {
        "EFH": "VDI4655",
        "MFH": "VDI4655",
        "HEF": "BDEW",
        "HMF": "BDEW",
        "GKO": "BDEW",
        "GHA": "BDEW",
        "GMK": "BDEW",
        "GBD": "BDEW",
        "GBH": "BDEW",
        "GWA": "BDEW",
        "GGA": "BDEW",
        "GBA": "BDEW",
        "GGB": "BDEW",
        "GPD": "BDEW",
        "GMF": "BDEW",
        "GHD": "BDEW",
    }

    for idx, YEU in enumerate(YEU_total_heat_kWh):
        if calc_method == "Datensatz":
            try:
                current_building_type = str(data.at[idx, "Gebäudetyp"])
                current_subtype = str(data.at[idx, "Subtyp"])
                current_ww_demand = float(data.at[idx, "WW_Anteil"])
                current_calc_method = building_type_to_method.get(current_building_type, "StandardMethode")
            except KeyError:
                print("Building type column not found in CSV.")
                current_calc_method = "StandardMethode"
        else:
            current_building_type = building_type
            current_calc_method = calc_method

        if current_calc_method == "VDI4655":
            YEU_heating_kWh, YEU_hot_water_kWh = YEU_total_heat_kWh * (1-ww_demand), YEU_total_heat_kWh * ww_demand
            heating, hot_water = YEU_heating_kWh[idx], YEU_hot_water_kWh[idx]
            yearly_time_steps, hourly_heat_demand_total_kW, hourly_heat_demand_heating_kW, hourly_heat_demand_warmwater_kW, hourly_air_temperatures, electricity_kW = heat_requirement_VDI4655.calculate(heating, hot_water, building_type=current_building_type, TRY=TRY)

        elif current_calc_method == "BDEW":
            yearly_time_steps, hourly_heat_demand_total_kW, hourly_heat_demand_heating_kW, hourly_heat_demand_warmwater_kW, hourly_air_temperatures = heat_requirement_BDEW.calculate(YEU_kWh=YEU, building_type=current_building_type, subtyp=current_subtype, TRY=TRY, real_ww_share=current_ww_demand)

        hourly_heat_demand_total_kW = np.where(hourly_heat_demand_total_kW < 0, 0, hourly_heat_demand_total_kW)
        hourly_heat_demand_heating_kW = np.where(hourly_heat_demand_heating_kW < 0, 0, hourly_heat_demand_heating_kW)
        hourly_heat_demand_warmwater_kW = np.where(hourly_heat_demand_warmwater_kW < 0, 0, hourly_heat_demand_warmwater_kW)

        total_heat_W.append(hourly_heat_demand_total_kW * 1000)
        heating_heat_W.append(hourly_heat_demand_heating_kW * 1000)
        warmwater_heat_W.append(hourly_heat_demand_warmwater_kW * 1000)
        max_heat_requirement_W.append(np.max(hourly_heat_demand_total_kW * 1000))

    total_heat_W = np.array(total_heat_W)
    heating_heat_W = np.array(heating_heat_W)
    warmwater_heat_W = np.array(warmwater_heat_W)
    max_heat_requirement_W = np.array(max_heat_requirement_W)

    supply_temperature_curve, return_temperature_curve = calculate_temperature_curves(data, hourly_air_temperatures)

    return yearly_time_steps, total_heat_W, heating_heat_W, warmwater_heat_W, max_heat_requirement_W, supply_temperature_curve, return_temperature_curve, hourly_air_temperatures

def calculate_temperature_curves(data, hourly_air_temperatures):
    """
    Calculate the supply and return temperature curves for buildings.

    Args:
        data (DataFrame): Input data containing building information.
        hourly_air_temperatures (array): Array of hourly air temperatures.

    Returns:
        tuple: Supply temperature curve and return temperature curve arrays.
    """
    supply_temperature_buildings = data["VLT_max"].values.astype(float)
    return_temperature_buildings = data["RLT_max"].values.astype(float)
    slope = -data["Steigung_Heizkurve"].values.astype(float)
    supply_temperature_curve = []
    return_temperature_curve = []

    dT = np.expand_dims(supply_temperature_buildings - return_temperature_buildings, axis=1)
    min_air_temperatures = data["Normaußentemperatur"].values.astype(float)

    for st, s, min_air_temperature in zip(supply_temperature_buildings, slope, min_air_temperatures):
        st_curve = np.where(hourly_air_temperatures <= min_air_temperature, st, st + (s * (hourly_air_temperatures - min_air_temperature)))
        supply_temperature_curve.append(st_curve)

    supply_temperature_curve = np.array(supply_temperature_curve)
    return_temperature_curve = supply_temperature_curve - dT

    return supply_temperature_curve, return_temperature_curve