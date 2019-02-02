import json

from charttool.plugins.iidx7thcs import Iidx7thCsFormat

class Iidx12thCsFormat:
    @staticmethod
    def get_format_name():
        return "12thcs"

    @staticmethod
    def to_json(params):
        output = json.loads(Iidx7thCsFormat.to_json(params))
        output['metadata']['version'] = Iidx12thCsFormat.get_format_name()
        return json.dumps(output, indent=4)

    @staticmethod
    def to_chart(params):
        return Iidx7thCsFormat.to_chart(params)


def get_class():
    return Iidx12thCsFormat
