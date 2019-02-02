import json

from charttool.plugins.iidx7thcs import Iidx7thCsFormat

class Iidx9thCsFormat:
    @staticmethod
    def get_format_name():
        return "9thcs"

    @staticmethod
    def to_json(params):
        output = json.loads(Iidx7thCsFormat.to_json(params))
        output['metadata']['version'] = Iidx9thCsFormat.get_format_name()
        return json.dumps(output, indent=4)

    @staticmethod
    def to_chart(params):
        return Iidx7thCsFormat.to_chart(params)


def get_class():
    return Iidx9thCsFormat
