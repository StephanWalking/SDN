# SDN

Een Mininet-netwerk met twee gebouwen (A en B), bestuurd door twee Faucet-controllers.

## Wat het doet

- **Dual-stack:** elk VLAN heeft een IPv4- en een IPv6-subnet, routeerbaar vanaf de ISP.
- **Stateful firewall:** op de routers (`natA`, `natB`) met iptables/ip6tables en conntrack. Alleen verbindingen die van binnenuit zijn gestart komen door, ongevraagd inkomend verkeer wordt geblokkeerd.
- **NAT/PAT (IPv4):** alle gebruikers delen het ene publieke adres van de router, vanwege het kleine /28-blok. IPv6 heeft geen NAT nodig.
- **Gast-isolatie:** gasten mogen alleen naar de gateway (en dus de ISP), niet naar elkaar en niet naar de andere VLAN's. Dit regelt een Faucet-ACL op de gastpoort, met een rate limit van 10 Mbit/s.
- **Port security:** op de management-poort mag alleen de beheer-pc hB2 (MAC `...:05`).
- **Redundantie:** twee controllers, beide verbonden met alle switches.

## Bestanden

| Bestand | Doel |
|---|---|
| `topo.py` | Mininet-topologie, adressen, routers en firewall |
| `faucet.yaml` | VLAN's, switches en poorten |
| `acls.yaml` | ACL's en meter (wordt ingeladen door `faucet.yaml`) |

Beide YAML-bestanden moeten in dezelfde map staan die Faucet leest (`/etc/faucet/`).

## Netwerk

| VLAN | Naam | IPv4 | IPv6 | Gateway A | Gateway B |
|---|---|---|---|---|---|
| 10 | Employee | 10.10.0.0/22 | 2001:db8:10::/64 | .254 / ::fe | .253 / ::fd |
| 20 | Gast | 10.20.0.0/22 | 2001:db8:20::/64 | .254 / ::fe | .253 / ::fd |
| 30 | Management | 10.30.0.0/24 | 2001:db8:30::/64 | .254 / ::fe | .253 / ::fd |

| Host | Gebouw | VLAN | Gateway |
|---|---|---|---|
| hA1 | A | 10 | natA |
| hA2 | A | 20 (gast) | natA |
| hB1 | B | 10 | natB |
| hB3 | B | 20 (gast) | natB |
| hB2 | B | 30 | natB |

ISP A: `203.0.113.1` en `2001:db8:a::1`. ISP B: `203.0.113.17` en `2001:db8:b::1`.

## Starten

1. **Faucet:** zorg dat beide controllers draaien (`faucet` op poort 6653 en `faucet-b` op 6654) met de YAML-bestanden. Bijvoorbeeld:

   docker start faucet faucet-b
   

2. **Mininet:**

   sudo mn -c
   sudo python3 topo.py
   

3. **Controllers controleren:**
   
   mininet> sh ovs-vsctl show
   
   Onder elke switch moet bij beide controllers `is_connected: true` staan.

## Testen

Gebruik `-c 3` voor korte uitvoer en `-W 1` bij tests die moeten falen.

| Wat | Commando | Verwacht |
|---|---|---|
| IPv4 naar ISP (gebouw A) | `hA1 ping -c 3 203.0.113.1` | werkt |
| IPv6 naar ISP (gebouw A) | `hA1 ping -6 -c 3 2001:db8:a::1` | werkt |
| IPv4 naar ISP (gebouw B) | `hB3 ping -c 3 203.0.113.17` | werkt |
| IPv6 naar ISP (gebouw B) | `hB3 ping -6 -c 3 2001:db8:b::1` | werkt |
| Tussen gebouwen (darkfiber) | `hA1 ping -c 3 10.10.0.2` | werkt |
| Ongevraagd inkomend (firewall) | `inetA ping -6 -c 3 -W 1 2001:db8:10::1` | 100% loss |
| Gast naar internet | `hA2 ping -c 3 203.0.113.1` | werkt |
| Gast naar andere gast | `hA2 ping -c 3 -W 1 10.20.0.2` | 100% loss |
| Gast naar Employee | `hA2 ping -c 3 -W 1 10.10.0.1` | 100% loss |
| Gast naar Management | `hA2 ping -c 3 -W 1 10.30.0.1` | 100% loss |

Port security op de management-poort (pas het mac adress even tijdelijk aan om te testen alleen :05 wordt toegestaan:

```
hB2 ping -c 2 10.30.0.253
hB2 ip link set dev hB2-eth0 address 00:00:00:00:99:99
hB2 ping -c 2 -W 1 10.30.0.253
hB2 ip link set dev hB2-eth0 address 00:00:00:00:00:05
```

Verwacht: eerst werkt het, daarna 100% loss met het onbekende MAC-adres.

## Controller-failover

1. Voer de pings uit de tabel uit (alles werkt).
2. Stop één controller:
   
   docker stop faucet of faucet-b
   
3. Controleer met `sh ovs-vsctl show` dat die controller niet meer verbonden is.
4. Voer dezelfde pings opnieuw uit. Het resultaat blijft gelijk.
5. Start de controller weer (`docker start faucet`).

## Bewijsmateriaal voor het verslag

Doe de dumps **na** de pings, zodat de tellers (`n_packets`) hoger zijn dan 0.

```
sh ovs-ofctl -O OpenFlow13 dump-flows sA2 > flows_sA2.txt
sh ovs-ofctl -O OpenFlow13 dump-flows sB2 > flows_sB2.txt
sh ovs-ofctl -O OpenFlow13 dump-meters sA2
natA ip6tables -L FORWARD -v -n
natA iptables -t nat -S
natA conntrack -L
```

Geen `conntrack`? Gebruik `natA cat /proc/net/nf_conntrack`.

## Afsluiten

mininet> exit
sudo mn -c
