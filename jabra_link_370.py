__version__ = '0.0.1'

import codecs
import ctypes
import struct

import click

import hid


VENDOR_ID = 0x0b0e
PRODUCT_ID = 0x245e


@click.group()
def cli():
    return


@cli.command()
def adapters():
    """List BT Jabra Link adapters"""
    adapters = list_devices()
    if adapters:
        for adapter in adapters:
            print("%d: %s:%s %s" % (adapter['index'], adapter['vendor_id'], adapter['product_id'], adapter['product_string']))
    else:
        print("No devices found.")
    return


@cli.command()
@click.option('-a', '--adapter', 'index', default=0, type=click.INT)
def headsets(index):
    adapters = list_devices()
    try:
        adapter = adapters[index]
        headsets = []
        with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
            headsets.extend(list_headsets(device))
        if headsets:
            for h in headsets:
                print('%d: %s (connected: %s)' % (h['index'], h['deviceName'], 'yes' if h['connected'] else 'no'))
        else:
            print('No headsets found')
    except IndexError:
        print("Device %d not found", (index, ))
    return


hexlify = codecs.getencoder('hex')


def list_devices():
    adapters = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    adapters = sorted(adapters, key=lambda a: a['serial_number'])
    for index, a in enumerate(adapters):
        a['index'] = index
    return adapters


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
        headset['address'] = hexlify(data[13:19])[0]
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

