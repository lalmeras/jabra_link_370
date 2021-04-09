# jabra\_link\_370

Command-line utility to manage Jabra Link 370 adapter.

```bash
$ # idVendor and idProduct for GN Netcom Jabra Link 370
$ # may need to be adapted
$ cat <<EOF | sudo tee /etc/udev/rules.d/99-hid.rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="0b0e", ATTRS{idProduct}=="245e", MODE="0666"
KERNEL=="hidraw*", ATTRS{idVendor}=="0b0e", ATTRS{idProduct}=="245e", MODE="0666"
EOF

$ sudo systemctl restart systemd-udevd

$ sudo dnf install hidapi

$ pipenv install

$ pipenv shell

$ jabra-link --help

# List adapters
$ jabra-link adapters
Usage: jabra-link [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  adapters      List Jabra Link bluetooth adapters
  auto-pairing  Configure auto-pairing status.
  clear         Remove ALL pairings.
  connect       Connect already paired device (identified by...
  disconnect    Disconnect currently connected device.
  list          List devices attached to adapter.
  pair          List available devices for pairing.
  unpair        Unpair device designated by INDEX_OR_ADDR_OR_NAME.

# Scan bluetooth devices
jabra-link list
0: Cuisine Bluetooth (connected: yes, address: XX:XX:XX:XX:XX:XX)
1: JBL Reflect Contour2 (connected: no, address: XX:XX:XX:XX:XX:XX)
2: Blue Power Sound (connected: no, address: XX:XX:XX:XX:XX:XX)

# Scan and pair with device
$ jabra-link pair JBL Reflect Contour2
Device JBL Reflect Contour2 (XX:XX:XX:XX:XX:XX) paired.
Device JBL Reflect Contour2 connected.

# Connect
$ jabra-link connect "Blue Power Sound"
Device JBL Reflect Contour2 disconnected.
Device Blue Power Sound connected.

# Disconnect
$ jabra-link disconnect
Device Blue Power Sound disconnected.

# Unpair
$ jabra-link unpair "Blue Power Sound"
Device Blue Power Sound unpaired.
```
