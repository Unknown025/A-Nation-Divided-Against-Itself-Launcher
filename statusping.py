import socket
import struct
import json
import time


def _unpack_varint(sock):
    """ Unpack the varint """
    data = 0
    for i in range(5):
        ordinal = sock.recv(1)

        if len(ordinal) == 0:
            break

        byte = ord(ordinal)
        data |= (byte & 0x7F) << 7 * i

        if not byte & 0x80:
            break

    return data


def _pack_varint(data):
    """ Pack the var int """
    ordinal = b''

    while True:
        byte = data & 0x7F
        data >>= 7
        ordinal += struct.pack('B', byte | (0x80 if data > 0 else 0))

        if data == 0:
            break

    return ordinal


def _pack_data(data):
    """ Page the data """
    if type(data) is str:
        data = data.encode('utf8')
        return _pack_varint(len(data)) + data
    elif type(data) is int:
        return struct.pack('H', data)
    elif type(data) is float:
        return struct.pack('L', int(data))
    else:
        return data


def _send_data(connection, *args):
    """ Send the data on the connection """
    data = b''

    for arg in args:
        data += _pack_data(arg)

    connection.send(_pack_varint(len(data)) + data)


def _read_fully(connection, extra_varint=False):
    """ Read the connection and return the bytes """
    packet_length = _unpack_varint(connection)
    packet_id = _unpack_varint(connection)
    byte = b''

    if extra_varint:
        # Packet contained netty header offset for this
        if packet_id > packet_length:
            _unpack_varint(connection)

        extra_length = _unpack_varint(connection)

        while len(byte) < extra_length:
            byte += connection.recv(extra_length)

    else:
        byte = connection.recv(packet_length)

    return byte


class StatusPing:
    """ Get the ping status for the Minecraft server """

    def __init__(self, host='andai.rainyville.org', port=25565, timeout=5):
        """ Init the hostname and the port """
        self._host = host
        self._port = port
        self._timeout = timeout

    def get_status(self):
        """ Get the status response """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(self._timeout)
            connection.connect((self._host, self._port))

            # Send handshake + status request
            _send_data(connection, b'\x00\x00', self._host, self._port, b'\x01')
            _send_data(connection, b'\x00')

            # Read response, offset for string length
            data = _read_fully(connection, extra_varint=True)

            # Send and read unix time
            _send_data(connection, b'\x01', time.time() * 1000)
            unix = _read_fully(connection)

        # Load json and return
        response = json.loads(data.decode('utf8'))
        response['ping'] = int(time.time() * 1000) - struct.unpack('L', unix)[0]

        return response
