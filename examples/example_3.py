from flow_pathing_example import Interpreter, Segment, print_path, Direction
from typing import Callable


if __name__ == '__main__':
    my_reactor_spec = """
    # Declaring nodes and their volumes ahead of time
    Bottle_1:0, Bottle_2:0, Syringe:50
    # Selector:0 (see note below)
    Reactor:750, Waste:0
    b1_to_sel:150, b2_to_sel:100, syr_to_sel:125
    # alt. "b1->sel:150, b2->sel:100, syr<>sel:125" (see comment below)
    sel_to_rxtr:200, rxtr_to_waste:75
    
    # On the absence of a "Selector" in the declarations.  Generally, it's not needed.  The states control what
    # connects to what, so explicit modeling of a Selector is unnecessary.  It is also poorly defined (unless a
    # binary, left/right, selector is used) as specifying connectivity with multiple inputs and a multiple outputs
    # on a single object is difficult to resolve.  If the dead volume of the selector is a critical factor, the
    # the connections between ports can be modeled explicitly.
    
    # The "b1_to_sel" notation is nice for readability and avoiding confusion with the " > " token which means 
    # "connects to".  But in cases like "syr_to_sel" which are bidirectional, the use of "to" implies the wrong
    # directionality.  So the "->" and "<>" notation can help make that explicit.  The interpreter looks for 
    # spaces around the ">" symbol so using "a->b" will not confuse the interpreter.
    
    # Note about the states (name or group : value)
    # Below three state values are used: "refill_1", "refill_2", and "infuse".  These states are grouped under the
    # parent state name "selector".  In this sense, when the Selector is in "refill_1", it means the selector connects
    # the Syringe to Bottle_1, similarly "refill_2" connects the Syringe to Bottle_2.  When the Selector is in "infuse",
    # it means the Syringe is connected to the Reactor.
    # By naming/grouping states around their physical devices it allows for the convolution of multiple states.  This
    # will be explored more in example 4 where there are two selector valves (one for selecting a reagent, like this
    # example, and one for bypassing the reactor).
    
    # Defining the connections
    Bottle_1 > b1_to_sel
    Bottle_2 > b2_to_sel
    
    b1_to_sel > sel_to_syr | selector:refill_1  # Only when the selector state has a value of refill_1 are these two
                                                # fluid lines connected in this way.
    b2_to_sel > sel_to_syr | selector:refill_2
    sel_to_syr > sel_to_rxtr | selector:infuse  
    
    sel_to_syr > Syringe | selector:refill_1, selector:refill_2  # The sel_to_syr tube connects to the Syringe in
                                                                 # either (both) of these cases.
    Syringe > sel_to_syr | selector:infuse                       # Conversely, the Syringe connects to the sel_to_syr 
                                                                 # tube in the infuse case.
    
    sel_to_rxtr > Reactor > rxtr_to_waste > Waste
    """
    # Drawing of the system as described
    #
    #  (Syringe)===[sel_to_syr]=======\
    #                                 |
    #  (Bottle_1)>--[b1_to_sel]-->(Selector)<--[b2_to_sel]--<(Bottle_2)
    #                                 v
    #                                 |
    #                                 \--[sel_to_rxtr]-->(Reactor)>--[rxtr_to_waste]-->(Waste)

    my_reactor = Interpreter().decode(my_reactor_spec)

    # How long will it take for fluid from Bottle 1 to reach the Syringe?
    starting_at = my_reactor['Bottle_1']
    test_state = "refill_1"
    starting_at.set_state("selector", test_state)  # Grab *any* node to set a state
    volume_between = starting_at.volume_to("Syringe")
    print(f"In the '{test_state}' state, there are {volume_between} uL between Bottle_1 and Syringe")

    # What about a different state?
    test_state = "refill_2"
    starting_at.set_state("selector", test_state)
    volume_between = starting_at.volume_to("Syringe")  # The search returns None if it fails
    print(f"In the '{test_state}' state, there are {volume_between} uL between Bottle_1 and Syringe")

    print("\n====\n")

    # How many paths to the Reactor?
    starting_at.set_state("selector", "refill_1")  # <-- try other states
    # Ultimately there should only be one path to the Reactor in each state.
    #   When infusing: Syringe > ... > Reactor
    #   When refilling: sel_to_rxtr > Reactor

    my_condition: Callable[[Segment], bool] = lambda n: not n.has_parents()
    starting_at = my_reactor['Reactor']
    counter = 0
    direction = Direction.UP
    for result, result_path in starting_at.traverse(my_condition, direction=direction):
        print(f"Path #{counter}")
        print("\t", print_path(reversed(result_path)))  # reversed because the search direction is "UP"
        volume_between = starting_at.volume_to(result.name, direction=direction)
        print(f"\tThis path is {volume_between} (volume units) long")
        counter += 1

    print("\n====\n")

    # Some search features have the ability to ignore the state value
    # However, they should be used carefully when the direction of flow can change in a segment for different states.
    # Consider how in this example the search will provide the path:
    # "[sel_to_syr]-->[sel_to_rxtr]" which would require back-tracking through the sel_to_syr tube.
    starting_at.set_state("selector", "infuse")
    my_condition: Callable[[Segment], bool] = lambda n: not n.has_parents(ignore_state=True)
    starting_at = my_reactor['Reactor']
    counter = 0
    direction = Direction.UP
    for result, result_path in starting_at.traverse(my_condition, direction=direction, ignore_state=True):
        print(f"Path #{counter}")
        print("\t", print_path(reversed(result_path)))
        volume_between = starting_at.volume_to(result.name, direction=direction)
        print(f"\tThis path is {volume_between} (volume units) long")
        counter += 1
