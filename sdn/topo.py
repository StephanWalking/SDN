#!/usr/bin/env python3
"""
Topologie voor twee gebouwen (A en B) met darkfiber, VLAN-segmentatie en ISP-uplinks.
Aangestuurd via OpenFlow 1.3 en de Faucet controller.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

def build():
    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=True)

    # Faucet Controller
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    # Switches aanmaken met 16-hexkarakter DPIDs (OpenFlow 1.3)
    kw = dict(protocols='OpenFlow13')
    sA0 = net.addSwitch('sA0', dpid='0000000000000001', **kw)
    sA1 = net.addSwitch('sA1', dpid='0000000000000002', **kw)
    sA2 = net.addSwitch('sA2', dpid='0000000000000003', **kw)

    sB0 = net.addSwitch('sB0', dpid='0000000000000004', **kw)
    sB1 = net.addSwitch('sB1', dpid='0000000000000005', **kw)
    sB2 = net.addSwitch('sB2', dpid='0000000000000006', **kw)
    sB3 = net.addSwitch('sB3', dpid='0000000000000007', **kw)

    # --- Inter-switch verbindingen ---
    # Gebouw A interne backbone (sA0 poort 1 en 2)
    net.addLink(sA0, sA1)  # sA0-eth1 <-> sA1-eth1
    net.addLink(sA0, sA2)  # sA0-eth2 <-> sA2-eth1

    # Gebouw B interne backbone (sB0 poort 1, 2 en 3)
    net.addLink(sB0, sB1)  # sB0-eth1 <-> sB1-eth1
    net.addLink(sB0, sB2)  # sB0-eth2 <-> sB2-eth1
    net.addLink(sB0, sB3)  # sB0-eth3 <-> sB3-eth1

    # Darkfiber tussen de centrale patchkasten (sA0 poort 3 <-> sB0 poort 4)
    net.addLink(sA0, sB0)  # sA0-eth3 <-> sB0-eth4

    # --- Endpoints / Hosts ---
    # Volgorde van toevoegen bepaalt het MAC-adres met autoSetMacs:
    # hA1 -> 00:00:00:00:00:01
    # hB1 -> 00:00:00:00:00:02
    # hA2 -> 00:00:00:00:00:03
    # hB3 -> 00:00:00:00:00:04
    # hB2 -> 00:00:00:00:00:05 (Komt exact overeen met de mgmt_portsec ACL)
    hosts_cfg = [
        ('hA1', sA1, '10.10.0.1/22'),   # Employee
        ('hB1', sB1, '10.10.0.2/22'),   # Employee
        ('hA2', sA2, '10.20.0.1/22'),   # Gast
        ('hB3', sB3, '10.20.0.2/22'),   # Gast
        ('hB2', sB2, '10.30.0.1/24')    # Management
    ]

    for name, sw, ip in hosts_cfg:
        h = net.addHost(name, ip=ip)
        net.addLink(h, sw)  # Wordt poort 2 op sA1, sA2, sB1, sB2, sB3

    # --- Externe Connectiviteit / ISP & NAT ---
    # Gebouw A: Router A (aangesloten op sA0 poort 4 en 5)
    natA = net.addHost('natA', ip=None)
    inetA = net.addHost('inetA', ip='203.0.113.1/28')  # ISP A simulatie
    net.addLink(natA, sA0)    # natA-eth0 <-> sA0-eth4 (Employee)
    net.addLink(natA, sA0)    # natA-eth1 <-> sA0-eth5 (Gast)
    net.addLink(natA, inetA)  # natA-eth2 <-> inetA-eth0

    # Gebouw B: Router B (aangesloten op sB0 poort 5 en 6)
    natB = net.addHost('natB', ip=None)
    inetB = net.addHost('inetB', ip='203.0.113.17/28') # ISP B simulatie
    net.addLink(natB, sB0)    # natB-eth0 <-> sB0-eth5 (Employee)
    net.addLink(natB, sB0)    # natB-eth1 <-> sB0-eth6 (Gast)
    net.addLink(natB, inetB)  # natB-eth2 <-> inetB-eth0

    return net

def configure_network(net):
    # --- NAT Router A configuratie ---
    natA = net.get('natA')
    natA.cmd('ip addr add 10.10.0.254/22 dev natA-eth0')
    natA.cmd('ip addr add 10.20.0.254/22 dev natA-eth1')
    natA.cmd('ip addr add 203.0.113.2/28 dev natA-eth2')
    natA.cmd('sysctl -w net.ipv4.ip_forward=1')
    natA.cmd('iptables -P FORWARD DROP')
    natA.cmd('iptables -A FORWARD -i natA-eth0 -o natA-eth2 -j ACCEPT')
    natA.cmd('iptables -A FORWARD -i natA-eth1 -o natA-eth2 -j ACCEPT')
    natA.cmd('iptables -A FORWARD -i natA-eth2 -m state --state RELATED,ESTABLISHED -j ACCEPT')
    natA.cmd('iptables -t nat -A POSTROUTING -o natA-eth2 -j MASQUERADE')

    # --- NAT Router B configuratie (Redundantie / ISP B) ---
    natB = net.get('natB')
    natB.cmd('ip addr add 10.10.0.253/22 dev natB-eth0')
    natB.cmd('ip addr add 10.20.0.253/22 dev natB-eth1')
    natB.cmd('ip addr add 203.0.113.18/28 dev natB-eth2')
    natB.cmd('sysctl -w net.ipv4.ip_forward=1')
    natB.cmd('iptables -P FORWARD DROP')
    natB.cmd('iptables -A FORWARD -i natB-eth0 -o natB-eth2 -j ACCEPT')
    natB.cmd('iptables -A FORWARD -i natB-eth1 -o natB-eth2 -j ACCEPT')
    natB.cmd('iptables -A FORWARD -i natB-eth2 -m state --state RELATED,ESTABLISHED -j ACCEPT')
    natB.cmd('iptables -t nat -A POSTROUTING -o natB-eth2 -j MASQUERADE')

    # Default gateways instellen voor hosts in Gebouw A
    net.get('hA1').cmd('ip route add default via 10.10.0.254')
    net.get('hA2').cmd('ip route add default via 10.20.0.254')

    # Default gateways instellen voor hosts in Gebouw B (via Router B)
    net.get('hB1').cmd('ip route add default via 10.10.0.253')
    net.get('hB3').cmd('ip route add default via 10.20.0.253')

    # Internet-hosts route teruggeven
    net.get('inetA').cmd('ip route add default via 203.0.113.2')
    net.get('inetB').cmd('ip route add default via 203.0.113.18')

if __name__ == '__main__':
    setLogLevel('info')
    net = build()
    net.start()
    configure_network(net)
    print("\n--- Netwerk gereed. Start CLI ---")
    CLI(net)
    net.stop()
