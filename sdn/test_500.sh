#!/bin/bash
# 500 gelijktijdige "gebruikers" via NAT naar de ISP.
#
# Draai in de Mininet-CLI (op de achtergrond, zodat je de CLI kunt blijven gebruiken):
#   mininet> hA1 bash test_500.sh &
#
# Kijk daarna terwijl de pings lopen (binnen ~10 seconden):
#   mininet> natA conntrack -C
#
# Resultaat bekijken als het klaar is:
#   mininet> sh cat /tmp/test500.log

IF=hA1-eth0
TARGET=203.0.113.1
LOG=/tmp/test500.log
TMP=$(mktemp)

echo "Adressen toevoegen op $IF..."
for x in $(seq 1 250); do
  ip addr add 10.10.1.$x/22 dev $IF 2>/dev/null
  ip addr add 10.10.2.$x/22 dev $IF 2>/dev/null
done

echo "500 pings starten (elk vanaf een eigen bronadres)..."
for net in 1 2; do
  for x in $(seq 1 250); do
    SRC=10.10.$net.$x
    (
      if ping -c 10 -i 1 -W 2 -I $SRC $TARGET > /dev/null 2>&1; then
        echo OK >> $TMP
      else
        echo FAIL >> $TMP
      fi
    ) &
  done
done

wait

OK=$(grep -c OK $TMP)
FAIL=$(grep -c FAIL $TMP)
{
  echo "Klaar: $OK van 500 gebruikers konden de ISP bereiken ($FAIL mislukt)."
} | tee $LOG

# Adressen weer opruimen
for x in $(seq 1 250); do
  ip addr del 10.10.1.$x/22 dev $IF 2>/dev/null
  ip addr del 10.10.2.$x/22 dev $IF 2>/dev/null
done
rm -f $TMP
