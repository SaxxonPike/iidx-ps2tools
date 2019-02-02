import json

from charttool.plugins.iidx3rdcs import Iidx3rdCsFormat

class Iidx4thCsFormat:
    @staticmethod
    def get_format_name():
        return "4thcs"

    @staticmethod
    def to_json(params):
        output = json.loads(Iidx3rdCsFormat.to_json(params))
        output['metadata']['version'] = Iidx4thCsFormat.get_format_name()
        return json.dumps(output, indent=4, sort_keys=True)

    @staticmethod
    def to_chart(params):
        return Iidx3rdCsFormat.to_chart(params)


def get_class():
    return Iidx4thCsFormat
