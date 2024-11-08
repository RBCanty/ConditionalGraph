from flow_pathing_example import Interpreter, Segment, print_path, Direction
from typing import Callable


if __name__ == '__main__':
    my_reactor_spec = """
    # Declaring some nodes and their volumes ahead of time
    Syringe_1:1000, Syringe_2:2000, Syringe_3:4000
    line_a1:10, line_a2:20, line_a3:40
    joiner_b:1, joiner_c:2
    line_b1:100, line_c1:200
    ftir:8

    # connections
    Syringe_1 > line_a1 > joiner_b > line_b1 > joiner_c > line_c1 > ftir
    Syringe_2 > line_a2 > joiner_b
    Syringe_3 > line_a3 > joiner_c
    """
    # The lines from syringes 1 and 2 meet, and their product then joins the line from syringe 3; this product then
    # proceeds to the FTIR (an analytical device).
    #
    # Visually:
    #
    # (Syringe_1)>--[line_a1]-->\
    #                           |joiner_b|>--[line_b1]-->\
    # (Syringe_2)>--[line_a2]-->/                        |
    #                                                    |joiner_c|>--[line_c1]-->(ftir)
    #                                                    |
    # (Syringe_3)>--[line_a3]--------------------------->/

    my_reactor = Interpreter().decode(my_reactor_spec)

    # To find paths from a Syringe to the ftir
    starting_at = my_reactor['ftir']
    my_condition: Callable[[Segment], bool] = lambda n: "Syringe" in n.name

    counter = 0
    for result, result_path in starting_at.traverse(my_condition, direction=Direction.UP):
        print(f"Path #{counter}")
        print("\t", print_path(result_path))
        volume_between_start_and_end = starting_at.volume_to(result.name, direction=Direction.UP)
        print(f"\tThis path is {volume_between_start_and_end} (volume units) long")
        counter += 1

    # Inspect junctions for flow rates that exceed 10:1 (that could cause flow instability)
    print("\n====\n")
    test_flow_rates = {'Syringe_1': 55, 'Syringe_2': 90, 'Syringe_3': 55}
    points_of_instability, worst_ratio = my_reactor['ftir'].check_flow_stability_from(**test_flow_rates)
    print(f"The worst ratio of incoming volumetric flow rates observed was: {round(worst_ratio, 1)}:1")
    print(f"All junctions where said ratio was above 10:1 are: {points_of_instability}")
