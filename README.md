# ConditionalGraph
A graph data structure where edges are conditionally traverasable.

# What is this meant to handle?
This data structure can represent roads (such as stoplights) or microfluidic reactors which have directing valves.
In these cases, multiple nodes may be physically connected, but their edges only traversable under some condition---red/green light or a valve directing left vs right.
While it is possible to make graphs for each case, but this may explode when the number of states increases (even 3 binary states could result in 8 graphs).
In this implementation, edges can be agnostic to state and edges are directional (though the direction can change between states).

# Example
Provided in addition to this repo is this data structure's original intended use: modeling a fluidic laboratory setup.
Consider a system where there is a reservoir of material, a selector valve, a syringe pump, and a reactor.
When refilling, the system will flow from the reservoir, through the selector, and into the syringe (the reactor is not involved).
When running, the system will from from the syringe, through the selector, and into the reactor (the reservoir is not involved).
For this system of a reservoir (R), selector valve (V), syringe pump (P), and reactor (X), I want to indicate:
R-->V-->P (when in refill mode) and P-->V-->X (when in running mode).

The microfludic example also contains an interpreter for writting the connections consicely.

# Python Version
3.12 or greater
