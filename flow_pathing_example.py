from types import SimpleNamespace
from typing import Self, Iterable, Literal, Callable

from abstractions import GenericStatefulGraph, CONSISTENT, Direction


class Minutes(float):
    @property
    def as_seconds(self):
        return self / 60


class Volume:
    def __init__(self, name: str, volume: float):
        self.name = name
        self.volume = volume
        self._flow_rate = 0.0

    def __repr__(self):
        return f"Volume('{self.name}', {self.volume})"

    def __str__(self):
        return f"{self.name} ({self.volume} uL)"


class Segment(GenericStatefulGraph[Volume]):
    _nodes: dict[str, Self] = {}

    def __init__(self, name: str, volume: float):
        super().__init__(Volume(name, volume))

    @property
    def name(self):
        return self.data.name

    @property
    def volume(self):
        return self.data.volume

    @property
    def flow_rate(self):
        return self.data._flow_rate  # noqa

    @property
    def duration(self) -> Minutes:
        if self.flow_rate < 1e-5:
            return Minutes(0)
        return Minutes(self.volume / self.flow_rate)

    @property
    def all_nodes(self):
        return self._nodes.values()

    def _add_child(self, child: Self, component_state_id: str, state_name: str):
        super()._add_child(child, component_state_id, state_name)
        self._nodes.setdefault(child.name, child)

    def _add_parent(self, parent: Self, component_state_id: str, state_name: str):
        super()._add_parent(parent, component_state_id, state_name)
        self._nodes.setdefault(parent.name, parent)

    def __str__(self):
        header = f"{self.name} ({self.volume} uL)"
        st = 2 * " "
        dt = 4 * " "
        tt = 6 * " "

        _states = [CONSISTENT, ] + [_k for _k in self._connections.keys() if _k != CONSISTENT]
        body = ""
        for _s in _states:
            if not (self._connections[_s].children or self._connections[_s].parents):
                continue
            body += f"{st}State:{_s}\n"

            if self._connections[_s].children:
                body += f"{dt}Children\n"
            for child in self._connections[_s].children:
                body += f"{tt}{child.name}\n"

            if self._connections[_s].parents:
                body += f"{dt}Parents\n"
            for parent in self._connections[_s].parents:
                body += f"{tt}{parent.name}\n"

        return f"{header}\n{body}"

    def volume_to(self, target_name: str, direction: Direction = Direction.DOWN) -> float | None:
        """ Calculates the cumulative volume from the current node to the target (does not include the volume of the
         final node). """
        traversals = self.traverse(lambda n: n.name == target_name, direction=direction)
        if not traversals:
            return None
        (final, path), *other = traversals
        if other:
            raise RuntimeError(f"Multiple paths to target {target_name} from {self.name}: "
                               f"{[_p for _, _p in traversals]}")
        volume = 0.0
        for segment in path:  # type: Segment
            volume += segment.volume

        return volume - final.volume

    def duration_to(self, target_name: str, direction: Direction = Direction.DOWN) -> Minutes | None:
        """ Calculates the longest duration from the current node to the target (does not include the volume of the
         final node).  Requires having first set flow rates for sources.
        """
        traversals = self.traverse(lambda n: n.name == target_name, direction=direction)
        if not traversals:
            return None
        (final, path), *other = traversals
        if other:
            raise RuntimeError(f"Multiple paths to target {target_name} from {self.name}: "
                               f"{[_p for _, _p in traversals]}")
        duration = Minutes(0)
        # print(f"Inspecting: {print_path(path)}")
        for segment in path:  # type: Segment
            duration += segment.duration
        # print(f"\tDuration = {duration - final.duration}")

        return duration - final.duration

    def reset_flow_rates(self):
        for rfr_segment in self._nodes.values():
            rfr_segment.data._flow_rate = 0.0

    def _build_flow_rates_between(self,
                                  target_name: str,
                                  **src_flow_rates: float
                                  ) -> tuple[set[Self], list[list[Self]]]:
        if target_name not in self._nodes:
            raise LookupError(f"Target '{target_name}' not found!")

        self.reset_flow_rates()

        for source_name, source_flow_rate in src_flow_rates.items():
            source: Segment = self._nodes.get(source_name, None)
            if source is None:
                continue
            source.data._flow_rate = source_flow_rate

        path_elements: dict[str, SimpleNamespace[Segment, bool]] = {}
        valid_sources: set[Segment] = set()
        valid_paths: list[list[Segment]] = []

        for source_name in src_flow_rates.keys():
            source: Segment = self._nodes.get(source_name, None)
            if source is None:
                continue
            traversals = source.traverse(lambda n: n.name == target_name)
            if not traversals:
                continue
            (_, path), *other = traversals
            if other:
                raise RuntimeError(f"Multiple paths to target {target_name} from {source.name}: "
                                   f"{[_p for _, _p in traversals]}")
            valid_sources.add(source)
            valid_paths.append(path)
            for segment in path:  # type: Segment
                if segment.name == target_name or segment.name in src_flow_rates.keys():
                    continue
                path_elements.setdefault(segment.name, SimpleNamespace(seg=segment, updated=False))

        first_pass = True  # Python, give me a do-while, please
        _iterations = 0
        while first_pass or any([_rec.updated for _rec in path_elements.values()]):
            first_pass = False
            for _rec in path_elements.values():
                segment: Segment = _rec.seg
                old_value = segment.flow_rate
                new_value = sum([_seg.flow_rate for _seg in segment.connections().parents], start=0.0)
                if old_value != new_value:
                    segment.data._flow_rate = new_value
                    _rec.updated = True
                else:
                    _rec.updated = False
            _iterations += 1
            if _iterations > 1000:
                raise TimeoutError(f"Flow rates failed to converge")

        return valid_sources, valid_paths

    def time_from(self, **src_flow_rates: float) -> Minutes | None:
        """ Calculates the time required for the current Node to receive the updated flow conditions from the sources
         specified in src_flow_rates. """
        try:
            valid_sources, _ = self._build_flow_rates_between(self.name, **src_flow_rates)
        except LookupError:
            return None

        durations = max([source.duration_to(self.name) for source in valid_sources], default=Minutes(0))

        self.reset_flow_rates()

        return durations

    def check_flow_stability_from(self,
                                  critical_flow_ratio=10.0,
                                  **src_flow_rates: float
                                  ) -> tuple[set[str], float] | None:
        """ Inspects nodes with >1 parent for the ratio of volumetric flow rates.  Provides a set of all Nodes
         with ratios exceeding this ratio and the worst (largest) ratio observed. """
        try:
            _, paths = self._build_flow_rates_between(self.name, **src_flow_rates)
        except LookupError:
            return None

        unstable_segments: set[str] = set()
        largest_ratio = float('-Inf')

        for path in paths:
            for segment in path:
                inlet_rates = [_p.flow_rate for _p in segment.connections().parents if _p.flow_rate > 0]
                if not inlet_rates:
                    continue
                flow_ratio = max(inlet_rates) / min(inlet_rates)
                largest_ratio = max(largest_ratio, flow_ratio)
                if flow_ratio > critical_flow_ratio:
                    unstable_segments.add(segment.name)

        self.reset_flow_rates()

        return unstable_segments, largest_ratio


