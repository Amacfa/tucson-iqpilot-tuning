#!/bin/sh
# set_variant.sh <0-15> - writes the LFA A/B variant selector on the comma.
# The variant file is read ONCE per CarController start; a parked IQ restart
# (reboot) is required for a new value to take effect. Missing file = 0 =
# release behavior. Run over ssh: ssh mac 'ssh comma "sh -s 3"' < set_variant.sh
set -e
v="${1:?usage: set_variant.sh <0-15>}"
case "$v" in ''|*[!0-9]*) echo "variant must be an integer 0-15" >&2; exit 1;; esac
[ "$v" -ge 0 ] && [ "$v" -le 15 ] || { echo "variant must be 0-15" >&2; exit 1; }
printf '%s' "$v" > /data/tucson_lfa_ab
sync
echo "wrote /data/tucson_lfa_ab = $v (reboot required to take effect)"
