# ConditionalGraph
A graph data structure where edges are conditionally traversable.

# What is this meant to handle?
This data structure can represent roads (such as stoplights) or microfluidic reactors which have directing valves.
In these cases, multiple nodes may be physically connected, but their edges only traversable under some condition---red/green light or a valve directing left vs right.
While it is possible to make graphs for each case, this may explode when the number of states increases (even 3 binary states could result in 8 graphs).
In this implementation, edges are directional (though the direction can change between states), and it is possible to define an edge as agnostic to state.
Furthermore, states can be grouped by name to simplify the convolution of multiple state-ful junctions.
The graph will allow all combinations of these states.

# Example
Provided in addition to this repo is this data structure's original intended use: modeling a fluidic laboratory setup.
Consider a system where there is a reservoir of material, a selector valve, a syringe pump, and a reactor.
When refilling, the system will flow from the reservoir, through the selector, and into the syringe (the reactor is not involved).
When running, the system will flow from the syringe, through the selector, and into the reactor (the reservoir is not involved).
For this system of a reservoir (R), selector valve (V), syringe pump (P), and reactor (X), I want to indicate:
R-->V-->P (when in refill mode) and P-->V-->X (when in running mode).

If one had two stream-diverting valve where the first can select left/right and the other can select left/right/center, then instead of naming all 6 possible configurations, one can instead specify that valve 1's state can have two values (left/right) and valve 2's state can have three values (left/right/center).
By individually setting each valve's state, all 6 configurations  can be accessed.

The microfluidic example also contains an interpreter for writing the connections concisely.

# Python Version
3.12 or greater

# Optimization
The current implementation is not optimized in memory, speed, or scalability.
Currently the implementation uses class attributes to handle states and book keep all the nodes.
This means that only one instance of the graph can exist at a time (within a scope of Python initializing class attributes) or else they will interfere with each other.
This implementation has no mutex for thread-stability.

# Serialization
Given the original application of this data structure being mapping flow systems so that dead-times can be calculated between devices, a way to encode the flow path in a more human-accessible way was developed.
Currently, the conversion is one-way (string to graph).

The syntax uses the following tokens:

- Connects to: " > ".  Whitespace is required.  Indicates a directional connection between nodes.  "Segment > Segment (> Segment (> ...))"
- Detail: ":".  For segments, the detail separates the segment name from its volume; "tube:50".  For constraints, the detail separates the state name from the state value; "selector:left".
- Constraint (1): " | ".  Whitespace is required.  Separates connections from constraints.  Indicates that the (last) connection on the line is subject to a constraint(s).
- Constraint (2): " || ".  Whitespace is required.  Separates connections from constraints.  Indicates that all connections on the line are subject to a constraint(s).
- Separator: ",".  Used to separate multiple elements (nodes, constraints) on a given line.
- Comment: "#".  Everything to the right will be ignored by the interpreter

These token separate or are part of various Words:

- A Segment is any object, tube, or device which has a volume (can be 0) and through which material flows.  They are addressed "name(:volume)".

  - Segments can be declared and initialized independently; and multiple can be declared and initialized on the same line.
  - The volume of each Segment only needs to be initialized once (it doesn't have to be the first time);
    multiple initializations will use the FIRST value.
  - Devices which alter flow (selector valves, 6-way valve, etc.) should not be modeled by explicit Segments,
    constrained connections between tubes can be implicitly define such devices.

- A Connection is any pair or group of Segments connected by the "connects to" token (" > ").  They are addressed "Segment > Segment (> Segment (> ...))".

- A Constraint is any requirement that a state have a given value.  They are addressed "state_id:state_name(, state_id:state_name(, ...))"

  - A constraint cannot occur on its own line, it must occur with an associated Connection(s).
  - Constrained_Connection: "Connection | Constraint".  The Constraint(s) will apply to the LAST connection.
  - Constrained_Connection: "Connection || Constraint".  The Constraint(s) will apply to ALL connections.

- A Comment is an annotation for human readability.  They are prefixed with the "#" symbol.

  - A comment may occur on its own line or follow at the end of a line 

In addition, whitespace and excess newlines are generally ignored, except for the ">", "|", and "||" tokens,
which must be surrounded on both sides by at least one space.

# Example serialization
The following is how a selector valve could connect multiple reagent bottoms to a single syringe and connect the syringe to the rest of the system (the mixers, reactor, analyzers, etc.).
The bottles are named "Bottle\_#".  The tubes connecting the bottles to the selector are named "bottle\_#\_rselect\_1".  The syringe is named "RSyr\_1". The tube between the selector and the syringe is named "rselect\_1\_rsyr\_1".  The tube connecting the selector to the rest of the system (System) is named "rselect\_1\_system".  The selector's valid sates are grouped under the name "rselect\_1" and can have the values "drive" (when flowing from the syringe to the system) and "refill\_#" where "#" is the number of the corresponding bottle being refilled from.

""" \
Bottle_1 > bottle_1_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_1 \
Bottle_2 > bottle_2_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_2 \
Bottle_3 > bottle_3_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_3 \
#...and so on, were there more bottles... \
rselect_1_rsyr_1 > RSyr_1 | rselect_1:refill_1, rselect_1:refill_2, rselect_1:refill_3 \
RSyr_1 > rselect_1_rsyr_1 > rselect_1_system || rselect_1:drive \
rselect_1_system > System \
"""
