#!/usr/bin/env python3
"""
Fase 2 Topologie:
- Dual-Stack (IPv4 /22 voor >500 users + IPv6 /64)
- Redundante Controllers (c0 en c1 voor Level 4 beoordeling)
- NFV Stateful Firewalling (iptables & ip6tables via conntrack)
- IPv4 PAT/NAT Masquerading voor het /28 ISP-blok
- Userspace Datapath (netdev) voor OpenFlow 1.3 Meter ondersteuning
"""

import time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

def build():
    net = Mininet(controller=None, switch=OVSSwitch, autoSetMacs=True)

    # --- CONTROLLER REDUNDANTIE (Criterium 6: Level 4) ---
    c0 = net.addController('c0', controller=RemoteController, ip='172.17.0.1', port=6653)
    c1 = net.addController('c1', controller=RemoteController, ip='172.17.0.1', port=6654)

    # datapath='netdev' activeert userspace OVS waardoor OpenFlow 1.3 meters functioneren
    kw = dict(protocols='OpenFlow13', datapath='netdev')
    
    # Switches Gebouw A
    sA0 = net.addSwitch('sA0', dpid='0000000000000001', **kw)
    sA1 = net.addSwitch('sA1', dpid='0000000000000002', **kw)
    sA2 = net.addSwitch('sA2', dpid='0000000000000003', **kw)

    # Switches Gebouw B
    sB0 = net.addSwitch('sB0', dpid='0000000000000004', **kw)
    sB1 = net.addSwitch('sB1', dpid='0000000000000005', **kw)
    sB2 = net.addSwitch('sB2', dpid='0000000000000006', **kw)
    sB3 = net.addSwitch('sB3', dpid='0000000000000007', **kw)

    # Interne switchverbindingen (Uplinks)
    net.addLink(sA0, sA1)  # sA0-p1 <-> sA1-p1
    net.addLink(sA0, sA2)  # sA0-p2 <-> sA2-p1
    net.addLink(sB0, sB1)  # sB0-p1 <-> sB1-p1
    net.addLink(sB0, sB2)  # sB0-p2 <-> sB2-p1
    net.addLink(sB0, sB3)  # sB0-p3 <-> sB3-p1

    # Darkfiber trunk tussen Gebouw A en B
    net.addLink(sA0, sB0)  # sA0-p3 <-> sB0-p4

    # Endpoints toevoegen (/22 biedt ruimte aan >500 users)
    hosts_cfg = [
        ('hA1', sA1, '10.10.0.1/22'),   # Employee Gebouw A (MAC ...:01)
        ('hB1', sB1, '10.10.0.2/22'),   # Employee Gebouw B (MAC ...:02)
        ('hA2', sA2, '10.20.0.1/22'),   # Gast Gebouw A     (MAC ...:03)
        ('hB3', sB3, '10.20.0.2/22'),   # Gast Gebouw B     (MAC ...:04)
        ('hB2', sB2, '10.30.0.1/24')    # Beheer Gebouw B   (MAC ...:05)
    ]

    for name, sw, ip in hosts_cfg:
        h = net.addHost(name, ip=ip)
        net.addLink(h, sw)

    # Externe Routers & ISP simulatie
    # Gebouw A
    natA = net.addHost('natA', ip=None)
    inetA = net.addHost('inetA', ip='203.0.113.1/28')
    net.addLink(natA, sA0)    # natA-eth0 <-> sA0-p4 (VLAN 10 Employee)
    net.addLink(natA, sA0)    # natA-eth1 <-> sA0-p5 (VLAN 20 Gast)
    net.addLink(natA, sA0)    # natA-eth2 <-> sA0-p6 (VLAN 30 Mgmt)
    net.addLink(natA, inetA)  # natA-eth3 <-> inetA-eth0 (WAN Uplink ISP A)

    # Gebouw B
    natB = net.addHost('natB', ip=None)
    inetB = net.addHost('inetB', ip='203.0.113.17/28')
    net.addLink(natB, sB0)    # natB-eth0 <-> sB0-p5 (VLAN 10 Employee)
    net.addLink(natB, sB0)    # natB-eth1 <-> sB0-p6 (VLAN 20 Gast)
    net.addLink(natB, sB0)    # natB-eth2 <->