class Interpreter:
    """
    Converts strings into Segment-graphs of the fluidic system.  Also contains helper methods for generating said
    strings.

    Syntax (tokens: " > ", ":", " | ", " || ", comma, and "#"):

    - Node: "name(:volume)"

      - Nodes will be implied by connections, so it is not necessary to define all Nodes before defining connections.
      - The volume of each Node only needs to be initialized once (and it doesn't have to be the first time either);
        multiple initializations will use the FIRST value.
      - A line(s) with comma-separated Node declarations can be used to specify nodes and their volumes so that in the
        subsequent lines that describe the connections between Nodes space is not used defining volume.
      - The helper methods will follow a convention where tubes are lowercase and other Nodes are uppercase.
      - Devices which alter flow (selector valves, 6-way valve, etc.) should not be modeled by explicit Nodes,
        constrained connections between tubes can be implicitly define such devices.

        - "tube_a > Selector > tube_b || selector:sel_left" & "tube_a > Selector > tube_c || selector:sel_right", and
        - "tube_a > tube_b | selector:sel_left" & "tube_a > tube_c | selector:sel_right" are functionally equivalent for
          a binary switcher.  2N-Way valves would then be modeled by 2N binary switchers, which isn't great.
        - The explicit Selector approach allows for encoding the dead-volume of the Selector (which is often negligible)

    - Connection: "Node > Node (> Node (> ...))"
    - Constraint: "state_id:state_name(, state_id:state_name(, ...)"

      - A constraint cannot occur on its own line.

    - Constrained_Connection: "Connection | Constraint"

      - The Constraint(s) will apply to the LAST connection.

    - Constrained_Connection: "Connection || Constraint"

      - The Constraint(s) will apply to ALL connections.

    - Comment: "# comment"

      - Anything after a "#" will be ignored.

    - Whitespace: Whitespace and excess newlines are generally ignored, except for the ">", "|", and "||" tokens,
      which must be surrounded on both sides by at least one space.
    """

    connects_to = " > "
    details = ":"
    provided_final = " | "
    provided_all = " || "
    comment = "#"

    class SkipLine(Exception):
        pass

    def __init__(self):
        self.nodes: dict[str, Segment] = {}

    def _add_to_nodes(self, node_string: str) -> Segment:
        """ Takes a Node string and converts it into a Segment object, saves it to memory and returns it as well. """
        node_string = node_string.strip()
        if self.details in node_string:
            _name, _volume = node_string.split(self.details)
            _volume = float(_volume)
        else:
            _name = node_string
            _volume = None
        _name = _name.strip()
        if _name not in self.nodes:
            self.nodes[_name] = Segment(_name, _volume)
        elif self.nodes[_name].volume is None:
            self.nodes[_name].data.volume = _volume
        return self.nodes[_name]

    def _strip_line(self, line: str) -> str:
        """ Takes a line from the spec string and will remove comments and strip whitespace, signaling a skip if
        nothing remains. """
        if self.comment in line:
            line, *_ = line.split(self.comment)
        line = line.strip()
        if not line:
            raise self.SkipLine
        return line

    def _check_for_possible_typos(self, line_idx: int, line: str):
        """ Prints warning messages if the line from the spec string contains suspicious patterns. """
        if (self.connects_to not in line) and (" >" in line or "> " in line):
            print(f"Warning, possible connection typo on line #{line_idx} '{line}'")
        if (self.provided_all not in line) and (self.provided_final not in line) and (" |" in line or "| " in line):
            print(f"Warning, possible constraint typo on line #{line_idx} '{line}'")
        if (": " in line) or (" :" in line):
            # ": " will throw exception for Nodes but be silent for Constraints
            # " :" will be silent for Nodes and Constraints
            print(f"Warning, possible detailing typo on line #{line_idx} '{line}'")

    def _import_header(self, line: str):
        """ Goes through a line from the spec file which does not contain the connects-to (' > ') token, which are
        assumed to be declarations and initializations for individual Nodes (comma separated), and processes each Node.
        """
        if self.connects_to not in line:
            for entry in line.split(","):
                if entry.strip():
                    self._add_to_nodes(entry)
            raise self.SkipLine

    def _unpack_phrases(self, line: str) -> tuple[str, str | None]:
        """ Splits a line into its components (connections and constraints) """
        if self.provided_final in line and self.provided_all in line:
            raise ValueError(f"A line cannot contain both a provided_all ('||') and provided_final ('|') token!")
        phrases = [
            phrase
            for _phrase in line.split(self.provided_all)
            for phrase in _phrase.split(self.provided_final)
        ]
        connection_phrase, constraint_phrase, *_ = phrases + 2 * [None, ]
        if connection_phrase is None:
            raise ValueError(f"A constraint cannot occur on a line without a connection phrase ('A > B')")
        return connection_phrase, constraint_phrase

    def _determine_constraint_mode(self,
                                   line_idx: int,
                                   line: str,
                                   constraint_phrase: str
                                   ) -> Literal['all', 'final', None]:
        """ Inspects a line to determine if the constraints apply to the last or all connections. """
        if constraint_phrase is None:
            return None
        elif self.provided_all in line:
            return "all"
        elif self.provided_final in line:
            return "final"
        else:
            print(f"Warning on line #{line_idx} '{line}'\n\tCould not determine constraint mode")
            return None

    def _compile_connections_and_constraints(self,
                                             connection_phrase: str,
                                             constraint_mode: str | None,
                                             constraint_phrase: str
                                             ):
        """ Runs through and adds all the connections. """
        connection_nodes = connection_phrase.split(self.connects_to)
        connections = [f"{_s}{self.connects_to}{_d}" for _s, _d in zip(connection_nodes, connection_nodes[1:])]

        last_index = len(connections) - 1
        for _idx, connection in enumerate(connections):  # type: int, str
            _source, _destination = connection.split(self.connects_to)
            source, destination = self._add_to_nodes(_source), self._add_to_nodes(_destination)
            if (constraint_mode is None) or ((constraint_mode == 'final') and (_idx != last_index)):
                source.connect(destination)
                continue
            for constraint in constraint_phrase.split(","):
                for_state = self._unpack_constraint(constraint)
                source.connect(destination, for_state=for_state)

    def _unpack_constraint(self, constraint_string: str | None) -> tuple[str, str] | None:
        """ takes a constraint string and returns the state_id and state_name (or None) """
        if constraint_string is None:
            return None
        constraint_string = constraint_string.strip()
        _component_state_id, _state_name = constraint_string.split(self.details)
        return _component_state_id.strip(), _state_name.strip()

    def decode(self, string: str) -> dict[str, Segment]:
        """ Constructs a flow path from a string representation and provides a view over the whole graph. """
        for line_idx, line in enumerate(string.split("\n")):  # type: int, str
            try:
                line = self._strip_line(line)
                self._check_for_possible_typos(line_idx, line)
                self._import_header(line)

                connection_phrase, constraint_phrase = self._unpack_phrases(line)
                constraint_mode = self._determine_constraint_mode(line_idx, line, constraint_phrase)

                self._compile_connections_and_constraints(connection_phrase, constraint_mode, constraint_phrase)

            except self.SkipLine:
                pass
            except ValueError as ve:
                print(f"Error parsing line #{line_idx}: '{line.strip()}'\n\t{ve!r}")

        for node in self.nodes.values():
            if node.volume is None:
                print(f"Assuming a volume of 0 for '{node.name}'")
                node.data.volume = 0

        return self.nodes

    @staticmethod
    def encode_selector_valve(
            sources: Iterable[tuple[str, int]], selector: str, syringe: str, outlet: str, prefix: str = ""
    ) -> str:
        """ Automates the binding of multiple input sources to a Selector valve.

        Tubing are auto-generated using the lowercase version of what they connect and a "_" symbol.

        Example:  If given Bottle_1 on port 2, Bottle_2 on port 3, and Bottle_3 on port 4, RSelect_1 as the selector,
        RSyr_1 as the syringe, and rselect_1_system as the outlet, then this returns:

        - "Bottle_1 > bottle_1_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_2"
        - "Bottle_2 > bottle_2_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_3"
        - "Bottle_3 > bottle_3_rselect_1 > rselect_1_rsyr_1 | rselect_1:refill_4"
        - ...and so on, were there more bottles...
        - "rselect_1_rsyr_1 > RSyr_1 | rselect_1:refill_2, rselect_1:refill_3, rselect_1:refill_4  # arbitrary order"
        - "RSyr_1 > rselect_1_rsyr_1 > rselect_1_system || rselect_1:drive"

        """
        encoding = [f"\n{prefix}# <Auto-generated segment for selector valve inputs>", ]

        sel_to_syr = f"{selector.lower()}_{syringe.lower()}"
        refilling_states: set[str] = set()

        for source, port in sources:
            tubing = f"{source.lower()}_{selector.lower()}"
            refilling_state = f"{selector.lower()}:refill_{port}"
            encoding.append(f"{source} > {tubing} > {sel_to_syr} | {refilling_state}")
            refilling_states.add(refilling_state)

        refilling = ", ".join([refilling_state for refilling_state in refilling_states])
        driving_state = f"{selector.lower()}:drive"
        encoding.append(f"{sel_to_syr} > {syringe} | " + refilling)
        encoding.append(f"{syringe} > {sel_to_syr} > {outlet} || {driving_state}")
        encoding.append(f"# </Auto-generated segment>\n")

        return f"\n{prefix}".join(encoding)

    @staticmethod
    def generate_header(flow_graph: Segment, width: int = 120, prefix: str = "") -> str:
        """ Given a graph, produce the header for a specification file for re-use. """
        all_nodes = sorted(
            sorted(
                flow_graph.all_nodes,
                key=lambda n: n.has_children(True),
                reverse=True),
            key=lambda n: n.has_parents(True),
            reverse=True
        )

        input_entries = [f"{node.name}:{node.volume}, " for node in all_nodes if not node.has_parents(True)]
        output_entries = [f"{node.name}:{node.volume}, " for node in all_nodes if not node.has_children(True)]
        all_entries = [f"{node.name}:{node.volume}, " for node in all_nodes]
        inner_entries = [
            entry
            for entry in all_entries
            if (entry not in input_entries) and (entry not in output_entries)
        ]
        header_string = f"\n{prefix}# <Auto-generated header segment>\n{prefix}"
        for entry in input_entries + inner_entries + output_entries:
            if len(header_string.split("\n")[-1]) + len(entry) > width:
                header_string += f"\n{prefix}"
            header_string += entry
        return header_string + f"\n{prefix}# </Auto-generated segment>\n"


