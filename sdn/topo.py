#!/usr/bin/env python3
"""
Fase 2 Topologie - Pure SDN (Faucet Fabric Stacking + OVS Conntrack NAT)
"""

import time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

def build():
    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=False)

    c0 = net.addController('c0', controller=RemoteController, ip='172.17.0.1', port=6653)
    c1 = net.addController('c1', controller=RemoteController, ip='172.17.0.1', port=6654)

    kw = dict(protocols='OpenFlow13', datapath='netdev')
    
    # Switches Gebouw A (DPIDs: 1, 2, 3)
    sA0 = net.addSwitch('sA0', dpid='0000000000000001', **kw)
    sA1 = net.addSwitch('sA1', dpid='0000000000000002', **kw)
    sA2 = net.addSwitch('sA2', dpid='0000000000000003', **kw)

    # Switches Gebouw B (DPIDs: 0x11=17, 0x12=18, 0x13=19, 0x14=20)
    sB0 = net.addSwitch('sB0', dpid='0000000000000011', **kw)
    sB1 = net.addSwitch('sB1', dpid='0000000000000012', **kw)
    sB2 = net.addSwitch('sB2', dpid='0000000000000013', **kw)
    sB3 = net.addSwitch('sB3', dpid='0000000000000014', **kw)

    # ISP Nodes (direct gekoppeld aan sA0-p1 en sB0-p1)
    inetA = net.addHost('inetA', ip='203.0.113.1/28')
    inetB = net.addHost('inetB', ip='203.0.113.17/28')
    net.addLink(inetA, sA0)  # inetA-eth0 <-> sA0-eth1 (poort 1)
    net.addLink(inetB, sB0)  # inetB-eth0 <-> sB0-eth1 (poort 1)

    # Stacking links Gebouw A
    net.addLink(sA0, sA1)  # sA0-eth2 (p2) <-> sA1-eth1 (p1)
    net.addLink(sA0, sA2)  # sA0-eth3 (p3) <-> sA2-eth1 (p1)

    # Stacking links Gebouw B
    net.addLink(sB0, sB1)  # sB0-eth2 (p2) <-> sB1-eth1 (p1)
    net.addLink(sB0, sB2)  # sB0-eth3 (p3) <-> sB2-eth1 (p1)
    net.addLink(sB0, sB3)  # sB0-eth4 (p4) <-> sB3-eth1 (p1)

    # Darkfiber Stack link tussen sA0 en sB0
    net.addLink(sA0, sB0)  # sA0-eth4 (p4) <-> sB0-eth5 (p5)

    # Hosts (allemaal op poort 2 van hun respectievelijke access switch)
    hosts_cfg = [
        ('hA1', sA1, '10.10.0.1/22', '00:00:00:00:00:01'),
        ('hA2', sA2, '10.20.0.1/22', '00:00:00:00:00:02'),
        ('hB1', sB1, '10.10.0.2/22', '00:00:00:00:00:03'),
        ('hB2', sB2, '10.30.0.1/24', '00:00:00:00:00:05'),
        ('hB3', sB3, '10.20.0.2/22', '00:00:00:00:00:04')
    ]

    for name, sw, ip, mac in hosts_cfg:
        h = net.addHost(name, ip=ip, mac=mac)
        net.addLink(sw, h)

    return net

def configure_network(net):
    print("*** Netwerk configureren en wachten op switch initialisatie...")
    time.sleep(2)

    # IPv6 expliciet inschakelen op alle hosts[cite: 5]
    for host in net.hosts:
        host.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=0')
        host.cmd('sysctl -w net.ipv6.conf.default.disable_ipv6=0')
        host.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=0')

    # Hosts configureren (default gateways wijzen naar Faucet VIPs)
    host_routing = {
        'hA1': ('2001:db8:10::1/64', '10.10.0.254', '2001:db8:10::fe'),
        'hA2': ('2001:db8:20::1/64', '10.20.0.254', '2001:db8:20::fe'),
        'hB1': ('2001:db8:10::2/64', '10.10.0.254', '2001:db8:10::fe'),
        'hB2': ('2001:db8:30::1/64', '10.30.0.254', '2001:db8:30::fe'),
        'hB3': ('2001:db8:20::2/64', '10.20.0.254', '2001:db8:20::fe'),
    }

    for hname, (ipv6, gw4, gw6) in host_routing.items():
        h = net.get(hname)
        h.cmd(f'ip -6 addr add {ipv6} dev {hname}-eth0')
        h.cmd(f'ip route add default via {gw4}')
        h.cmd(f'ip -6 route add default via {gw6}')

    # ISP Nodes (WAN endpoints)
    inetA = net.get('inetA')
    inetA.cmd('ip -6 addr add 2001:db8:a::1/64 dev inetA-eth0')
    inetA.cmd('ip route add default via 203.0.113.2')
    inetA.cmd('ip -6 route add default via 2001:db8:a::2')

    inetB = net.get('inetB')
    inetB.cmd('ip -6 addr add 2001:db8:b::1/64 dev inetB-eth0')
    inetB.cmd('ip route add default via 203.0.113.18')
    inetB.cmd('ip -6 route add default via 2001:db8:b::2')

if __name__ == '__main__':
    setLogLevel('info')
    net = build()
    net.start()

    controllers = [net.get('c0'), net.get('c1')]
    for sw in net.switches:
        sw.start(controllers)

    configure_network(net)
    print("\n--- Pure SDN Netwerk gereed (Stacking + OVS Conntrack/NAT). Start CLI ---")
    CLI(net)
    net.stop()
