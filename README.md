# ConditionalGraph
A graph data structure where edges are conditionally traverasable.

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
When running, the system will from from the syringe, through the selector, and into the reactor (the reservoir is not involved).
For this system of a reservoir (R), selector valve (V), syringe pump (P), and reactor (X), I want to indicate:
R-->V-->P (when in refill mode) and P-->V-->X (when in running mode).

If one had two stream-diverting valve where the first can select left/right and the other can select left/right/center, then instead of naming all 6 possible configurations, one can instead specify that valve 1's state can have two values (left/right) and valve 2's state can have three values (left/right/center).
By individually setting each valve's state, all 6 configuations can be accessed.

The microfludic example also contains an interpreter for writting the connections consicely.

# Python Version
3.12 or greater

# Optimization
The current implementation is not optimized in memory, speed, or scalability.
Currently the implementation uses class attributes to handle states and book keep all the nodes.
This means that only one instance of the graph can exist at a time (within a scope of Python initializing class attributes) or else they will interfere with each other.
This implementation has no mutex for thread-stability.
