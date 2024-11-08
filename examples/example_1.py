from flow_pathing_example import Interpreter

if __name__ == '__main__':
    my_reactor_spec = """
    # Declaring some nodes and their volumes ahead of time
    Syringe_1:0, Syringe_2:0, Syringe_3:0
    line_a1:10, line_a2:20, line_a3:40
    line_b1:100, line_c1:200
    ftir:8

    # connections
    Syringe_1 > line_a1 > line_b1 > line_c1 > ftir
    Syringe_2 > line_a2 > line_b1
    Syringe_3 > line_a3 > line_c1
    """
    # The lines from syringes 1 and 2 meet, and their product then joins the line from syringe 3; this product then
    # proceeds to the FTIR (an analytical device).
    #
    # Visually:
    #
    # (Syringe_1)>--[line_a1]-->\
    #                           |>--[line_b1]-->\
    # (Syringe_2)>--[line_a2]-->/               |
    #                                           |>--[line_c1]-->(ftir)
    #                                           |
    # (Syringe_3)>--[line_a3]------------------>/
    #
    # Note that the T-junctions were not modeled in this example

    my_reactor = Interpreter().decode(my_reactor_spec)

    starting_at = my_reactor['Syringe_1']

    print(f"Starting at: {starting_at}")

    print(f"There are {starting_at.volume_to('ftir') - starting_at.volume} uL between Syringe_1 and the FTIR.")

    test_flow_rates = {'Syringe_1': 55, 'Syringe_2': 90, 'Syringe_3': 55}

    duration_syringes_to_ftir = my_reactor['ftir'].time_from(**test_flow_rates)

    print(f"FTIR will experience the new flow condition {duration_syringes_to_ftir} minutes "
          f"after the flow rates have been set to {test_flow_rates}")
