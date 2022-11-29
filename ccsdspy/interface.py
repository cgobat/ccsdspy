"""High level Object-Oriented interface methods for the package."""

__author__ = "Daniel da Silva <mail@danieldasilva.org>"
import os.path
import csv

import numpy as np

from .decode import _decode_fixed_length


class PacketField(object):
    """A field contained in a packet.
    """

    def __init__(self, name, data_type, bit_length, bit_offset=None,
                 byte_order='big'):
        """
        Parameters
        ----------
        name : str
            String identifier for the field. The name specified how you may
            call upon this data later.
        data_type : {'uint', 'int', 'float', 'str', 'fill'}
            Data type of the field.
        bit_length : int
            Number of bits contained in the field.
        bit_offset : int, optional
            Bit offset into packet, including the primary header which is 48 bits long.
            If this is not specified, than the bit offset will the be calculated automatically
            from its position inside the packet definition.
        byte_order : {'big', 'little'}, optional
            Byte order of the field. Defaults to big endian.

        Raises
        ------
        TypeError
             If one of the arguments is not of the correct type.
        ValueError
             data_type or byte_order is invalid
        """
        if not isinstance(name, str):
            raise TypeError('name parameter must be a str')
        if not isinstance(data_type, str):
            raise TypeError('data_type parameter must be a str')
        if not isinstance(bit_length, (int, np.integer)):
            raise TypeError('bit_length parameter must be an int')
        if not (bit_offset is None or isinstance(bit_offset, (int, np.integer))):
            raise TypeError('bit_offset parameter must be an int')

        valid_data_types = ('uint', 'int', 'float', 'str', 'fill')
        if data_type not in valid_data_types:
            raise ValueError(f'data_type must be one of {valid_data_types}')

        valid_byte_orders = ('big', 'little')
        if byte_order not in valid_byte_orders:
            raise ValueError(f'byte_order must be one of {valid_byte_orders}')

        self._name = name
        self._data_type = data_type
        self._bit_length = bit_length
        self._bit_offset = bit_offset
        self._byte_order = byte_order

    def __repr__(self):
        values = {k: repr(v) for (k, v) in self.__dict__.items()}

        return ('PacketField(name={_name}, data_type={_data_type}, '
                'bit_length={_bit_length}, bit_offset={_bit_offset}, '
                'byte_order={_byte_order})'.format(**values))

    def __iter__(self):
        return iter([('name', self._name), ('dataType', self._data_type), ('bitLength', self._bit_length), ('bitOffset', self._bit_offset), ('byteOrder', self._byte_order)])


class FixedLength(object):
    """Define a fixed length packet to decode binary data.

    In the context of engineering and science, fixed length packets correspond
    to data that is of the same layout every time. Examples of this include
    sensor time series, status codes, or error messages.
    """
    def __init__(self, fields):
        """
        Parameters
        ----------
        fields : list of `ccsdspy.PacketField`
            Layout of packet fields contained in the definition.
        """
        self._fields = fields[:]

    @classmethod
    def from_file(cls, file):
        """
        Parameters
        ----------
        file: str
           Path to file on the local file system that defines the packet fields.
           Currently only suports csv files.  See :download:`simple_csv_3col.csv <../../ccsdspy/tests/data/packet_def/simple_csv_3col.csv>`
           and :download:`simple_csv_4col.csv <../../ccsdspy/tests/data/packet_def/simple_csv_4col.csv>`
        
        Returns
        -------
        An instance of FixedLength.
        """
        file_extension = os.path.splitext(file)
        if file_extension[1] == ".csv":
            fields = _get_fields_csv_file(file)
        else:
            raise ValueError(f"File type {file_extension[1]} not supported.")

        return cls(fields)

    def load(self, file, include_primary_header=False):
        """Decode a file-like object containing a sequence of these packets.

        Parameters
        ----------
        file: str
           Path to file on the local file system, or file-like object
        include_primary_header: bool
           If True, provides the primary header in the output

        Returns
        -------
        dictionary mapping field names to NumPy arrays, with key order matching
        the order fields in the packet.
        """
        if hasattr(file, 'read'):
            file_bytes = np.frombuffer(file.read(), 'u1')
        else:
            file_bytes = np.fromfile(file, 'u1')

        if include_primary_header:
            self._fields = [PacketField(name="CCSDS_VERSION_NUMBER", data_type='uint', bit_length=3, bit_offset=0),
                            PacketField(name="CCSDS_PACKET_TYPE", data_type='uint', bit_length=1, bit_offset=3),
                            PacketField(name="CCSDS_SECONDARY_FLAG", data_type='uint', bit_length=1, bit_offset=4),
                            PacketField(name="CCSDS_APID", data_type='uint', bit_length=11, bit_offset=5),
                            PacketField(name="CCSDS_SEQUENCE_FLAG", data_type='uint', bit_length=2, bit_offset=16),
                            PacketField(name="CCSDS_SEQUENCE_COUNT", data_type='uint', bit_length=14, bit_offset=18),
                            PacketField(name="CCSDS_PACKET_LENGTH", data_type='uint', bit_length=16, bit_offset=32),
                            ] + self._fields

        field_arrays = _decode_fixed_length(file_bytes, self._fields)
        return field_arrays


def _get_fields_csv_file(csv_file):
    """Parse a simple comma-delimited file that defines a packet. Should not include the CCSDS header.
    The minimum set of columns are (name, data_type, bit_length). An optional bit_offset can also be provided.

    Parameters
    ----------
    csv_file: str
        Path to file on the local file system

    Returns
    -------
    fields: list
        A list of `PacketField` objects.
    """
    req_columns = ['name', 'data_type', 'bit_length']

    with open(csv_file, "r") as fp:
        fields = []
        reader = csv.DictReader(fp, skipinitialspace=True)
        headers = reader.fieldnames
        if not all(req_col in headers for req_col in req_columns):
            raise ValueError(f"Minimum required columns are {req_columns}.")
        for row in reader:  # skip the header row
            if 'bit_offset' not in headers:  # 3 col csv file
                fields.append(PacketField(name=row['name'], data_type=row['data_type'], bit_length=int(row['bit_length'])))
            if 'bit_offset' in headers:  # 4 col csv file provides bit offsets
                # TODO: Check the consistency of bit_offsets versus previous bit_lengths
                fields.append(PacketField(name=row['name'], data_type=row['data_type'], bit_length=int(row['bit_length']), bit_offset=int(row['bit_offset'])))

    return fields
