"""Wi-Fi & Services agent facade mirroring netcoop.agents.wifi_services_agent."""

import sys
import netcoop.agents.wifi_services_agent

sys.modules[__name__] = netcoop.agents.wifi_services_agent
from netcoop.agents.wifi_services_agent import WifiServicesAgent
