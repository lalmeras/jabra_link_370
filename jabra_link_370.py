__version__ = '0.0.1'

import binascii
import codecs
import ctypes
import functools
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


@cli.command('adapters')
def cmd_adapters():
    """List Jabra Link bluetooth adapters"""
    adapters = do_list_adapters()
    if adapters:
        for adapter in adapters:
            print("%d: %s:%s %s" % (adapter['index'], adapter['vendor_id'], adapter['product_id'], adapter['product_string']))
    else:
        print("No devices found.")


def install_adapter(f):
    """Handle -a/--adapter option for all commands."""
    @click.option('-a', '--adapter', 'index_or_name_or_serial', default=0, type=click.STRING,
                  help='Target an specific adapter; first adapter when option is missing.')
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        try:
            n_kwargs = dict(kwargs)
            del n_kwargs['index_or_name_or_serial']
            ctx.obj['adapter'] = lookup_adapter(kwargs['index_or_name_or_serial'])
            return ctx.invoke(f, *args, **n_kwargs)
        except JabraError as exc:
            raise click.ClickException(exc.args[0])
    return functools.update_wrapper(new_func, f)


@cli.command('list')
@click.pass_context
@install_adapter
def cmd_headsets(ctx):
    """List devices attached to adapter."""
    adapter = ctx.obj['adapter']
    headsets = []
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        headsets.extend(do_list_headsets(device))
    if headsets:
        for h in headsets:
            print('%d: %s (connected: %s, address: %s)' % (
                  h['index'], h['deviceName'], 'yes' if h['connected'] else 'no', h['address']))
    else:
        print('No headsets found.')


@cli.command('connect')
@click.pass_context
@click.argument('index_or_addr_or_name')
@install_adapter
def cmd_connect(ctx, index_or_addr_or_name):
    """Connect already paired device (identified by INDEX_OR_ADDR_OR_NAME). Use _list_ command to display
    paired devices.
    """
    handle_connect(False, ctx, True)
    handle_connect(True, ctx, index_or_addr_or_name)


@cli.command('disconnect')
@click.pass_context
@install_adapter
def cmd_disconnect(ctx):
    """Disconnect currently connected device."""
    handle_connect(False, ctx, True)


@cli.command('clear')
@click.pass_context
@install_adapter
def cmd_clear(ctx):
    """Remove ALL pairings."""
    adapter = ctx.obj['adapter']
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        do_clear(device)


@cli.command('pair')
@click.argument('addr_or_name', required=False)
@click.pass_context
@install_adapter
def cmd_pair(ctx, addr_or_name):
    """List available devices for pairing. Optionally pair device if ADDR_OR_NAME is provided."""
    adapter = ctx.obj['adapter']
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        candidates = do_search_devices(device, addr_or_name)
        print_candidates = True
        if addr_or_name:
            candidate = lookup_candidate(candidates, addr_or_name)
            if candidate is not None:
                print("Device %s (%s) paired." % (candidate['deviceName'], candidate['address'], ))
                do_pair(device, candidate)
                print("Device %s connected." % (candidate['deviceName'], ))
                print_candidates = False
            else:
                print("Candidate %s not found. Found devices:" % (addr_or_name))
        if print_candidates:
            if candidates:
                print("\n".join(["%s: %s" % (d['address'], d['deviceName']) for d in candidates]))
            else:
                print("No devices found.")


@cli.command('unpair')
@click.argument('index_or_addr_or_name')
@click.pass_context
@install_adapter
def cmd_unpair(ctx, index_or_addr_or_name):
    """Unpair device designated by INDEX_OR_ADDR_OR_NAME."""
    adapter = ctx.obj['adapter']
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        removed = do_unpair(device, index_or_addr_or_name)
        if removed:
            print("Device %s unpaired." % (removed['deviceName'], ))
        else:
            print("Device %s not found." % (index_or_addr_or_name, ))


