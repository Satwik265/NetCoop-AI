"""Topology agent facade mirroring netcoop.agents.topology_agent."""

import sys
import netcoop.agents.topology_agent

sys.modules[__name__] = netcoop.agents.topology_agent
from netcoop.agents.topology_agent import ConnectivityAgent, TopologyAgent
