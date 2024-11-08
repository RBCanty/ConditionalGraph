from flow_pathing_example import Interpreter, Segment, print_path, Direction
from typing import Callable


if __name__ == '__main__':
    my_reactor_spec = """
    # Declaring some nodes and their volumes ahead of time
    #   (Purposefully being messy and leaving some declarations out)
    Syringe_1:0, Reactor:700, Syringe_2:0, Pump:0,Joiner:2 , Waste,,  ,,
    sel<>syr:100,  sel->vlv:50, vlv->rxt:80, vlv1->jnr:64, syr->vlv:400, vlv2->jnr:80, pmp->vlv:300
    rxt->jnr:2, jnr->wst:500

    # Bottles to the main syringe in the refilling state
    Bottle_1:0  > bot1->sel:4    > sel<>syr  | selector_1:refill_1  # Constraint only applies to bot1->sel:4 > sel<>syr
    Bottle_2:0  > bot2->sel:4.1  > sel<>syr  | selector_1:refill_2
    Bottle_3:0  > bot3->sel:4.2  > sel<>syr  | selector_1:refill_3
    sel<>syr    > Syringe_1                  | selector_1:refill_1, selector_1:refill_2, selector_1:refill_3

    # Main syringe to the 6-Port valve
    Syringe_1  > sel<>syr  > sel->vlv  || selector_1:drive  # Constraint applies to both connections

    # Main fluid line through the 6-Port valve
    sel->vlv   > vlv->rxt                        | valve_1:through
    sel->vlv   > vlv1->jnr                       | valve_1:bypass
    vlv->rxt   > Reactor    > rxt->jnr > Joiner
    vlv1->jnr  > Joiner

    # Diluter syringe to the 6-Port valve
    Syringe_2  > syr->vlv  > vlv2->jnr  | valve_1:through
                 syr->vlv  > vlv->rxt   | valve_1:bypass
    vlv2->jnr  > Joiner

    # Wash pump to the 6-Port valve
    Pump  > pmp->vlv  > vlv1->jnr  | valve_1:through
            pmp->vlv  > vlv2->jnr  | valve_1:bypass

    # Take us out
    Joiner  > jnr->wst  > Waste
    """

    my_reactor = Interpreter().decode(my_reactor_spec)

    bottle = my_reactor['Bottle_2']
    bottle.set_state('valve_1', 'through')
    bottle.set_state("selector_1", "drive")

    starting_at = my_reactor['Syringe_1']

    print("\n====\n\n")

    my_condition: Callable[[Segment], bool] = lambda n: n.name == "Waste"

    # If instead we wanted terminal/initial nodes
    # my_condition: Callable[[Segment], bool] = lambda n: (not n.has_children(True)) or (not n.has_parents(True))
    # and set direction to BOTH

    counter = 0
    direction = Direction.DOWN
    for result, result_path in starting_at.traverse(my_condition, direction=direction):
        print(f"Path #{counter}")
        print("\t", print_path(result_path))
        volume_between_start_and_end = starting_at.volume_to(result.name, direction=direction)
        print(f"\tThis path is {volume_between_start_and_end} (volume units) long")
        counter += 1

    print("\n====\n")

    test_flow_rates = {'Syringe_1': 55, 'Syringe_2': 90, 'Pump': 55}
    print(my_reactor['Reactor'].time_from(**test_flow_rates))
    print(my_reactor['Reactor'].check_flow_stability_from(**test_flow_rates))