def print_path(path: list[Segment]) -> str:
    """ prints a path in the form '[segment]-->[segment]-->...' """
    return "-->".join([f"[{seg.name}]" for seg in path])


if __name__ == '__main__':
    # my_reactor_spec = """
    # # Declaring some nodes and their volumes ahead of time
    # #   (Purposefully being messy and leaving some declarations out)
    # Syringe_1:0, Reactor:700, Syringe_2:0, Pump:0,Joiner:2 , Waste,,  ,,
    # sel<>syr:100,  sel->vlv:50, vlv->rxt:80, vlv1->jnr:64, syr->vlv:400, vlv2->jnr:80, pmp->vlv:300
    # rxt->jnr:2, jnr->wst:500
    #
    # # Bottles to the main syringe in the refilling state
    # Bottle_1:0  > bot1->sel:4    > sel<>syr  | selector_1:refill_1  # Constraint only applies to bot1->sel:4 > sel<>syr
    # Bottle_2:0  > bot2->sel:4.1  > sel<>syr  | selector_1:refill_2
    # Bottle_3:0  > bot3->sel:4.2  > sel<>syr  | selector_1:refill_3
    # sel<>syr    > Syringe_1                  | selector_1:refill_1, selector_1:refill_2, selector_1:refill_3
    #
    # # Main syringe to the 6-Port valve
    # Syringe_1  > sel<>syr  > sel->vlv  || selector_1:drive  # Constraint applies to both connections
    #
    # # Main fluid line through the 6-Port valve
    # sel->vlv   > vlv->rxt                        | valve_1:through
    # sel->vlv   > vlv1->jnr                       | valve_1:bypass
    # vlv->rxt   > Reactor    > rxt->jnr > Joiner
    # vlv1->jnr  > Joiner
    #
    # # Diluter syringe to the 6-Port valve
    # Syringe_2  > syr->vlv  > vlv2->jnr  | valve_1:through
    #              syr->vlv  > vlv->rxt   | valve_1:bypass
    # vlv2->jnr  > Joiner
    #
    # # Wash pump to the 6-Port valve
    # Pump  > pmp->vlv  > vlv1->jnr  | valve_1:through
    #         pmp->vlv  > vlv2->jnr  | valve_1:bypass
    #
    # # Take us out
    # Joiner  > jnr->wst  > Waste
    # """

    my_reactor_spec = """
    # Declaring some nodes and their volumes ahead of time
    Syringe_1:0, Syringe_2:0, Syringe_3:0
    line_a1:0, line_a2:0, line_a3:0
    line_b1:200, line_c1:300
    ftir:0

    # connection :)
    Syringe_1 > line_a1 > line_b1 > line_c1 > ftir
    Syringe_2 > line_a2 > line_b1
    Syringe_3 > line_a3 > line_c1
    """

    # print(Interpreter().encode_selector_valve(
    #     [
    #         ("Bottle_1", 2),
    #         ("Bottle_2", 3),
    #         ("Bottle_3", 4)
    #     ],
    #     "RSelect_1",
    #     "RSyr_1",
    #     "rselect_1_system",
    #     prefix="    "
    # ))

    my_reactor = Interpreter().decode(my_reactor_spec)

    # bottle = my_reactor['Bottle_2']
    # bottle.set_state('valve_1', 'through')
    # bottle.set_state("selector_1", "drive")

    # print(Interpreter.generate_header(bottle, prefix=4*" ", width=80))

    iais = False
    starting_at = my_reactor['Syringe_1']

    print(my_reactor['Syringe_1'])
    print("\n====\n\n")

    # my_condition: Callable[[Segment], bool] = lambda n: (not n.has_children(iais)) or (not n.has_parents(iais))
    my_condition: Callable[[Segment], bool] = lambda n: n.name == "ftir"

    counter = 0
    for result, result_path in starting_at.traverse(my_condition, direction=Direction.DOWN, ignore_state=iais):
        print(counter)
        print(result.print(iais))
        # print([_p.print(iais) for _p in result_path])
        print(print_path(result_path))
        print(starting_at.volume_to(result.name) - (starting_at.volume - result.volume))
        counter += 1

    print("\n====\n")
    test_flow_rates = {'Syringe_1': 55, 'Syringe_2': 90, 'Syringe_3': 55}
    print(my_reactor['ftir'].time_from(**test_flow_rates))
    # {'Syringe_1': 100, 'Syringe_2': 50, 'Pump': 25}
    # through: 17.429
    # bypass:  26.509
    print(my_reactor['ftir'].check_flow_stability_from(**test_flow_rates))