def handle_connect(target_connect, ctx, index_or_addr_or_connected):
    handler = do_connect if target_connect else do_disconnect
    adapter = ctx.obj['adapter']
    with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
        try:
            headsets = do_list_headsets(device)
            headset = next(filter(get_headset_matcher(index_or_addr_or_connected), headsets))
            handler(device, headset)
            if target_connect:
                print("Device %s connected." % (headset['deviceName'], ))
            else:
                print("Device %s disconnected." % (headset['deviceName'], ))
        except StopIteration:
            # disconnect if not device connected is not an error
            if target_connect:
                raise click.ClickException("Device %s not found." % (index_or_addr_or_connected, ))


@cli.command()
@click.option('--enabled/--disabled', 'status', default=None,
              help="Enable/disable auto-pairing; display current status if not provided.")
@click.pass_context
@install_adapter
def auto_pairing(ctx, status):
    """Configure auto-pairing status.
    
    When auto-pairing is enabled, if no known device is available when adapter
    is plugged in, a pairing is automatically done with first available device."""
    adapter = ctx.obj['adapter']
    if status is None:
        with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
            status = do_get_pairing_status(device)
            print("enabled" if status else "disabled")
    else:
        with hid.Device(adapter['vendor_id'], adapter['product_id'], adapter['serial_number']) as device:
            status = do_set_pairing_status(device, status)
            print("enabled" if status else "disabled")


def lookup_adapter(index_or_name_or_serial):
    try:
        adapters = do_list_adapters()
        return next(filter(get_adapter_matcher(index_or_name_or_serial), adapters))
    except StopIteration:
        raise JabraError("Device %s not found" % (index_or_name_or_serial, ))


def do_list_adapters():
    adapters = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    adapters = sorted(adapters, key=lambda a: a['serial_number'])
    for index, a in enumerate(adapters):
        a['index'] = index
    return adapters


def do_get_pairing_status(device):
    counter = 0
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x46\x13\x40'
    device.write(bytes(buff))
    counter += 1
    data = device.read(64)
    return struct.unpack('?', data[7:8])[0]


