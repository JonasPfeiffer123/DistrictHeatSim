from pandapower.control.basic_controller import BasicCtrl
from math import pi

class WorstPointPressureController(BasicCtrl):
    def __init__(self, net, worst_point_idx, circ_pump_pressure_idx=0, target_dp_min_bar=1, tolerance=0.1, proportional_gain=0.2,**kwargs):
        super(WorstPointPressureController, self).__init__(net, **kwargs)
        self.heat_exchanger_idx = worst_point_idx
        self.flow_control_idx = worst_point_idx
        self.circ_pump_pressure_idx = circ_pump_pressure_idx
        self.target_dp_min_bar = target_dp_min_bar
        self.tolerance = tolerance
        self.proportional_gain = proportional_gain

    def time_step(self, net, time_step):
        return time_step

    def is_converged(self, net):
        qext_w = net.heat_exchanger["qext_w"].at[self.heat_exchanger_idx]
        if qext_w <= 250:
            #print("Da")
            # Wenn der Wärmestrom null ist, betrachte den Controller als nicht konvergiert
            return True
        current_dp_bar = net.res_flow_control["p_from_bar"].at[self.flow_control_idx] - net.res_heat_exchanger["p_to_bar"].at[self.heat_exchanger_idx]

        # check, if the temperature converged
        dp_within_tolerance = abs(current_dp_bar - self.target_dp_min_bar) < self.tolerance

        #print(f"WorstPointPressureController: is_converegd(), Wärmleistung: {qext_w}, aktuelles dp: {current_dp_bar}, Ziel erreicht: {dp_within_tolerance}")

        if dp_within_tolerance == True:
            return dp_within_tolerance
    
    def control_step(self, net):
        # Überprüfe, ob der Wärmestrom im Wärmeübertrager null ist
        qext_w = net.heat_exchanger["qext_w"].at[self.heat_exchanger_idx]
        if qext_w <= 250:
            #print("Hier")
            # Wenn der Wärmestrom null ist, führe keine Anpassungen durch
            return super(WorstPointPressureController, self).control_step(net)

        current_dp_bar = net.res_flow_control["p_from_bar"].at[self.flow_control_idx] - net.res_heat_exchanger["p_to_bar"].at[self.heat_exchanger_idx]
        dp_error = self.target_dp_min_bar - current_dp_bar

        current_plift_bar = net.circ_pump_pressure["plift_bar"].at[self.circ_pump_pressure_idx]
        current_pflow_bar = net.circ_pump_pressure["p_flow_bar"].at[self.circ_pump_pressure_idx]
        
        plift_adjustment = dp_error * self.proportional_gain
        pflow_adjustment = dp_error * self.proportional_gain        

        new_plift = current_plift_bar + plift_adjustment
        new_pflow = current_pflow_bar + pflow_adjustment
        
        net.circ_pump_pressure["plift_bar"].at[self.circ_pump_pressure_idx] = new_plift
        net.circ_pump_pressure["p_flow_bar"].at[self.circ_pump_pressure_idx] = new_pflow

        #print(self.target_dp_min_bar, current_dp_bar, current_plift_bar, current_pflow_bar, new_plift, new_pflow)
 
        return super(WorstPointPressureController, self).control_step(net)
    

class ReturnTemperatureController(BasicCtrl):
    def __init__(self, net, heat_exchanger_idx, target_temperature, tolerance=3, lower_proportional_gain=0.0005, higher_proportional_gain=0.003, min_velocity=0.005, max_velocity=2,**kwargs):
        super(ReturnTemperatureController, self).__init__(net, **kwargs)
        self.heat_exchanger_idx = heat_exchanger_idx
        self.flow_control_idx = heat_exchanger_idx
        self.target_temperature = target_temperature
        self.initial_target_temperature = target_temperature
        self.tolerance = tolerance
        self.lower_proportional_gain = lower_proportional_gain
        self.higher_proportional_gain = higher_proportional_gain

        self.min_mass_flow = min_velocity * ((pi/4)*(net.heat_exchanger["diameter_m"].at[heat_exchanger_idx] ** 2)) * 1000
        self.max_mass_flow = max_velocity * ((pi/4)*(net.heat_exchanger["diameter_m"].at[heat_exchanger_idx] ** 2)) * 1000

    def time_step(self, net, time_step):
        return time_step

    def is_converged(self, net):
        qext_w = net.heat_exchanger["qext_w"].at[self.heat_exchanger_idx]
        if qext_w <= 250:
            #print("Da2")
            # Wenn der Wärmestrom null ist, betrachte den Controller als nicht konvergiert
            return True
        current_temperature = net.res_heat_exchanger["t_to_k"].at[self.heat_exchanger_idx] - 273.15
        current_mass_flow = net.flow_control["controlled_mdot_kg_per_s"].at[self.flow_control_idx]

        # check, if min or max massflow are reached
        at_min_mass_flow = current_mass_flow < self.min_mass_flow
        at_max_mass_flow = current_mass_flow > self.max_mass_flow

        # check, if the temperature converged
        temperature_within_tolerance = abs(current_temperature - self.target_temperature) < self.tolerance

        #print(f"ReturnTemperatureController: is_converegd(), Wärmleistung: {qext_w}, aktuelle Temperatur: {current_temperature}, aktueller Massenstrom: {current_mass_flow}, Ziel erreicht: {temperature_within_tolerance}")

        if temperature_within_tolerance == False and at_max_mass_flow == True:
            self.target_temperature = current_temperature - 0.5
        
        if temperature_within_tolerance == False and at_min_mass_flow == True:
            self.target_temperature = current_temperature + 0.5

        if temperature_within_tolerance == True:
            self.target_temperature = self.initial_target_temperature
            return temperature_within_tolerance
    

    def control_step(self, net):
        # Überprüfe, ob der Wärmestrom im Wärmeübertrager null ist
        qext_w = net.heat_exchanger["qext_w"].at[self.heat_exchanger_idx]
        if qext_w <= 250:
            #print("Hier2")
            return super(ReturnTemperatureController, self).control_step(net)

        current_temperature = net.res_heat_exchanger["t_to_k"].at[self.heat_exchanger_idx] - 273.15
        temperature_error = self.target_temperature - current_temperature

        current_mass_flow = net.flow_control["controlled_mdot_kg_per_s"].at[self.flow_control_idx]

        if current_mass_flow <= 0.05:
            mass_flow_adjustment = temperature_error * self.lower_proportional_gain        
        if current_mass_flow > 0.05:
            mass_flow_adjustment = temperature_error * self.higher_proportional_gain

        new_mass_flow = current_mass_flow + mass_flow_adjustment
        new_mass_flow = max(self.min_mass_flow, min(new_mass_flow, self.max_mass_flow))
        
        net.flow_control["controlled_mdot_kg_per_s"].at[self.flow_control_idx] = new_mass_flow

        #print(self.target_temperature, current_temperature, current_mass_flow, new_mass_flow)
        
        return super(ReturnTemperatureController, self).control_step(net)