__version__ = '0.0.1'

import binascii
import codecs
import ctypes
import re
import struct

import click

import hid


VENDOR_ID = 0x0b0e
PRODUCT_ID = 0x245e


class JabraError(Exception):
    pass


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = {}


@cli.command()
def adapters():
    """List BT Jabra Link adapters"""
    adapters = list_adapters()
    if adapters:
        for adapter in adapters:
            print("%d: %s:%s %s" % (adapter['index'], adapter['vendor_id'], adapter['product_id'], adapter['product_string']))
    else:
        print("No devices found.")


@cli.group()
@click.option('-a', '--adapter', 'index', default=0, type=click.INT)
@click.pass_context
def adapter(ctx, index):
    """Perform adapter configuration."""
    try:
        ctx.obj['adapter'] = get_adapter(index)
    except JabraError as exc:
        raise click.ClickException(exc.args[0])


@adapter.command()
@click.pass_context
def headsets(ctx):
    """List devices attached to adapter."""
    adapter = ctx.obj['adapter']
    headsets = []
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        headsets.extend(list_headsets(device))
    if headsets:
        for h in headsets:
            print('%d: %s (connected: %s, address: %s)' % (
                  h['index'], h['deviceName'], 'yes' if h['connected'] else 'no', h['address']))
    else:
        print('No headsets found')


@adapter.command()
@click.argument('index_or_addr')
@click.pass_context
def connect(ctx, index_or_addr):
    handle_connect(True, ctx, index_or_addr)


@adapter.command()
@click.argument('index_or_addr')
@click.pass_context
def disconnect(ctx, index_or_addr):
    handle_connect(False, ctx, index_or_addr)


def handle_connect(target_connect, ctx, index_or_addr):
    handler = headset_connect if target_connect else headset_disconnect
    adapter = ctx.obj['adapter']
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        headsets = list_headsets(device)
        def headset_filter(h):
            if ':' in index_or_addr:
                return h['address'] == index_or_addr
            else:
                return h['index'] == int(index_or_addr)
        try:
            headset = next(filter(headset_filter, headsets))
            handler(device, headset)
        except StopIteration:
            raise click.ClickException("Device %s not found" % (index_or_addr, ))


@adapter.command()
@click.option('--enabled/--disabled', 'status', default=None)
@click.pass_context
def auto_pairing(ctx, status):
    """Configure auto-pairing status."""
    adapter = ctx.obj['adapter']
    if status is None:
        with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
            status = pairing_status(device)
            print("enabled" if status else "disabled")
    else:
        with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
            status = set_pairing_status(device, status)
            print("enabled" if status else "disabled")


hexlify = codecs.getencoder('hex')


def get_adapter(index):
    try:
        adapters = list_adapters()
        return adapters[index]
    except IndexError:
        raise JabraError("Device %d not found" % (index, ))


def list_adapters():
    adapters = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    adapters = sorted(adapters, key=lambda a: a['serial_number'])
    for index, a in enumerate(adapters):
        a['index'] = index
    return adapters


def pairing_status(device):
    counter = 0
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x46\x13\x40'
    device.write(bytes(buff))
    counter += 1
    data = device.read(64)
    return struct.unpack('?', data[7:8])[0]


def set_pairing_status(device, status):
    counter = 0
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x87\x13\x40'
    buff[7:8] = struct.pack('?', status)
    device.write(bytes(buff))
    counter += 1
    device.read(64)
    return pairing_status(device)


def headset_connect(device, headset):
    counter = 0
    address = binascii.a2b_hex(headset['address'].replace(':', ''))
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x8d\x0d\x24'
    buff[8:14] = address
    device.write(bytes(buff))
    counter += 1
    connected = False
    expected = b'\x11\x0d\x26\x01' + address
    while not connected:
        data = device.read(64)
        # data[16] = \x01 or \x04
        if data[4:14] == expected and data[16] & 5:
            connected = True


def headset_disconnect(device, headset):
    counter = 0
    address = binascii.a2b_hex(headset['address'].replace(':', ''))
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x8d\x0d\x25'
    buff[8:14] = address
    device.write(bytes(buff))
    counter += 1
    connected = False
    expected = b'\x11\x0d\x26\x01' + address
    while not connected:
        data = device.read(64)
        # data[16] = \x01 or \x04
        if data[4:14] == expected and data[16] & 5:
            connected = True


def list_headsets(device):
    headsets = []
    index = 0
    counter = 1
    while True:
        buff = bytearray(64)
        buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x48\x0d\x28'
        buff[8:9] = struct.pack('B', index)
        device.write(bytes(buff))
        counter += 1
        data = device.read(64)
        headset = dict()
        headset['index'] = index
        headset['address'] = ':'.join(re.findall('..', hexlify(data[13:19])[0].decode('ascii')))
        headset['connected'] = data[11:12] == b'\x04'
        last = struct.unpack('?', data[7:8])[0]
        buff2 = bytearray(64)
        buff2[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x48\x0d\x32'
        buff2[8:9] = struct.pack('B', index)
        device.write(bytes(buff2))
        counter += 1
        data2 = device.read(64)
        headset['deviceName'] = ctypes.create_string_buffer(data2[9:64]).value.decode('ascii')
        headsets.append(headset)
        if last:
            break
        index = struct.unpack('B', data[8:9])[0]
    return headsets

