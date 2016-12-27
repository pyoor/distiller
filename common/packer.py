import msgpack
import zlib


def unpack(job):
    data = msgpack.unpackb(zlib.decompress(job))
    return data


def pack(job):
    data = zlib.compress(msgpack.packb(job, use_bin_type=True), 9)
    return data
