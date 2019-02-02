import json

from charttool.plugins.iidx5thcs import Iidx5thCsFormat

class Iidx6thCsFormat:
    @staticmethod
    def get_format_name():
        return "6thcs"

    @staticmethod
    def to_json(params):
        output = json.loads(Iidx5thCsFormat.to_json(params))
        output['metadata']['version'] = Iidx6thCsFormat.get_format_name()
        return json.dumps(output, indent=4)

    @staticmethod
    def to_chart(params):
        return Iidx5thCsFormat.to_chart(params)


def get_class():
    return Iidx6thCsFormat