def do_set_pairing_status(device, status):
    counter = 0
    buff = bytearray(64)
    buff[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x87\x13\x40'
    buff[7:8] = struct.pack('?', status)
    device.write(bytes(buff))
    counter += 1
    device.read(64)
    return do_get_pairing_status(device)


def do_wait_connected(device, address):
    connected = False
    expected = b'\x11\x0d\x26\x01' + address
    while not connected:
        data = device.read(64)
        # data[16] = \x01 or \x04
        if data[4:14] == expected and data[16] & 5:
            connected = True


def do_connect(device, headset):
    counter = 0
    address = to_addr_bin(headset)
    buff = bytearray(64)
    buff[0:7] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x8d\x0d\x24'
    buff[8:14] = address
    device.write(bytes(buff))
    device.read(64)
    counter += 1
    do_wait_connected(device, address)


def do_disconnect(device, headset):
    counter = 0
    address = to_addr_bin(headset)
    buff = bytearray(64)
    buff[0:7] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x8d\x0d\x25'
    buff[8:14] = address
    device.write(bytes(buff))
    device.read(64)
    counter += 1
    connected = False
    expected = b'\x11\x0d\x26\x01' + address
    while not connected:
        data = device.read(64)
        # data[16] = \x01 or \x04
        if data[4:14] == expected and data[16] & 5:
            connected = True


def do_list_headsets(device):
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
        b_address = data[13:19]
        last = struct.unpack('?', data[7:8])[0]
        if b_address != b'\x00\x00\x00\x00\x00\x00':
            headset = dict()
            headset['index'] = index
            headset['address'] = to_address_str(b_address)
            headset['connected'] = data[11:12] == b'\x04'
            
            buff2 = bytearray(64)
            buff2[0:6] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x48\x0d\x32'
            buff2[8:9] = struct.pack('B', index)
            device.write(bytes(buff2))
            counter += 1
            data2 = device.read(64)
            headset['deviceName'] = to_deviceName_str(data2[9:64])
            headsets.append(headset)
        if last:
            break
        index = struct.unpack('B', data[8:9])[0]
    return headsets


def do_search_devices(device, addr_or_name):
    counter = 0
    buff = bytearray(64)
    buff[0:9] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x88\x0d\x20\x05\x14'
    device.write(bytes(buff))
    device.read(64)
    scan_ended = False
    candidates = []
    while not scan_ended:
        data = device.read(64)
        if data[4:8] == b'\x07\x0d\x23\x01':
            # scan ended message
            scan_ended = True
        if data[4:8] == b'\x13\x0d\x22\x01':
            # device detected
            get_or_initialize_candidate(candidates, data)
        if data[5:8] == b'\x0d\x2b\x01':
            # device name detected
            candidate = get_or_initialize_candidate(candidates, data)
            if candidate is not None:
                candidate['deviceName'] = to_deviceName_str(data[15:64])
        if addr_or_name is not None and lookup_candidate(candidates, addr_or_name):
            # expected candidate found
            scan_ended = True
    counter += 1
    return candidates


def do_pair(device, candidate):
    b_addr = to_addr_bin(candidate)
    counter = 0
    
    buff = bytearray(64)
    buff[0:7] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x48\x0d\x28'
    device.write(bytes(buff))
    device.read(64)
    
    buff = bytearray(64)
    buff[0:8] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x48\x0d\x32'
    device.write(bytes(buff))
    device.read(64)
    
    buff = bytearray(64)
    buff[0:8] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x8d\x0d\x30\x04'
    buff[8:14] = b_addr
    device.write(bytes(buff))
    device.read(64)
    do_wait_connected(device, b_addr)


def do_unpair(device, index_or_addr_or_name):
    headsets = do_list_headsets(device)
    current = next(filter(get_headset_matcher(index_or_addr_or_name), headsets), None)
    if current:
        if current['connected']:
            do_disconnect(device, current)
        counter = 0
        buff = bytearray(64)
        buff[0:7] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x88\x0d\x2a'
        buff[8:9] = struct.pack('B', current['index'])
        device.write(bytes(buff))
        device.read(64)
        device.read(64)
        return current


def do_clear(device):
    counter = 0
    buff = bytearray(64)
    buff[0:7] = b'\x05\x01\x00' + struct.pack('B', counter) + b'\x86\x0c\x04'
    device.write(bytes(buff))
    device.read(64)
    device.read(64)


def get_headset_matcher(target_bool_int_str):
    def f(headset):
        if isinstance(target_bool_int_str, bool):
            return headset['connected']
        if 'index' in headset:
            try:
                index = int(target_bool_int_str)
                return index == headset['index']
            except Exception:
                pass
        return headset['address'] == target_bool_int_str or headset['deviceName'] == target_bool_int_str
    return f


def get_adapter_matcher(target_str):
    def f(adapter):
        if 'index' in adapter:
            try:
                index = int(target_str)
                return index == adapter['index']
            except Exception:
                pass
        return adapter['serial_number'] == target_str or adapter['product_string'] == target_str
    return f


def get_or_initialize_candidate(candidates, data):
    addr = to_address_str(data[8:14])
    candidate = next(filter(lambda c: c['address'] == addr, candidates), None)
    if not candidate:
        candidate = {}
        candidate['address'] = addr
        candidate['deviceName'] = None
        candidates.append(candidate)
    return candidate


def lookup_candidate(candidates, addr_or_name):
    candidate = next(filter(get_headset_matcher(addr_or_name), candidates), None)
    return candidate if candidate and candidate['deviceName'] is not None else None


def to_deviceName_str(data):
    return ctypes.create_string_buffer(data).value.decode('ascii')


def to_address_str(b_address):
    return ':'.join(re.findall('..', binascii.b2a_hex(b_address).decode('ascii')))


def to_addr_bin(headset):
    return binascii.a2b_hex(headset['address'].replace(':', ''))